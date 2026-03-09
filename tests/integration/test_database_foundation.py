import pytest

from contracting_hub.config import get_settings
from contracting_hub.database import get_engine, ping_database

pytestmark = pytest.mark.smoke


def test_rxconfig_uses_resolved_database_settings(rxconfig_module: dict[str, object]) -> None:
    settings = get_settings()

    assert rxconfig_module["config"].db_url == settings.database_url
    assert settings.env_file.name == ".env"


def test_database_engine_enables_sqlite_foreign_keys() -> None:
    engine = get_engine()

    assert engine.url.render_as_string(hide_password=False) == get_settings().database_url

    with engine.connect() as connection:
        pragma_value = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()

    assert pragma_value == 1
    assert ping_database() is True


def test_migration_scaffold_uses_project_layout() -> None:
    settings = get_settings()

    assert settings.alembic_config_path.exists()
    assert settings.migrations_dir.exists()
    assert (settings.migrations_dir / "env.py").exists()
    assert (settings.migrations_dir / "script.py.mako").exists()
    assert (settings.migrations_dir / "versions").is_dir()
