from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone

import sqlalchemy as sa

from contracting_hub.services.developer_kpis import (
    DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS,
    DeveloperLeaderboardSort,
    DeveloperLeaderboardTimeframe,
    build_developer_activity_window_start,
)
from contracting_hub.services.developer_leaderboard import (
    PublicDeveloperLeaderboardSnapshot,
    build_empty_public_developer_leaderboard_snapshot,
    build_public_developer_leaderboard_path,
    load_public_developer_leaderboard_snapshot_safe,
    normalize_public_developer_activity_window_days,
    normalize_public_developer_leaderboard_sort,
    normalize_public_developer_leaderboard_timeframe,
)
from contracting_hub.utils.meta import DEVELOPER_LEADERBOARD_ROUTE


def test_public_leaderboard_normalizers_accept_valid_inputs_and_fall_back_for_invalid_values() -> (
    None
):
    assert (
        normalize_public_developer_leaderboard_sort(" weighted_rating ")
        is DeveloperLeaderboardSort.WEIGHTED_RATING
    )
    assert (
        normalize_public_developer_leaderboard_timeframe(" recent ")
        is DeveloperLeaderboardTimeframe.RECENT
    )
    assert normalize_public_developer_activity_window_days(" 90 ") == 90

    assert (
        normalize_public_developer_leaderboard_sort("bogus") is DeveloperLeaderboardSort.STAR_TOTAL
    )
    assert (
        normalize_public_developer_leaderboard_timeframe("bogus")
        is DeveloperLeaderboardTimeframe.ALL_TIME
    )
    assert (
        normalize_public_developer_activity_window_days("bogus")
        == DEFAULT_DEVELOPER_ACTIVITY_WINDOW_DAYS
    )


def test_build_empty_public_developer_leaderboard_snapshot_uses_normalized_state() -> None:
    now = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)

    snapshot = build_empty_public_developer_leaderboard_snapshot(
        sort="weighted_rating",
        timeframe="recent",
        activity_window_days="90",
        now=now,
    )

    assert snapshot.entries == ()
    assert snapshot.sort is DeveloperLeaderboardSort.WEIGHTED_RATING
    assert snapshot.timeframe is DeveloperLeaderboardTimeframe.RECENT
    assert snapshot.activity_window_days == 90
    assert snapshot.activity_since == build_developer_activity_window_start(
        window_days=90,
        now=now,
    )


def test_build_public_developer_leaderboard_path_omits_defaults_and_serializes_filters() -> None:
    assert build_public_developer_leaderboard_path() == DEVELOPER_LEADERBOARD_ROUTE
    assert (
        build_public_developer_leaderboard_path(
            sort="weighted_rating",
            timeframe="recent",
            activity_window_days="90",
        )
        == "/developers?sort=weighted_rating&timeframe=recent&window=90"
    )


def test_load_public_developer_leaderboard_snapshot_safe_returns_empty_on_db_failure(
    monkeypatch,
) -> None:
    class _BrokenSessionScope:
        def __enter__(self) -> None:
            raise sa.exc.OperationalError("SELECT 1", {}, RuntimeError("boom"))

        def __exit__(self, exc_type, exc, traceback) -> bool:
            return False

    monkeypatch.setattr(
        "contracting_hub.services.developer_leaderboard.session_scope",
        lambda: _BrokenSessionScope(),
    )

    snapshot = load_public_developer_leaderboard_snapshot_safe(
        sort="recent_activity",
        timeframe="recent",
        activity_window_days="90",
    )

    assert snapshot.entries == ()
    assert snapshot.sort is DeveloperLeaderboardSort.RECENT_ACTIVITY
    assert snapshot.timeframe is DeveloperLeaderboardTimeframe.RECENT
    assert snapshot.activity_window_days == 90


def test_load_public_developer_leaderboard_snapshot_safe_returns_loaded_snapshot_on_success(
    monkeypatch,
) -> None:
    expected_snapshot = build_empty_public_developer_leaderboard_snapshot(
        sort="contract_count",
        timeframe="recent",
        activity_window_days="180",
    )

    monkeypatch.setattr(
        "contracting_hub.services.developer_leaderboard.session_scope",
        lambda: nullcontext(object()),
    )
    monkeypatch.setattr(
        "contracting_hub.services.developer_leaderboard.load_public_developer_leaderboard_snapshot",
        lambda **_kwargs: expected_snapshot,
    )

    snapshot = load_public_developer_leaderboard_snapshot_safe(
        sort="contract_count",
        timeframe="recent",
        activity_window_days="180",
    )

    assert isinstance(snapshot, PublicDeveloperLeaderboardSnapshot)
    assert snapshot == expected_snapshot
