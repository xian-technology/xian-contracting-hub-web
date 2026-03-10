"""Repeatable local reset helpers for development and QA databases."""

from __future__ import annotations

import argparse
import os
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlmodel import Session

from contracting_hub.config import AppSettings, get_settings
from contracting_hub.database import _configure_sqlite_engine
from contracting_hub.services.bootstrap import (
    BootstrapSeedReport,
    _format_bootstrap_report,
    seed_local_development_data,
)


@dataclass(frozen=True)
class LocalResetReport:
    """Summary of one local reset and reseed run."""

    database_removed: bool
    database_sidecars_removed: int
    uploads_cleared: bool
    migrations_applied: bool
    seed_report: BootstrapSeedReport


def reset_local_development_environment(
    *,
    settings: AppSettings | None = None,
    include_demo_data: bool = True,
) -> LocalResetReport:
    """Reset the configured SQLite database, uploads, migrations, and seed data."""
    resolved_settings = settings or get_settings()
    if not resolved_settings.uses_sqlite or resolved_settings.sqlite_database_path is None:
        raise ValueError("Local reset only supports SQLite-backed configurations.")

    database_removed, database_sidecars_removed = _remove_sqlite_database_files(
        resolved_settings.sqlite_database_path
    )
    uploads_cleared = _reset_uploads_directory(resolved_settings)

    with _temporary_settings_environment(resolved_settings):
        _upgrade_database_to_head(resolved_settings)
        engine = sa.create_engine(resolved_settings.database_url)
        _configure_sqlite_engine(engine)
        with Session(engine) as session:
            seed_report = seed_local_development_data(
                settings=resolved_settings,
                session=session,
                include_demo_data=include_demo_data,
            )
        engine.dispose()

    return LocalResetReport(
        database_removed=database_removed,
        database_sidecars_removed=database_sidecars_removed,
        uploads_cleared=uploads_cleared,
        migrations_applied=True,
        seed_report=seed_report,
    )


def _remove_sqlite_database_files(database_path) -> tuple[bool, int]:
    database_removed = False
    if database_path.exists():
        database_path.unlink()
        database_removed = True

    removed_sidecars = 0
    for suffix in ("-shm", "-wal", "-journal"):
        sidecar_path = database_path.with_name(f"{database_path.name}{suffix}")
        if not sidecar_path.exists():
            continue
        sidecar_path.unlink()
        removed_sidecars += 1

    return database_removed, removed_sidecars


def _reset_uploads_directory(settings: AppSettings) -> bool:
    if settings.uploads_dir.exists():
        shutil.rmtree(settings.uploads_dir)
        cleared = True
    else:
        cleared = False

    settings.ensure_local_paths()
    return cleared


def _upgrade_database_to_head(settings: AppSettings) -> None:
    command.upgrade(Config(str(settings.alembic_config_path)), "head")


@contextmanager
def _temporary_settings_environment(settings: AppSettings) -> Iterator[None]:
    overrides = {
        "CONTRACTING_HUB_ENV": settings.environment,
        "CONTRACTING_HUB_INSTANCE_DIR": str(settings.instance_dir),
        "CONTRACTING_HUB_UPLOADS_DIR": str(settings.uploads_dir),
        "CONTRACTING_HUB_AVATAR_UPLOAD_DIR": str(settings.avatar_upload_dir),
        "CONTRACTING_HUB_DB_URL": settings.database_url,
        "REFLEX_DB_URL": settings.database_url,
    }
    previous_values = {key: os.environ.get(key) for key in overrides}

    try:
        for key, value in overrides.items():
            os.environ[key] = value
        get_settings.cache_clear()
        yield
    finally:
        for key, previous_value in previous_values.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value
        get_settings.cache_clear()


def _format_local_reset_report(report: LocalResetReport) -> str:
    lines = [
        f"database_removed={report.database_removed}",
        f"database_sidecars_removed={report.database_sidecars_removed}",
        f"uploads_cleared={report.uploads_cleared}",
        f"migrations_applied={report.migrations_applied}",
    ]
    lines.append(_format_bootstrap_report(report.seed_report))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Reset the configured local environment and print a concise summary."""
    parser = argparse.ArgumentParser(
        prog="python -m contracting_hub.services.local_reset",
        description="Reset the configured local database, uploads, and demo seed data.",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Reset the environment but seed only the base taxonomy and bootstrap admin.",
    )
    args = parser.parse_args(argv)

    report = reset_local_development_environment(include_demo_data=not args.bootstrap_only)
    print(_format_local_reset_report(report))
    return 0 if report.seed_report.schema_ready else 1


__all__ = ["LocalResetReport", "main", "reset_local_development_environment"]


if __name__ == "__main__":
    raise SystemExit(main())
