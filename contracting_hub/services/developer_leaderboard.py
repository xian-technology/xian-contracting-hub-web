"""Service helpers for the public developer leaderboard page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import sqlalchemy as sa
from sqlmodel import Session

from contracting_hub.database import session_scope
from contracting_hub.services.developer_kpis import (
    DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS,
    DEFAULT_DEVELOPER_LEADERBOARD_LIMIT,
    DeveloperKPIAggregate,
    DeveloperKPIServiceError,
    DeveloperLeaderboardSort,
    DeveloperLeaderboardTimeframe,
    build_developer_activity_window_start,
    list_developer_leaderboard,
    normalize_developer_activity_window_days,
    normalize_developer_leaderboard_sort,
    normalize_developer_leaderboard_timeframe,
)
from contracting_hub.utils.meta import DEVELOPER_LEADERBOARD_ROUTE

DEFAULT_PUBLIC_DEVELOPER_LEADERBOARD_LIMIT = DEFAULT_DEVELOPER_LEADERBOARD_LIMIT


@dataclass(frozen=True)
class PublicDeveloperLeaderboardSnapshot:
    """Public leaderboard data plus normalized filter state."""

    entries: tuple[DeveloperKPIAggregate, ...]
    sort: DeveloperLeaderboardSort
    timeframe: DeveloperLeaderboardTimeframe
    activity_window_days: int
    activity_since: datetime


def normalize_public_developer_leaderboard_sort(
    sort: DeveloperLeaderboardSort | str | None,
) -> DeveloperLeaderboardSort:
    """Normalize public leaderboard sort input from the URL or UI."""
    try:
        return normalize_developer_leaderboard_sort(sort)
    except DeveloperKPIServiceError:
        return normalize_developer_leaderboard_sort(None)


def normalize_public_developer_leaderboard_timeframe(
    timeframe: DeveloperLeaderboardTimeframe | str | None,
) -> DeveloperLeaderboardTimeframe:
    """Normalize public leaderboard timeframe input from the URL or UI."""
    try:
        return normalize_developer_leaderboard_timeframe(timeframe)
    except DeveloperKPIServiceError:
        return normalize_developer_leaderboard_timeframe(None)


def normalize_public_developer_activity_window_days(window_days: int | str | None) -> int:
    """Normalize the public recent-activity window from string or integer inputs."""
    parsed_window_days: int | None
    if isinstance(window_days, str):
        normalized_window_days = window_days.strip()
        if not normalized_window_days:
            return DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS
        if not normalized_window_days.isdigit():
            return DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS
        parsed_window_days = int(normalized_window_days)
    else:
        parsed_window_days = window_days

    try:
        return normalize_developer_activity_window_days(parsed_window_days)
    except DeveloperKPIServiceError:
        return DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS


def build_empty_public_developer_leaderboard_snapshot(
    *,
    sort: DeveloperLeaderboardSort | str | None = None,
    timeframe: DeveloperLeaderboardTimeframe | str | None = None,
    activity_window_days: int | str | None = None,
    now: datetime | None = None,
) -> PublicDeveloperLeaderboardSnapshot:
    """Return a stable empty leaderboard snapshot for first render or fallback states."""
    resolved_sort = normalize_public_developer_leaderboard_sort(sort)
    resolved_timeframe = normalize_public_developer_leaderboard_timeframe(timeframe)
    resolved_window_days = normalize_public_developer_activity_window_days(activity_window_days)
    return PublicDeveloperLeaderboardSnapshot(
        entries=(),
        sort=resolved_sort,
        timeframe=resolved_timeframe,
        activity_window_days=resolved_window_days,
        activity_since=build_developer_activity_window_start(
            window_days=resolved_window_days,
            now=now,
        ),
    )


def build_public_developer_leaderboard_path(
    *,
    sort: DeveloperLeaderboardSort | str | None = None,
    timeframe: DeveloperLeaderboardTimeframe | str | None = None,
    activity_window_days: int | str | None = None,
) -> str:
    """Build the canonical public leaderboard URL for the current filter state."""
    resolved_sort = normalize_public_developer_leaderboard_sort(sort)
    resolved_timeframe = normalize_public_developer_leaderboard_timeframe(timeframe)
    resolved_window_days = normalize_public_developer_activity_window_days(activity_window_days)

    params: dict[str, str] = {}
    if resolved_sort is not normalize_public_developer_leaderboard_sort(None):
        params["sort"] = resolved_sort.value
    if resolved_timeframe is not normalize_public_developer_leaderboard_timeframe(None):
        params["timeframe"] = resolved_timeframe.value
    if resolved_window_days != normalize_public_developer_activity_window_days(
        DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS
    ):
        params["window"] = str(resolved_window_days)

    if not params:
        return DEVELOPER_LEADERBOARD_ROUTE
    return f"{DEVELOPER_LEADERBOARD_ROUTE}?{urlencode(params)}"


def load_public_developer_leaderboard_snapshot(
    *,
    session: Session,
    sort: DeveloperLeaderboardSort | str | None = None,
    timeframe: DeveloperLeaderboardTimeframe | str | None = None,
    activity_window_days: int | str | None = None,
    limit: int | None = DEFAULT_PUBLIC_DEVELOPER_LEADERBOARD_LIMIT,
    now: datetime | None = None,
) -> PublicDeveloperLeaderboardSnapshot:
    """Load one leaderboard-ready public KPI snapshot collection."""
    resolved_sort = normalize_public_developer_leaderboard_sort(sort)
    resolved_timeframe = normalize_public_developer_leaderboard_timeframe(timeframe)
    resolved_window_days = normalize_public_developer_activity_window_days(activity_window_days)

    entries = tuple(
        list_developer_leaderboard(
            session=session,
            sort=resolved_sort,
            timeframe=resolved_timeframe,
            activity_window_days=resolved_window_days,
            limit=limit,
            now=now,
        )
    )
    return PublicDeveloperLeaderboardSnapshot(
        entries=entries,
        sort=resolved_sort,
        timeframe=resolved_timeframe,
        activity_window_days=resolved_window_days,
        activity_since=build_developer_activity_window_start(
            window_days=resolved_window_days,
            now=now,
        ),
    )


def load_public_developer_leaderboard_snapshot_safe(
    *,
    sort: DeveloperLeaderboardSort | str | None = None,
    timeframe: DeveloperLeaderboardTimeframe | str | None = None,
    activity_window_days: int | str | None = None,
    limit: int | None = DEFAULT_PUBLIC_DEVELOPER_LEADERBOARD_LIMIT,
    now: datetime | None = None,
) -> PublicDeveloperLeaderboardSnapshot:
    """Load the public leaderboard while tolerating a cold or unmigrated database."""
    resolved_sort = normalize_public_developer_leaderboard_sort(sort)
    resolved_timeframe = normalize_public_developer_leaderboard_timeframe(timeframe)
    resolved_window_days = normalize_public_developer_activity_window_days(activity_window_days)
    try:
        with session_scope() as session:
            return load_public_developer_leaderboard_snapshot(
                session=session,
                sort=resolved_sort,
                timeframe=resolved_timeframe,
                activity_window_days=resolved_window_days,
                limit=limit,
                now=now,
            )
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_public_developer_leaderboard_snapshot(
            sort=resolved_sort,
            timeframe=resolved_timeframe,
            activity_window_days=resolved_window_days,
            now=now,
        )


__all__ = [
    "DEFAULT_PUBLIC_DEVELOPER_LEADERBOARD_LIMIT",
    "PublicDeveloperLeaderboardSnapshot",
    "build_empty_public_developer_leaderboard_snapshot",
    "build_public_developer_leaderboard_path",
    "load_public_developer_leaderboard_snapshot",
    "load_public_developer_leaderboard_snapshot_safe",
    "normalize_public_developer_activity_window_days",
    "normalize_public_developer_leaderboard_sort",
    "normalize_public_developer_leaderboard_timeframe",
]
