from datetime import datetime, timezone

import pytest

from contracting_hub.services.developer_kpis import (
    DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS,
    DeveloperKPIAggregate,
    DeveloperKPIServiceError,
    DeveloperKPIServiceErrorCode,
    DeveloperLeaderboardSort,
    DeveloperLeaderboardTimeframe,
    build_developer_activity_window_start,
    normalize_developer_activity_window_days,
    normalize_developer_leaderboard_sort,
    normalize_developer_leaderboard_timeframe,
)


def test_normalize_developer_activity_window_days_defaults_to_30_days() -> None:
    assert normalize_developer_activity_window_days(None) == DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS


@pytest.mark.parametrize("window_days", [1, 30, 365])
def test_normalize_developer_activity_window_days_accepts_valid_values(
    window_days: int,
) -> None:
    assert normalize_developer_activity_window_days(window_days) == window_days


@pytest.mark.parametrize("window_days", [0, -1, 366, "30", False])
def test_normalize_developer_activity_window_days_rejects_invalid_values(
    window_days: object,
) -> None:
    with pytest.raises(DeveloperKPIServiceError) as error:
        normalize_developer_activity_window_days(window_days)  # type: ignore[arg-type]

    assert error.value.code is DeveloperKPIServiceErrorCode.INVALID_ACTIVITY_WINDOW
    assert error.value.field == "activity_window_days"


def test_build_developer_activity_window_start_coerces_naive_datetimes_to_utc() -> None:
    now = datetime(2026, 3, 9, 12, 0, 0)

    cutoff = build_developer_activity_window_start(window_days=7, now=now)

    assert cutoff == datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)


def test_normalize_developer_leaderboard_sort_accepts_strings_and_defaults() -> None:
    assert normalize_developer_leaderboard_sort(None) is DeveloperLeaderboardSort.STAR_TOTAL
    assert (
        normalize_developer_leaderboard_sort(" weighted_rating ")
        is DeveloperLeaderboardSort.WEIGHTED_RATING
    )


def test_normalize_developer_leaderboard_timeframe_accepts_strings_and_defaults() -> None:
    assert normalize_developer_leaderboard_timeframe(None) is DeveloperLeaderboardTimeframe.ALL_TIME
    assert (
        normalize_developer_leaderboard_timeframe(" recent ")
        is DeveloperLeaderboardTimeframe.RECENT
    )


def test_developer_kpi_aggregate_recent_activity_count_sums_recent_metrics() -> None:
    aggregate = DeveloperKPIAggregate(
        user_id=1,
        username="alice",
        display_name="Alice",
        avatar_path=None,
        published_contract_count=2,
        total_stars_received=8,
        weighted_average_rating=4.25,
        total_rating_count=4,
        total_deployment_count=3,
        recent_published_contract_count=1,
        recent_publish_count=2,
        recent_stars_received=3,
        recent_weighted_average_rating=4.5,
        recent_rating_count=2,
        recent_deployment_count=4,
        activity_window_days=30,
        activity_since=datetime(2026, 2, 8, 12, 0, tzinfo=timezone.utc),
    )

    assert aggregate.recent_activity_count == 11


def test_developer_kpi_service_error_serializes_stable_payload() -> None:
    error = DeveloperKPIServiceError(
        DeveloperKPIServiceErrorCode.INVALID_SORT,
        "Leaderboard sort must be valid.",
        field="sort",
        details={"value": "bogus"},
    )

    assert error.as_payload() == {
        "code": "invalid_sort",
        "field": "sort",
        "message": "Leaderboard sort must be valid.",
        "details": {"value": "bogus"},
    }
