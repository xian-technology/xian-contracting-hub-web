from pathlib import Path

import pytest

from contracting_hub.config import load_settings, sqlite_url_for_path


def test_explicit_empty_environment_does_not_read_process_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTRACTING_HUB_ENV", "production")
    monkeypatch.setenv("CONTRACTING_HUB_DB_PATH", "/host-only/production.db")
    env_file = tmp_path / ".env"
    env_file.write_text("CONTRACTING_HUB_ENV=dotenv\n")

    settings = load_settings(project_root=tmp_path, environ={}, env_file=env_file)

    assert settings.environment == "dotenv"
    assert settings.sqlite_database_path == tmp_path / ".local" / "contracting_hub.db"


def test_omitted_environment_reads_process_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTRACTING_HUB_ENV", "process")
    settings = load_settings(project_root=tmp_path, env_file=tmp_path / ".env")

    assert settings.environment == "process"


@pytest.mark.parametrize(
    ("environ", "expected_url", "relative_path"),
    [
        ({}, None, ".local/contracting_hub.db"),
        ({"CONTRACTING_HUB_DB_PATH": "data/custom.db"}, None, "data/custom.db"),
        ({"CONTRACTING_HUB_DB_URL": "sqlite:///catalog.db"}, None, "catalog.db"),
        (
            {"REFLEX_DB_URL": "", "CONTRACTING_HUB_DB_URL": "sqlite:///fallback.db"},
            None,
            "fallback.db",
        ),
        (
            {
                "REFLEX_DB_URL": "sqlite:///reflex.db",
                "CONTRACTING_HUB_DB_URL": "sqlite:///other.db",
            },
            None,
            "reflex.db",
        ),
        ({"REFLEX_DB_URL": "sqlite:///:memory:"}, "sqlite:///:memory:", None),
        (
            {"REFLEX_DB_URL": "postgresql://localhost/catalog"},
            "postgresql://localhost/catalog",
            None,
        ),
    ],
)
def test_database_configuration_precedence_and_paths(
    tmp_path, environ, expected_url, relative_path
):
    settings = load_settings(project_root=tmp_path, environ=environ, env_file=tmp_path / ".env")
    expected_path = tmp_path / relative_path if relative_path is not None else None

    assert settings.sqlite_database_path == expected_path
    assert settings.database_url == (
        sqlite_url_for_path(expected_path) if expected_path is not None else expected_url
    )


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
    assert settings.bootstrap_admin_email == "admin@contractinghub.local"
    assert settings.bootstrap_admin_username == "admin"
    assert settings.bootstrap_admin_display_name == "Local Admin"
    assert settings.bootstrap_admin_password_hash == "!bootstrap-admin-auth-pending!"
    assert settings.playground_deep_link_base_url is None
    assert settings.playground_callback_url is None
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
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_EMAIL": "ops@example.com",
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_USERNAME": "opsadmin",
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Ops Admin",
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_PASSWORD_HASH": "hashed-admin",
            "CONTRACTING_HUB_PLAYGROUND_DEEP_LINK_BASE_URL": "https://playground.local/deploy",
            "CONTRACTING_HUB_PLAYGROUND_CALLBACK_URL": "https://hub.local/callback",
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
    assert settings.bootstrap_admin_email == "ops@example.com"
    assert settings.bootstrap_admin_username == "opsadmin"
    assert settings.bootstrap_admin_display_name == "Ops Admin"
    assert settings.bootstrap_admin_password_hash == "hashed-admin"
    assert settings.playground_deep_link_base_url == "https://playground.local/deploy"
    assert settings.playground_callback_url == "https://hub.local/callback"


def test_blank_bootstrap_admin_identity_disables_local_admin_seed(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_EMAIL": "",
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_USERNAME": " ",
        },
        env_file=tmp_path / ".env",
    )

    assert settings.bootstrap_admin_email is None
    assert settings.bootstrap_admin_username is None


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
