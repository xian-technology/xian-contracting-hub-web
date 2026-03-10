"""Public developer leaderboard page state."""

from __future__ import annotations

from typing import Any, TypedDict

import reflex as rx

from contracting_hub.services.developer_kpis import (
    DeveloperKPIAggregate,
    DeveloperLeaderboardTimeframe,
)
from contracting_hub.services.developer_leaderboard import (
    PublicDeveloperLeaderboardSnapshot,
    build_empty_public_developer_leaderboard_snapshot,
    build_public_developer_leaderboard_path,
    load_public_developer_leaderboard_snapshot_safe,
)
from contracting_hub.utils import build_contract_rating_display
from contracting_hub.utils.meta import (
    DEVELOPER_LEADERBOARD_ROUTE,
    build_developer_profile_path,
)

SORT_LABELS = {
    "contract_count": "Most contracts",
    "star_total": "Most starred",
    "weighted_rating": "Top rated",
    "deployment_count": "Most deployed",
    "recent_activity": "Recent activity",
}
TIMEFRAME_LABELS = {
    "all_time": "All time",
    "recent": "Recent window",
}


class DeveloperLeaderboardEntryPayload(TypedDict):
    """Serialized leaderboard-card content stored in state."""

    rank_label: str
    display_name: str
    username_label: str
    profile_href: str
    avatar_fallback: str
    contracts_label: str
    contracts_value: str
    stars_label: str
    stars_value: str
    deployments_label: str
    deployments_value: str
    rating_headline: str
    rating_detail: str
    rating_empty: bool
    recent_activity_value: str
    recent_activity_breakdown: str


class DeveloperLeaderboardState(rx.State):
    """URL-driven state for the public developer leaderboard page."""

    load_state: str = "loading"
    load_error_message: str = ""
    selected_sort: str = "star_total"
    selected_sort_label: str = "Most starred"
    selected_timeframe: str = "all_time"
    selected_timeframe_label: str = "All time"
    selected_window_days: str = "30"
    activity_window_label: str = "Last 30 days"
    leaderboard_entries: list[DeveloperLeaderboardEntryPayload] = []
    developer_count_label: str = "0 developers"
    leaderboard_context: str = "No public developers are ranked yet."
    clear_filters_href: str = DEVELOPER_LEADERBOARD_ROUTE

    @rx.var
    def has_entries(self) -> bool:
        """Return whether the current leaderboard includes ranked developers."""
        return bool(self.leaderboard_entries)

    @rx.var
    def is_loading(self) -> bool:
        """Return whether the current leaderboard route is loading KPI data."""
        return self.load_state == "loading"

    @rx.var
    def has_load_error(self) -> bool:
        """Return whether the leaderboard route failed to resolve cleanly."""
        return self.load_state == "error" and bool(self.load_error_message)

    @rx.var
    def page_intro(self) -> str:
        """Return the current intro copy for the public leaderboard."""
        return (
            f"Public author rankings ordered by {self.selected_sort_label.lower()} across "
            f"{self.selected_timeframe_label.lower()} published-contract signals. "
            f"Recent activity metrics use the {self.activity_window_label.lower()} window."
        )

    def load_page(self) -> None:
        """Load the leaderboard snapshot from the current router query params."""
        params = self.router.page.params
        self.load_state = "loading"
        self.load_error_message = ""
        try:
            snapshot = load_public_developer_leaderboard_snapshot_safe(
                sort=params.get("sort"),
                timeframe=params.get("timeframe"),
                activity_window_days=params.get("window"),
            )
        except Exception as error:
            snapshot = build_empty_public_developer_leaderboard_snapshot(
                sort=params.get("sort"),
                timeframe=params.get("timeframe"),
                activity_window_days=params.get("window"),
            )
            self._apply_snapshot(snapshot)
            self.load_error_message = str(error)
            self.load_state = "error"
            return

        self._apply_snapshot(snapshot)
        self.load_state = "ready"

    def set_selected_sort(self, value: str) -> None:
        """Update the current leaderboard sort control."""
        self.selected_sort = value

    def set_selected_timeframe(self, value: str) -> None:
        """Update the current leaderboard timeframe control."""
        self.selected_timeframe = value

    def set_selected_window_days(self, value: str) -> None:
        """Update the current activity-window control."""
        self.selected_window_days = value

    def apply_filters(self, form_data: dict[str, Any]) -> rx.event.EventSpec:
        """Redirect to the canonical leaderboard URL for the submitted filters."""
        return rx.redirect(
            build_public_developer_leaderboard_path(
                sort=form_data.get("sort"),
                timeframe=form_data.get("timeframe"),
                activity_window_days=form_data.get("window"),
            )
        )

    def _apply_snapshot(self, snapshot: PublicDeveloperLeaderboardSnapshot) -> None:
        self.selected_sort = snapshot.sort.value
        self.selected_sort_label = _sort_label(snapshot.sort.value)
        self.selected_timeframe = snapshot.timeframe.value
        self.selected_timeframe_label = _timeframe_label(snapshot.timeframe.value)
        self.selected_window_days = str(snapshot.activity_window_days)
        self.activity_window_label = _format_activity_window_label(snapshot.activity_window_days)
        self.leaderboard_entries = [
            _serialize_entry(
                entry,
                rank=index + 1,
                timeframe=snapshot.timeframe,
            )
            for index, entry in enumerate(snapshot.entries)
        ]
        self.developer_count_label = _developer_count_label(len(snapshot.entries))
        self.leaderboard_context = _leaderboard_context(snapshot)
        self.clear_filters_href = DEVELOPER_LEADERBOARD_ROUTE


def _serialize_entry(
    entry: DeveloperKPIAggregate,
    *,
    rank: int,
    timeframe: DeveloperLeaderboardTimeframe,
) -> DeveloperLeaderboardEntryPayload:
    if timeframe is DeveloperLeaderboardTimeframe.RECENT:
        contracts_label = "Recent contracts"
        contracts_value = str(entry.recent_published_contract_count)
        stars_label = "Recent stars"
        stars_value = str(entry.recent_stars_received)
        deployments_label = "Recent deploys"
        deployments_value = str(entry.recent_deployment_count)
        average_rating = entry.recent_weighted_average_rating
        rating_count = entry.recent_rating_count
    else:
        contracts_label = "Published contracts"
        contracts_value = str(entry.published_contract_count)
        stars_label = "Total stars"
        stars_value = str(entry.total_stars_received)
        deployments_label = "Deployments"
        deployments_value = str(entry.total_deployment_count)
        average_rating = entry.weighted_average_rating
        rating_count = entry.total_rating_count

    rating_display = build_contract_rating_display(
        average_rating=average_rating,
        rating_count=rating_count,
    )
    return {
        "rank_label": f"#{rank}",
        "display_name": entry.display_name or entry.username,
        "username_label": f"@{entry.username}",
        "profile_href": build_developer_profile_path(entry.username),
        "avatar_fallback": _avatar_fallback(entry),
        "contracts_label": contracts_label,
        "contracts_value": contracts_value,
        "stars_label": stars_label,
        "stars_value": stars_value,
        "deployments_label": deployments_label,
        "deployments_value": deployments_value,
        "rating_headline": rating_display.headline,
        "rating_detail": rating_display.detail,
        "rating_empty": rating_display.empty,
        "recent_activity_value": str(entry.recent_activity_count),
        "recent_activity_breakdown": _recent_activity_breakdown(entry),
    }


def _avatar_fallback(entry: DeveloperKPIAggregate) -> str:
    source = entry.display_name or entry.username
    initials = [segment[0] for segment in source.replace("@", " ").split() if segment]
    if not initials:
        return "DL"
    return "".join(initials[:2]).upper()


def _recent_activity_breakdown(entry: DeveloperKPIAggregate) -> str:
    return (
        f"Last {entry.activity_window_days} days: {entry.recent_publish_count} publishes • "
        f"{entry.recent_stars_received} stars • {entry.recent_rating_count} ratings • "
        f"{entry.recent_deployment_count} deploys"
    )


def _sort_label(sort_value: str) -> str:
    return SORT_LABELS.get(sort_value, sort_value.replace("_", " ").title())


def _timeframe_label(timeframe_value: str) -> str:
    return TIMEFRAME_LABELS.get(timeframe_value, timeframe_value.replace("_", " ").title())


def _format_activity_window_label(activity_window_days: int) -> str:
    return f"Last {activity_window_days} days"


def _developer_count_label(developer_count: int) -> str:
    return "1 developer" if developer_count == 1 else f"{developer_count} developers"


def _leaderboard_context(snapshot: PublicDeveloperLeaderboardSnapshot) -> str:
    if not snapshot.entries:
        return "Publish public contracts to start ranking developers on this board."

    timeframe_label = _timeframe_label(snapshot.timeframe.value).lower()
    sort_label = _sort_label(snapshot.sort.value).lower()
    return (
        f"Showing {len(snapshot.entries)} ranked developers sorted by {sort_label} "
        f"for the {timeframe_label} view."
    )


__all__ = ["DeveloperLeaderboardState"]
