"""Shared SQLModel base classes."""

from __future__ import annotations

from datetime import datetime, timezone

import reflex as rx
import sqlmodel


def utc_now() -> datetime:
    """Return an aware UTC timestamp for model defaults."""
    return datetime.now(timezone.utc)


class AppModel(rx.Model, table=False):
    """Base model for all application tables."""


class TimestampedModel(AppModel, table=False):
    """Mixin for tables that track creation and update times."""

    created_at: datetime = sqlmodel.Field(default_factory=utc_now, nullable=False, index=True)
    updated_at: datetime = sqlmodel.Field(
        default_factory=utc_now,
        nullable=False,
        index=True,
        sa_column_kwargs={"onupdate": utc_now},
    )


__all__ = ["AppModel", "TimestampedModel", "utc_now"]
