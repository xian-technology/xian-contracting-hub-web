from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from reflex.model import ModelRegistry
from sqlalchemy import inspect

import contracting_hub.models  # noqa: F401
from contracting_hub.config import get_settings
from contracting_hub.repositories import CONTRACT_SEARCH_INDEX_TABLE_NAME
from contracting_hub.services import SEARCH_INDEX_SHADOW_TABLE_NAMES


def _database_url(database_path: Path) -> str:
    return f"sqlite:///{database_path}"


def _load_alembic_config() -> Config:
    settings = get_settings()
    return Config(str(settings.alembic_config_path))


def _schema_snapshot(database_url: str) -> dict[str, dict[str, object]]:
    engine = sa.create_engine(database_url)
    inspector = inspect(engine)
    tables = sorted(
        table
        for table in inspector.get_table_names()
        if table != "alembic_version" and table not in SEARCH_INDEX_SHADOW_TABLE_NAMES
    )

    return {
        table: {
            "columns": [
                (column["name"], str(column["type"]), column["nullable"])
                for column in inspector.get_columns(table)
            ],
            "indexes": sorted(
                (
                    index["name"],
                    tuple(index["column_names"]),
                    bool(index.get("unique")),
                )
                for index in inspector.get_indexes(table)
            ),
            "unique_constraints": sorted(
                (constraint["name"], tuple(constraint["column_names"]))
                for constraint in inspector.get_unique_constraints(table)
            ),
            "check_constraints": sorted(
                (constraint["name"], constraint["sqltext"])
                for constraint in inspector.get_check_constraints(table)
            ),
            "foreign_keys": sorted(
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in inspector.get_foreign_keys(table)
            ),
        }
        for table in tables
    }


def test_initial_migration_matches_model_registry_schema(
    tmp_path: Path,
    monkeypatch,
) -> None:
    migrated_database_path = tmp_path / "migrated.db"
    direct_database_path = tmp_path / "direct.db"

    monkeypatch.setenv("REFLEX_DB_URL", _database_url(migrated_database_path))
    get_settings.cache_clear()
    command.upgrade(_load_alembic_config(), "head")

    direct_engine = sa.create_engine(_database_url(direct_database_path))
    ModelRegistry.get_metadata().create_all(direct_engine)

    assert _schema_snapshot(_database_url(migrated_database_path)) == _schema_snapshot(
        _database_url(direct_database_path)
    )


def test_initial_migration_downgrades_to_base(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "downgrade.db"

    monkeypatch.setenv("REFLEX_DB_URL", _database_url(database_path))
    get_settings.cache_clear()
    alembic_config = _load_alembic_config()

    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    inspector = inspect(sa.create_engine(_database_url(database_path)))

    assert inspector.get_table_names() == ["alembic_version"]


def test_head_migration_creates_contract_search_index(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "search.db"

    monkeypatch.setenv("REFLEX_DB_URL", _database_url(database_path))
    get_settings.cache_clear()
    command.upgrade(_load_alembic_config(), "head")

    engine = sa.create_engine(_database_url(database_path))
    with engine.connect() as connection:
        search_schema_sql = connection.execute(
            sa.text(
                """
                SELECT sql
                FROM sqlite_master
                WHERE name = :table_name
                """
            ),
            {"table_name": CONTRACT_SEARCH_INDEX_TABLE_NAME},
        ).scalar_one()

    assert "CREATE VIRTUAL TABLE contract_search_index USING fts5" in search_schema_sql
