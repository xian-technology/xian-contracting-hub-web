from pathlib import Path

from contracting_hub.config import load_settings, sqlite_url_for_path


def test_load_settings_uses_local_sqlite_defaults(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={},
        env_file=tmp_path / ".env",
    )

    expected_database_path = (tmp_path / ".local" / "contracting_hub.db").resolve()

    assert settings.environment == "development"
    assert settings.sqlite_database_path == expected_database_path
    assert settings.database_url == sqlite_url_for_path(expected_database_path)
    assert settings.alembic_config_path == tmp_path / "alembic.ini"
    assert settings.migrations_dir == tmp_path / "migrations"


def test_environment_variables_override_dotenv_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CONTRACTING_HUB_ENV=staging\nCONTRACTING_HUB_DB_PATH=data/from-dotenv.db\n",
        encoding="utf-8",
    )

    settings = load_settings(
        project_root=tmp_path,
        env_file=env_file,
        environ={
            "CONTRACTING_HUB_ENV": "test",
            "REFLEX_DB_URL": "sqlite:///override.db",
        },
    )

    expected_database_path = (tmp_path / "override.db").resolve()

    assert settings.environment == "test"
    assert settings.sqlite_database_path == expected_database_path
    assert settings.database_url == sqlite_url_for_path(expected_database_path)


def test_ensure_local_paths_creates_sqlite_parent_directory(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={"CONTRACTING_HUB_INSTANCE_DIR": "runtime"},
        env_file=tmp_path / ".env",
    )

    settings.ensure_local_paths()

    assert (tmp_path / "runtime").exists()
