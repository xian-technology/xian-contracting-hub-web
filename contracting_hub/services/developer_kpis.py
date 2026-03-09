"""Service helpers for developer KPI snapshots and leaderboards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from sqlmodel import Session

from contracting_hub.repositories import DeveloperKPIRecord, DeveloperKPIRepository

DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS = 30
MAX_DEVELOPER_ACTIVITY_WINDOW_DAYS = 365
DEFAULT_DEVELOPER_LEADERBOARD_LIMIT = 50


class DeveloperLeaderboardSort(StrEnum):
    """Supported leaderboard sort keys."""

    CONTRACT_COUNT = "contract_count"
    STAR_TOTAL = "star_total"
    WEIGHTED_RATING = "weighted_rating"
    DEPLOYMENT_COUNT = "deployment_count"
    RECENT_ACTIVITY = "recent_activity"


class DeveloperLeaderboardTimeframe(StrEnum):
    """Supported leaderboard timeframes."""

    ALL_TIME = "all_time"
    RECENT = "recent"


@dataclass(frozen=True)
class DeveloperKPIAggregate:
    """Public developer KPI snapshot for profile and leaderboard screens."""

    user_id: int
    username: str
    display_name: str | None
    avatar_path: str | None
    published_contract_count: int
    total_stars_received: int
    weighted_average_rating: float | None
    total_rating_count: int
    total_deployment_count: int
    recent_published_contract_count: int
    recent_publish_count: int
    recent_stars_received: int
    recent_weighted_average_rating: float | None
    recent_rating_count: int
    recent_deployment_count: int
    activity_window_days: int
    activity_since: datetime

    @property
    def recent_activity_count(self) -> int:
        """Return the combined recent activity total for the configured window."""
        return (
            self.recent_publish_count
            + self.recent_stars_received
            + self.recent_rating_count
            + self.recent_deployment_count
        )


class DeveloperKPIServiceErrorCode(StrEnum):
    """Stable developer-KPI service failures exposed to callers."""

    INVALID_ACTIVITY_WINDOW = "invalid_activity_window"
    INVALID_LIMIT = "invalid_limit"
    INVALID_OFFSET = "invalid_offset"
    INVALID_SORT = "invalid_sort"
    INVALID_TIMEFRAME = "invalid_timeframe"


class DeveloperKPIServiceError(ValueError):
    """Structured service error for developer-KPI workflows."""

    def __init__(
        self,
        code: DeveloperKPIServiceErrorCode,
        message: str,
        *,
        field: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.details = details or {}

    def as_payload(self) -> dict[str, object]:
        """Serialize the service failure for UI or API responses."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


def get_developer_kpi_snapshot(
    *,
    session: Session,
    username: str,
    activity_window_days: int | None = None,
    now: datetime | None = None,
) -> DeveloperKPIAggregate | None:
    """Return one developer KPI snapshot for the given profile username."""
    resolved_window_days = normalize_developer_activity_window_days(activity_window_days)
    activity_since = build_developer_activity_window_start(
        window_days=resolved_window_days,
        now=now,
    )
    normalized_username = username.strip().lower()
    if not normalized_username:
        return None

    repository = DeveloperKPIRepository(session)
    record = repository.get_developer_kpis_by_username(
        username=normalized_username,
        activity_since=activity_since,
    )
    if record is None:
        return None
    return _build_kpi_aggregate(
        record,
        activity_window_days=resolved_window_days,
        activity_since=activity_since,
    )


def list_developer_leaderboard(
    *,
    session: Session,
    sort: DeveloperLeaderboardSort | str | None = None,
    timeframe: DeveloperLeaderboardTimeframe | str | None = None,
    activity_window_days: int | None = None,
    limit: int | None = DEFAULT_DEVELOPER_LEADERBOARD_LIMIT,
    offset: int = 0,
    now: datetime | None = None,
) -> list[DeveloperKPIAggregate]:
    """Return leaderboard-ready developer KPI aggregates."""
    resolved_sort = normalize_developer_leaderboard_sort(sort)
    resolved_timeframe = normalize_developer_leaderboard_timeframe(timeframe)
    resolved_window_days = normalize_developer_activity_window_days(activity_window_days)
    resolved_limit = _normalize_leaderboard_limit(limit)
    resolved_offset = _normalize_leaderboard_offset(offset)
    activity_since = build_developer_activity_window_start(
        window_days=resolved_window_days,
        now=now,
    )

    repository = DeveloperKPIRepository(session)
    records = repository.list_developer_kpis(
        activity_since=activity_since,
        sort_by=resolved_sort.value,
        timeframe=resolved_timeframe.value,
        limit=resolved_limit,
        offset=resolved_offset,
    )
    return [
        _build_kpi_aggregate(
            record,
            activity_window_days=resolved_window_days,
            activity_since=activity_since,
        )
        for record in records
    ]


def normalize_developer_activity_window_days(window_days: int | None) -> int:
    """Validate and normalize the requested recent-activity window."""
    if window_days is None:
        return DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS
    if isinstance(window_days, bool) or not isinstance(window_days, int):
        raise DeveloperKPIServiceError(
            DeveloperKPIServiceErrorCode.INVALID_ACTIVITY_WINDOW,
            "Activity window must be an integer between 1 and 365 days.",
            field="activity_window_days",
            details={"min": 1, "max": MAX_DEVELOPER_ACTIVITY_WINDOW_DAYS},
        )
    if 1 <= window_days <= MAX_DEVELOPER_ACTIVITY_WINDOW_DAYS:
        return window_days
    raise DeveloperKPIServiceError(
        DeveloperKPIServiceErrorCode.INVALID_ACTIVITY_WINDOW,
        "Activity window must be an integer between 1 and 365 days.",
        field="activity_window_days",
        details={
            "window_days": window_days,
            "min": 1,
            "max": MAX_DEVELOPER_ACTIVITY_WINDOW_DAYS,
        },
    )


def build_developer_activity_window_start(
    *,
    window_days: int | None = None,
    now: datetime | None = None,
) -> datetime:
    """Return the inclusive UTC cutoff timestamp for recent developer activity."""
    resolved_window_days = normalize_developer_activity_window_days(window_days)
    return _coerce_utc_datetime(now or datetime.now(timezone.utc)) - timedelta(
        days=resolved_window_days
    )


def normalize_developer_leaderboard_sort(
    sort: DeveloperLeaderboardSort | str | None,
) -> DeveloperLeaderboardSort:
    """Normalize leaderboard sort input from UI or query params."""
    if sort is None:
        return DeveloperLeaderboardSort.STAR_TOTAL
    if isinstance(sort, DeveloperLeaderboardSort):
        return sort
    if isinstance(sort, str):
        normalized_sort = sort.strip().lower()
        try:
            return DeveloperLeaderboardSort(normalized_sort)
        except ValueError:
            pass
    raise DeveloperKPIServiceError(
        DeveloperKPIServiceErrorCode.INVALID_SORT,
        (
            "Leaderboard sort must be one of: contract_count, star_total, "
            "weighted_rating, deployment_count, recent_activity."
        ),
        field="sort",
        details={"value": sort},
    )


def normalize_developer_leaderboard_timeframe(
    timeframe: DeveloperLeaderboardTimeframe | str | None,
) -> DeveloperLeaderboardTimeframe:
    """Normalize leaderboard timeframe input from UI or query params."""
    if timeframe is None:
        return DeveloperLeaderboardTimeframe.ALL_TIME
    if isinstance(timeframe, DeveloperLeaderboardTimeframe):
        return timeframe
    if isinstance(timeframe, str):
        normalized_timeframe = timeframe.strip().lower()
        try:
            return DeveloperLeaderboardTimeframe(normalized_timeframe)
        except ValueError:
            pass
    raise DeveloperKPIServiceError(
        DeveloperKPIServiceErrorCode.INVALID_TIMEFRAME,
        "Leaderboard timeframe must be either all_time or recent.",
        field="timeframe",
        details={"value": timeframe},
    )


def _normalize_leaderboard_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise DeveloperKPIServiceError(
            DeveloperKPIServiceErrorCode.INVALID_LIMIT,
            "Leaderboard limit must be a positive integer.",
            field="limit",
            details={"value": limit},
        )
    return limit


def _normalize_leaderboard_offset(offset: int) -> int:
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise DeveloperKPIServiceError(
            DeveloperKPIServiceErrorCode.INVALID_OFFSET,
            "Leaderboard offset must be a non-negative integer.",
            field="offset",
            details={"value": offset},
        )
    return offset


def _build_kpi_aggregate(
    record: DeveloperKPIRecord,
    *,
    activity_window_days: int,
    activity_since: datetime,
) -> DeveloperKPIAggregate:
    return DeveloperKPIAggregate(
        user_id=record.user_id,
        username=record.username,
        display_name=record.display_name,
        avatar_path=record.avatar_path,
        published_contract_count=record.published_contract_count,
        total_stars_received=record.total_stars_received,
        weighted_average_rating=record.weighted_average_rating,
        total_rating_count=record.total_rating_count,
        total_deployment_count=record.total_deployment_count,
        recent_published_contract_count=record.recent_published_contract_count,
        recent_publish_count=record.recent_publish_count,
        recent_stars_received=record.recent_stars_received,
        recent_weighted_average_rating=record.recent_weighted_average_rating,
        recent_rating_count=record.recent_rating_count,
        recent_deployment_count=record.recent_deployment_count,
        activity_window_days=activity_window_days,
        activity_since=activity_since,
    )


def _coerce_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS",
    "DEFAULT_DEVELOPER_LEADERBOARD_LIMIT",
    "MAX_DEVELOPER_ACTIVITY_WINDOW_DAYS",
    "DeveloperKPIAggregate",
    "DeveloperKPIServiceError",
    "DeveloperKPIServiceErrorCode",
    "DeveloperLeaderboardSort",
    "DeveloperLeaderboardTimeframe",
    "build_developer_activity_window_start",
    "get_developer_kpi_snapshot",
    "list_developer_leaderboard",
    "normalize_developer_activity_window_days",
    "normalize_developer_leaderboard_sort",
    "normalize_developer_leaderboard_timeframe",
]
