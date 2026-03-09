"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import reflex as rx
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from contracting_hub.config import get_settings


def _configure_sqlite_engine(engine: Engine) -> None:
    """Apply SQLite-specific connection settings once per engine instance."""
    if engine.dialect.name != "sqlite" or getattr(
        engine,
        "_contracting_hub_sqlite_configured",
        False,
    ):
        return

    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine, "connect", _set_pragmas)
    engine._contracting_hub_sqlite_configured = True


def get_engine() -> Engine:
    """Return the configured SQLAlchemy engine."""
    settings = get_settings()
    settings.ensure_local_paths()
    engine = rx.Model.get_db_engine()
    _configure_sqlite_engine(engine)
    return engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a SQLModel session bound to the configured engine."""
    with Session(get_engine()) as session:
        yield session


def ping_database() -> bool:
    """Run a minimal query against the configured database."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


__all__ = ["get_engine", "ping_database", "session_scope"]
