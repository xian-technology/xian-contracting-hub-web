from pathlib import Path

import pytest

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
    assert settings.uploads_dir == (tmp_path / "uploads").resolve()
    assert settings.avatar_upload_dir == (tmp_path / "uploads" / "avatars").resolve()
    assert settings.managed_upload_max_bytes == 10 * 1024 * 1024
    assert settings.avatar_upload_max_bytes == 5 * 1024 * 1024
    assert settings.alembic_config_path == tmp_path / "alembic.ini"
    assert settings.migrations_dir == tmp_path / "migrations"


def test_environment_variables_override_dotenv_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        (
            "CONTRACTING_HUB_ENV=staging\n"
            "CONTRACTING_HUB_DB_PATH=data/from-dotenv.db\n"
            "CONTRACTING_HUB_UPLOADS_DIR=uploads/from-dotenv\n"
        ),
        encoding="utf-8",
    )

    settings = load_settings(
        project_root=tmp_path,
        env_file=env_file,
        environ={
            "CONTRACTING_HUB_ENV": "test",
            "REFLEX_DB_URL": "sqlite:///override.db",
            "CONTRACTING_HUB_AVATAR_UPLOAD_DIR": "custom/avatars",
            "CONTRACTING_HUB_UPLOAD_MAX_BYTES": "1234",
            "CONTRACTING_HUB_AVATAR_UPLOAD_MAX_BYTES": "456",
        },
    )

    expected_database_path = (tmp_path / "override.db").resolve()

    assert settings.environment == "test"
    assert settings.sqlite_database_path == expected_database_path
    assert settings.database_url == sqlite_url_for_path(expected_database_path)
    assert settings.uploads_dir == (tmp_path / "uploads" / "from-dotenv").resolve()
    assert (
        settings.avatar_upload_dir
        == (tmp_path / "uploads" / "from-dotenv" / "custom" / "avatars").resolve()
    )
    assert settings.managed_upload_max_bytes == 1234
    assert settings.avatar_upload_max_bytes == 456


def test_ensure_local_paths_creates_sqlite_and_upload_directories(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={"CONTRACTING_HUB_INSTANCE_DIR": "runtime"},
        env_file=tmp_path / ".env",
    )

    settings.ensure_local_paths()

    assert (tmp_path / "runtime").exists()
    assert (tmp_path / "uploads").exists()
    assert (tmp_path / "uploads" / "avatars").exists()


def test_avatar_upload_dir_must_stay_within_uploads_dir(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must stay within"):
        load_settings(
            project_root=tmp_path,
            environ={
                "CONTRACTING_HUB_UPLOADS_DIR": "uploads",
                "CONTRACTING_HUB_AVATAR_UPLOAD_DIR": "../shared/avatars",
            },
            env_file=tmp_path / ".env",
        )
