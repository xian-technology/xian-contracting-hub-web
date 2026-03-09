"""Application settings and local environment helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE_NAME = ".env"
DEFAULT_INSTANCE_DIR_NAME = ".local"
DEFAULT_SQLITE_FILENAME = "contracting_hub.db"
DEFAULT_ENVIRONMENT = "development"


def _read_env_file(env_file: Path) -> dict[str, str]:
    """Parse a minimal dotenv file without adding a runtime dependency."""
    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")
        if not separator:
            continue

        cleaned_key = key.strip()
        cleaned_value = value.strip().strip('"').strip("'")
        if cleaned_key:
            values[cleaned_key] = cleaned_value

    return values


def _resolve_path(value: str | None, *, base_dir: Path) -> Path | None:
    """Resolve a user-supplied filesystem path relative to the project root."""
    if value is None or not value.strip():
        return None

    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def sqlite_url_for_path(path: Path) -> str:
    """Convert a filesystem path into a SQLAlchemy SQLite URL."""
    resolved_path = path.expanduser().resolve()
    return f"sqlite:///{resolved_path.as_posix()}"


def _sqlite_path_from_url(database_url: str, *, base_dir: Path) -> Path | None:
    """Extract a filesystem path from a SQLite URL when possible."""
    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return None

    raw_path = database_url.removeprefix(sqlite_prefix)
    if raw_path in {"", ":memory:"} or raw_path.startswith("file:"):
        return None

    return _resolve_path(raw_path, base_dir=base_dir)


def _normalize_database_url(database_url: str, *, base_dir: Path) -> str:
    """Normalize relative SQLite URLs so runtime and CLI calls agree on one path."""
    sqlite_path = _sqlite_path_from_url(database_url, base_dir=base_dir)
    if sqlite_path is None:
        return database_url
    return sqlite_url_for_path(sqlite_path)


@dataclass(frozen=True)
class AppSettings:
    """Resolved application settings for the local development environment."""

    environment: str
    env_file: Path
    project_root: Path
    instance_dir: Path
    database_url: str
    sqlite_database_path: Path | None
    alembic_config_path: Path
    migrations_dir: Path

    @property
    def uses_sqlite(self) -> bool:
        """Return whether the configured database is SQLite-backed."""
        return self.sqlite_database_path is not None or self.database_url.startswith("sqlite:")

    def ensure_local_paths(self) -> None:
        """Create local filesystem directories required by the current settings."""
        if self.sqlite_database_path is not None:
            self.sqlite_database_path.parent.mkdir(parents=True, exist_ok=True)


def load_settings(
    *,
    project_root: Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = None,
) -> AppSettings:
    """Load application settings from `.env` and environment variables."""
    resolved_project_root = project_root.resolve()
    resolved_env_file = (env_file or (resolved_project_root / DEFAULT_ENV_FILE_NAME)).resolve()
    dotenv_values = _read_env_file(resolved_env_file)
    merged_environment = {**dotenv_values, **dict(environ or os.environ)}

    environment_name = merged_environment.get("CONTRACTING_HUB_ENV", DEFAULT_ENVIRONMENT)
    instance_dir = (
        _resolve_path(
            merged_environment.get("CONTRACTING_HUB_INSTANCE_DIR"),
            base_dir=resolved_project_root,
        )
        or (resolved_project_root / DEFAULT_INSTANCE_DIR_NAME).resolve()
    )
    database_url_override = merged_environment.get("REFLEX_DB_URL") or merged_environment.get(
        "CONTRACTING_HUB_DB_URL"
    )

    if database_url_override:
        database_url = _normalize_database_url(
            database_url_override,
            base_dir=resolved_project_root,
        )
        sqlite_database_path = _sqlite_path_from_url(database_url, base_dir=resolved_project_root)
    else:
        sqlite_database_path = (
            _resolve_path(
                merged_environment.get("CONTRACTING_HUB_DB_PATH"),
                base_dir=resolved_project_root,
            )
            or (instance_dir / DEFAULT_SQLITE_FILENAME).resolve()
        )
        database_url = sqlite_url_for_path(sqlite_database_path)

    return AppSettings(
        environment=environment_name,
        env_file=resolved_env_file,
        project_root=resolved_project_root,
        instance_dir=instance_dir,
        database_url=database_url,
        sqlite_database_path=sqlite_database_path,
        alembic_config_path=resolved_project_root / "alembic.ini",
        migrations_dir=resolved_project_root / "migrations",
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached application settings for the current process."""
    return load_settings()


__all__ = [
    "APP_SETTINGS",
    "AppSettings",
    "DEFAULT_ENVIRONMENT",
    "PROJECT_ROOT",
    "get_settings",
    "load_settings",
    "sqlite_url_for_path",
]

APP_SETTINGS = get_settings()
