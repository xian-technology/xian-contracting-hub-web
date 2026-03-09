"""Public contract-detail page state."""

from __future__ import annotations

from typing import TypedDict

import reflex as rx

from contracting_hub.models import PublicationStatus
from contracting_hub.services import (
    ContractDetailSnapshot,
    load_public_contract_detail_snapshot_safe,
)
from contracting_hub.utils import build_contract_rating_display, format_contract_calendar_date
from contracting_hub.utils.meta import BROWSE_ROUTE


class AuthorLinkPayload(TypedDict):
    """Serialized public author link content stored in state."""

    label: str
    href: str


class ContractDetailState(rx.State):
    """Route-driven state for the public contract detail header."""

    load_state: str = "loading"
    contract_slug: str = ""
    display_name: str = ""
    contract_name: str = ""
    short_summary: str = ""
    long_description: str = ""
    header_context_label: str = ""
    contract_status_label: str = ""
    contract_status_color_scheme: str = "gray"
    version_label: str = ""
    version_status_label: str = ""
    version_status_color_scheme: str = "gray"
    published_label: str = "Pending"
    updated_label: str = "Pending"
    star_count: str = "0"
    rating_headline: str = "No ratings yet"
    rating_detail: str = ""
    rating_empty: bool = True
    author_name: str = "Curated entry"
    author_secondary: str = ""
    author_initials: str = "CE"
    author_bio: str = ""
    author_links: list[AuthorLinkPayload] = []
    primary_category_label: str = "Uncategorized"
    category_labels: list[str] = []
    tag_labels: list[str] = []
    featured: bool = False
    network_label: str = ""
    license_label: str = ""
    documentation_url: str = ""
    source_repository_url: str = ""
    browse_href: str = BROWSE_ROUTE

    @rx.var
    def is_loading(self) -> bool:
        """Return whether the current route is loading detail data."""
        return self.load_state == "loading"

    @rx.var
    def is_ready(self) -> bool:
        """Return whether the current route resolved a visible contract."""
        return self.load_state == "ready"

    @rx.var
    def is_missing(self) -> bool:
        """Return whether the current route resolved to no visible contract."""
        return self.load_state == "missing"

    @rx.var
    def has_author_secondary(self) -> bool:
        """Return whether the author panel has a secondary identity line."""
        return bool(self.author_secondary)

    @rx.var
    def has_author_bio(self) -> bool:
        """Return whether the author panel has public bio copy."""
        return bool(self.author_bio)

    @rx.var
    def has_author_links(self) -> bool:
        """Return whether the author panel has outbound links."""
        return bool(self.author_links)

    @rx.var
    def has_tags(self) -> bool:
        """Return whether the current contract has public tags."""
        return bool(self.tag_labels)

    @rx.var
    def has_network(self) -> bool:
        """Return whether the contract has a network badge."""
        return bool(self.network_label)

    @rx.var
    def has_license(self) -> bool:
        """Return whether the contract has a license badge."""
        return bool(self.license_label)

    @rx.var
    def has_documentation_url(self) -> bool:
        """Return whether the contract has public documentation metadata."""
        return bool(self.documentation_url)

    @rx.var
    def has_source_repository_url(self) -> bool:
        """Return whether the contract has a public source repository URL."""
        return bool(self.source_repository_url)

    def load_page(self) -> None:
        """Load one public contract snapshot from the current route params."""
        params = self.router.page.params
        snapshot = load_public_contract_detail_snapshot_safe(slug=params.get("slug"))
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: ContractDetailSnapshot) -> None:
        if not snapshot.found:
            self._apply_missing(snapshot.slug)
            return

        rating_display = build_contract_rating_display(
            average_rating=snapshot.average_rating,
            rating_count=snapshot.rating_count,
        )
        self.load_state = "ready"
        self.contract_slug = snapshot.slug or ""
        self.display_name = snapshot.display_name
        self.contract_name = snapshot.contract_name
        self.short_summary = snapshot.short_summary
        self.long_description = snapshot.long_description
        self.version_label = snapshot.selected_version or "No published version"
        self.version_status_label = _status_label(snapshot.selected_version_status)
        self.version_status_color_scheme = _status_color_scheme(snapshot.selected_version_status)
        self.published_label = format_contract_calendar_date(snapshot.selected_version_published_at)
        self.updated_label = format_contract_calendar_date(snapshot.updated_at)
        self.header_context_label = (
            f"Version {self.version_label} • Published {self.published_label} • "
            f"Updated {self.updated_label}"
        )
        self.contract_status_label = _status_label(snapshot.contract_status)
        self.contract_status_color_scheme = _status_color_scheme(snapshot.contract_status)
        self.star_count = str(snapshot.star_count)
        self.rating_headline = rating_display.headline
        self.rating_detail = rating_display.detail
        self.rating_empty = rating_display.empty
        self.author_name = snapshot.author.display_name
        self.author_secondary = (
            f"@{snapshot.author.username}" if snapshot.author.username else "Curated author"
        )
        self.author_initials = _author_initials(snapshot.author.display_name)
        self.author_bio = snapshot.author.bio or ""
        self.author_links = _serialize_author_links(snapshot)
        self.primary_category_label = snapshot.primary_category_name or "Uncategorized"
        self.category_labels = list(snapshot.category_names)
        self.tag_labels = list(snapshot.tag_names)
        self.featured = snapshot.featured
        self.network_label = (
            snapshot.network.value.replace("-", " ").title() if snapshot.network is not None else ""
        )
        self.license_label = snapshot.license_name or ""
        self.documentation_url = snapshot.documentation_url or ""
        self.source_repository_url = snapshot.source_repository_url or ""
        self.browse_href = BROWSE_ROUTE

    def _apply_missing(self, slug: str | None) -> None:
        self.load_state = "missing"
        self.contract_slug = slug or ""
        self.display_name = ""
        self.contract_name = ""
        self.short_summary = ""
        self.long_description = ""
        self.header_context_label = ""
        self.contract_status_label = ""
        self.contract_status_color_scheme = "gray"
        self.version_label = ""
        self.version_status_label = ""
        self.version_status_color_scheme = "gray"
        self.published_label = "Pending"
        self.updated_label = "Pending"
        self.star_count = "0"
        self.rating_headline = "No ratings yet"
        self.rating_detail = ""
        self.rating_empty = True
        self.author_name = "Curated entry"
        self.author_secondary = ""
        self.author_initials = "CE"
        self.author_bio = ""
        self.author_links = []
        self.primary_category_label = "Uncategorized"
        self.category_labels = []
        self.tag_labels = []
        self.featured = False
        self.network_label = ""
        self.license_label = ""
        self.documentation_url = ""
        self.source_repository_url = ""
        self.browse_href = BROWSE_ROUTE


def _serialize_author_links(snapshot: ContractDetailSnapshot) -> list[AuthorLinkPayload]:
    links: list[AuthorLinkPayload] = []
    if snapshot.author.website_url:
        links.append({"label": "Website", "href": snapshot.author.website_url})
    if snapshot.author.github_url:
        links.append({"label": "GitHub", "href": snapshot.author.github_url})
    if snapshot.author.xian_profile_url:
        links.append({"label": "Xian", "href": snapshot.author.xian_profile_url})
    return links


def _status_label(status: PublicationStatus | None) -> str:
    if status is None:
        return "Pending"
    return status.value.replace("_", " ").title()


def _status_color_scheme(status: PublicationStatus | None) -> str:
    if status is PublicationStatus.PUBLISHED:
        return "grass"
    if status in {PublicationStatus.DEPRECATED, PublicationStatus.ARCHIVED}:
        return "orange"
    if status is PublicationStatus.DRAFT:
        return "gray"
    return "gray"


def _author_initials(value: str) -> str:
    parts = [part[0].upper() for part in value.split() if part]
    if not parts:
        return "CE"
    return "".join(parts[:2])


__all__ = ["ContractDetailState"]
