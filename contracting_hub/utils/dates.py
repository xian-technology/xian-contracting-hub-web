"""Normalize database timestamps at service boundaries."""

from datetime import datetime, timezone


def coerce_utc_datetime(value: datetime) -> datetime:
    """Interpret naive SQLite timestamps as UTC and normalize aware timestamps."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
