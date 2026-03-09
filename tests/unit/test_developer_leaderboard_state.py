from __future__ import annotations

from datetime import datetime, timezone

from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.services.developer_kpis import (
    DeveloperKPIAggregate,
    DeveloperLeaderboardSort,
    DeveloperLeaderboardTimeframe,
)
from contracting_hub.services.developer_leaderboard import (
    PublicDeveloperLeaderboardSnapshot,
    build_empty_public_developer_leaderboard_snapshot,
)
from contracting_hub.states import DeveloperLeaderboardState


def _set_route_context(
    state: DeveloperLeaderboardState,
    path: str,
    *,
    params: dict[str, str] | None = None,
) -> None:
    router_data = {
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: "http://localhost:3000",
        constants.RouteVar.HEADERS: {"origin": "http://localhost:3000"},
        constants.RouteVar.QUERY: params or {},
    }
    object.__setattr__(state, "router_data", router_data)
    object.__setattr__(state, "router", RouterData.from_router_data(router_data))


def _build_state(
    path: str = "/developers",
    *,
    params: dict[str, str] | None = None,
) -> DeveloperLeaderboardState:
    state = DeveloperLeaderboardState(_reflex_internal_init=True)
    _set_route_context(state, path, params=params)
    return state


def _timestamp(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 12, 0, tzinfo=timezone.utc)


def test_load_page_populates_leaderboard_state_from_snapshot(monkeypatch) -> None:
    state = _build_state(
        params={
            "sort": "weighted_rating",
            "timeframe": "recent",
            "window": "90",
        }
    )
    snapshot = PublicDeveloperLeaderboardSnapshot(
        entries=(
            DeveloperKPIAggregate(
                user_id=1,
                username="alice",
                display_name="Alice Builder",
                avatar_path=None,
                published_contract_count=3,
                total_stars_received=12,
                weighted_average_rating=4.75,
                total_rating_count=6,
                total_deployment_count=8,
                recent_published_contract_count=2,
                recent_publish_count=3,
                recent_stars_received=5,
                recent_weighted_average_rating=4.5,
                recent_rating_count=4,
                recent_deployment_count=3,
                activity_window_days=90,
                activity_since=_timestamp(12, 9),
            ),
        ),
        sort=DeveloperLeaderboardSort.WEIGHTED_RATING,
        timeframe=DeveloperLeaderboardTimeframe.RECENT,
        activity_window_days=90,
        activity_since=_timestamp(12, 9),
    )

    monkeypatch.setattr(
        "contracting_hub.states.developer_leaderboard.load_public_developer_leaderboard_snapshot_safe",
        lambda **_kwargs: snapshot,
    )

    state.load_page()

    assert state.selected_sort == "weighted_rating"
    assert state.selected_sort_label == "Top rated"
    assert state.selected_timeframe == "recent"
    assert state.activity_window_label == "Last 90 days"
    assert state.developer_count_label == "1 developer"
    assert state.leaderboard_context == (
        "Showing 1 ranked developers sorted by top rated for the recent window view."
    )
    assert state.leaderboard_entries[0]["profile_href"] == "/developers/alice"
    assert state.leaderboard_entries[0]["contracts_label"] == "Recent contracts"
    assert state.leaderboard_entries[0]["deployments_value"] == "3"
    assert state.leaderboard_entries[0]["rating_empty"] is False
    assert state.leaderboard_entries[0]["recent_activity_breakdown"] == (
        "Last 90 days: 3 publishes • 5 stars • 4 ratings • 3 deploys"
    )


def test_state_defaults_cover_empty_leaderboard_branches() -> None:
    state = _build_state()

    assert state.has_entries is False
    assert "most starred" in state.page_intro
    assert "all time" in state.page_intro

    state._apply_snapshot(
        build_empty_public_developer_leaderboard_snapshot(
            sort="recent_activity",
            timeframe="recent",
            activity_window_days="180",
        )
    )

    assert state.has_entries is False
    assert state.selected_sort_label == "Recent activity"
    assert state.selected_timeframe_label == "Recent window"
    assert state.selected_window_days == "180"
    assert state.developer_count_label == "0 developers"
    assert state.leaderboard_context == (
        "Publish public contracts to start ranking developers on this board."
    )
