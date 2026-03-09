"""Public developer-profile page state."""

from __future__ import annotations

from typing import TypedDict

import reflex as rx

from contracting_hub.services.developer_profiles import (
    PublicDeveloperContractSummary,
    PublicDeveloperProfileSnapshot,
    load_public_developer_profile_snapshot_safe,
)
from contracting_hub.utils import build_contract_rating_display, format_contract_calendar_date
from contracting_hub.utils.meta import BROWSE_ROUTE, build_contract_detail_path


class DeveloperProfileLinkPayload(TypedDict):
    """Serialized public developer-link content stored in state."""

    label: str
    href: str


class DeveloperProfileContractPayload(TypedDict):
    """Serialized authored-contract content rendered on the public profile page."""

    slug: str
    detail_href: str
    display_name: str
    contract_name: str
    short_summary: str
    featured: bool
    status_label: str
    status_is_published: bool
    category_label: str
    updated_context: str
    version_label: str
    star_count: str
    rating_headline: str
    rating_detail: str
    rating_empty: bool
    deployment_count: str
    tag_preview: list[str]


class DeveloperProfileState(rx.State):
    """Route-driven state for the public developer profile page."""

    load_state: str = "loading"
    developer_username: str = ""
    display_name: str = "Developer profile"
    bio: str = ""
    avatar_storage_key: str = ""
    profile_links: list[DeveloperProfileLinkPayload] = []
    published_contract_count_text: str = "0"
    star_total_text: str = "0"
    rating_headline: str = "No ratings yet"
    rating_detail: str = ""
    rating_empty: bool = True
    deployment_count_text: str = "0"
    recent_activity_count_text: str = "0"
    recent_activity_breakdown: str = "0 publishes • 0 stars • 0 ratings • 0 deploys"
    activity_window_label: str = "Last 30 days"
    authored_contract_count_label: str = "0 public contracts"
    authored_contracts: list[DeveloperProfileContractPayload] = []
    browse_href: str = BROWSE_ROUTE

    @rx.var
    def is_loading(self) -> bool:
        """Return whether the current route is still resolving profile data."""
        return self.load_state == "loading"

    @rx.var
    def is_ready(self) -> bool:
        """Return whether the current route resolved a public developer profile."""
        return self.load_state == "ready"

    @rx.var
    def is_missing(self) -> bool:
        """Return whether the current route did not match a public developer profile."""
        return self.load_state == "missing"

    @rx.var
    def has_bio(self) -> bool:
        """Return whether the current public profile exposes bio copy."""
        return bool(self.bio)

    @rx.var
    def has_profile_links(self) -> bool:
        """Return whether the current public profile exposes outbound links."""
        return bool(self.profile_links)

    @rx.var
    def has_authored_contracts(self) -> bool:
        """Return whether the current public profile has authored-contract cards to render."""
        return bool(self.authored_contracts)

    @rx.var
    def page_title(self) -> str:
        """Return the current shell title for the public profile route."""
        if self.display_name and self.display_name != "Developer profile":
            return self.display_name
        if self.developer_username:
            return f"@{self.developer_username}"
        return "Developer profile"

    @rx.var
    def page_intro(self) -> str:
        """Return the current shell intro copy for the public profile route."""
        if self.is_missing:
            return "This developer profile is not available on the public catalog."
        if self.bio:
            return self.bio
        return (
            "Published authorship signals, deployment history, and public contract releases "
            "for this Xian developer."
        )

    @rx.var
    def profile_secondary(self) -> str:
        """Return the compact secondary identity line shown beside the display name."""
        if self.developer_username:
            return f"@{self.developer_username}"
        return "Public developer"

    @rx.var
    def avatar_fallback(self) -> str:
        """Return initials used by the public profile avatar placeholder."""
        source = (
            self.display_name
            if self.display_name != "Developer profile"
            else self.profile_secondary
        )
        initials = [segment[0] for segment in source.replace("@", " ").split() if segment]
        if not initials:
            return "DP"
        return "".join(initials[:2]).upper()

    def load_page(self) -> None:
        """Load the public developer profile snapshot from the current route params."""
        self.load_state = "loading"
        params = self.router.page.params
        snapshot = load_public_developer_profile_snapshot_safe(username=params.get("username"))
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: PublicDeveloperProfileSnapshot) -> None:
        if not snapshot.found:
            self._apply_missing(snapshot)
            return

        rating_display = build_contract_rating_display(
            average_rating=snapshot.weighted_average_rating,
            rating_count=snapshot.total_rating_count,
        )
        self.load_state = "ready"
        self.developer_username = snapshot.username or ""
        self.display_name = snapshot.display_name
        self.bio = snapshot.bio or ""
        self.avatar_storage_key = snapshot.avatar_path or ""
        self.profile_links = _serialize_profile_links(snapshot)
        self.published_contract_count_text = str(snapshot.published_contract_count)
        self.star_total_text = str(snapshot.total_stars_received)
        self.rating_headline = rating_display.headline
        self.rating_detail = rating_display.detail
        self.rating_empty = rating_display.empty
        self.deployment_count_text = str(snapshot.total_deployment_count)
        self.recent_activity_count_text = str(snapshot.recent_activity_count)
        self.recent_activity_breakdown = _format_recent_activity_breakdown(snapshot)
        self.activity_window_label = _format_activity_window_label(snapshot.activity_window_days)
        self.authored_contract_count_label = _format_public_contract_count_label(
            len(snapshot.authored_contracts)
        )
        self.authored_contracts = _serialize_authored_contracts(snapshot.authored_contracts)
        self.browse_href = BROWSE_ROUTE

    def _apply_missing(self, snapshot: PublicDeveloperProfileSnapshot) -> None:
        self.load_state = "missing"
        self.developer_username = snapshot.username or ""
        self.display_name = "Developer profile"
        self.bio = ""
        self.avatar_storage_key = ""
        self.profile_links = []
        self.published_contract_count_text = "0"
        self.star_total_text = "0"
        self.rating_headline = "No ratings yet"
        self.rating_detail = ""
        self.rating_empty = True
        self.deployment_count_text = "0"
        self.recent_activity_count_text = "0"
        self.recent_activity_breakdown = "0 publishes • 0 stars • 0 ratings • 0 deploys"
        self.activity_window_label = _format_activity_window_label(snapshot.activity_window_days)
        self.authored_contract_count_label = "0 public contracts"
        self.authored_contracts = []
        self.browse_href = BROWSE_ROUTE


def _serialize_profile_links(
    snapshot: PublicDeveloperProfileSnapshot,
) -> list[DeveloperProfileLinkPayload]:
    links: list[DeveloperProfileLinkPayload] = []
    if snapshot.website_url:
        links.append({"label": "Website", "href": snapshot.website_url})
    if snapshot.github_url:
        links.append({"label": "GitHub", "href": snapshot.github_url})
    if snapshot.xian_profile_url:
        links.append({"label": "Xian", "href": snapshot.xian_profile_url})
    return links


def _serialize_authored_contracts(
    contracts: tuple[PublicDeveloperContractSummary, ...],
) -> list[DeveloperProfileContractPayload]:
    payload: list[DeveloperProfileContractPayload] = []
    for contract in contracts:
        rating_display = build_contract_rating_display(
            average_rating=contract.average_rating,
            rating_count=contract.rating_count,
        )
        payload.append(
            {
                "slug": contract.slug,
                "detail_href": build_contract_detail_path(contract.slug),
                "display_name": contract.display_name,
                "contract_name": contract.contract_name,
                "short_summary": contract.short_summary,
                "featured": contract.featured,
                "status_label": contract.status.value.replace("_", " ").title(),
                "status_is_published": contract.status.value == "published",
                "category_label": contract.primary_category_name or "Uncategorized",
                "updated_context": f"Updated {format_contract_calendar_date(contract.updated_at)}",
                "version_label": contract.semantic_version or "No public version",
                "star_count": str(contract.star_count),
                "rating_headline": rating_display.headline,
                "rating_detail": rating_display.detail,
                "rating_empty": rating_display.empty,
                "deployment_count": str(contract.deployment_count),
                "tag_preview": list(contract.tag_names[:4]),
            }
        )
    return payload


def _format_recent_activity_breakdown(snapshot: PublicDeveloperProfileSnapshot) -> str:
    return (
        f"{snapshot.recent_publish_count} publishes • "
        f"{snapshot.recent_stars_received} stars • "
        f"{snapshot.recent_rating_count} ratings • "
        f"{snapshot.recent_deployment_count} deploys"
    )


def _format_activity_window_label(activity_window_days: int) -> str:
    return f"Last {activity_window_days} days"


def _format_public_contract_count_label(contract_count: int) -> str:
    return "1 public contract" if contract_count == 1 else f"{contract_count} public contracts"


__all__ = ["DeveloperProfileState"]
