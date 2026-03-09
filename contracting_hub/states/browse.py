"""Public browse-page state."""

from __future__ import annotations

from typing import Any, TypedDict

import reflex as rx

from contracting_hub.services import (
    ContractBrowseFilterOption,
    ContractBrowseSnapshot,
    ContractBrowseSummary,
    build_contract_browse_path,
    load_public_contract_browse_snapshot_safe,
)
from contracting_hub.utils import build_contract_rating_display, format_contract_calendar_date
from contracting_hub.utils.meta import BROWSE_ROUTE


class BrowseCardPayload(TypedDict):
    """Serialized browse-card content kept in state."""

    slug: str
    display_name: str
    contract_name: str
    short_summary: str
    featured: bool
    version_label: str
    author_name: str
    category_label: str
    updated_label: str
    published_label: str
    star_count: str
    rating_headline: str
    rating_detail: str
    rating_empty: bool
    tag_preview: list[str]


class BrowseFilterOptionPayload(TypedDict):
    """Serialized select option content kept in state."""

    value: str
    label: str
    count: str


class BrowseActiveFilterPayload(TypedDict):
    """Serialized active-filter badge content kept in state."""

    label: str
    value: str


class BrowsePaginationPayload(TypedDict):
    """Serialized pagination-link content kept in state."""

    label: str
    href: str
    is_current: bool


class BrowseState(rx.State):
    """URL-driven state for the public browse page."""

    search_query: str = ""
    selected_category: str = ""
    selected_tag: str = ""
    selected_sort: str = "featured"
    selected_sort_label: str = "Featured"
    current_page: int = 1
    total_pages: int = 1
    total_results: int = 0
    result_count_label: str = "0 contracts"
    result_window_label: str = "No contracts match the current browse state."
    empty_state_body: str = (
        "Try a different search term or clear one of the active filters to widen the catalog."
    )
    result_cards: list[BrowseCardPayload] = []
    category_options: list[BrowseFilterOptionPayload] = []
    tag_options: list[BrowseFilterOptionPayload] = []
    active_filters: list[BrowseActiveFilterPayload] = []
    previous_page_href: str = ""
    next_page_href: str = ""
    pagination_links: list[BrowsePaginationPayload] = []
    clear_filters_href: str = BROWSE_ROUTE

    @rx.var
    def has_results(self) -> bool:
        """Return whether the current browse state has visible contracts."""
        return bool(self.result_cards)

    @rx.var
    def has_active_filters(self) -> bool:
        """Return whether the current browse state has any active search filters."""
        return bool(self.active_filters)

    def load_page(self) -> None:
        """Load the browse snapshot from the current router query params."""
        params = self.router.page.params
        snapshot = load_public_contract_browse_snapshot_safe(
            query=params.get("query"),
            category_slug=params.get("category"),
            tag=params.get("tag"),
            sort=params.get("sort"),
            page=params.get("page"),
        )
        self._apply_snapshot(snapshot)

    def set_search_query(self, value: str) -> None:
        """Update the current search input value."""
        self.search_query = value

    def set_selected_category(self, value: str) -> None:
        """Update the selected category filter."""
        self.selected_category = value

    def set_selected_tag(self, value: str) -> None:
        """Update the selected tag filter."""
        self.selected_tag = value

    def set_selected_sort(self, value: str) -> None:
        """Update the selected sort control."""
        self.selected_sort = value

    def apply_filters(self, form_data: dict[str, Any]) -> rx.event.EventSpec:
        """Redirect to the canonical browse URL for the submitted filter form."""
        return rx.redirect(
            build_contract_browse_path(
                query=form_data.get("query"),
                category_slug=form_data.get("category"),
                tag=form_data.get("tag"),
                sort=form_data.get("sort"),
                page=1,
            )
        )

    def _apply_snapshot(self, snapshot: ContractBrowseSnapshot) -> None:
        self.search_query = snapshot.query
        self.selected_category = snapshot.category_slug or ""
        self.selected_tag = snapshot.tag or ""
        self.selected_sort = snapshot.sort.value
        self.selected_sort_label = _sort_label(snapshot.sort.value)
        self.current_page = snapshot.current_page
        self.total_pages = snapshot.total_pages
        self.total_results = snapshot.total_results
        self.result_count_label = _result_count_label(snapshot.total_results)
        self.result_window_label = _result_window_label(snapshot)
        self.empty_state_body = _empty_state_body(snapshot)
        self.result_cards = [_serialize_summary(summary) for summary in snapshot.results]
        self.category_options = [
            _serialize_filter_option(option) for option in snapshot.available_categories
        ]
        self.tag_options = [_serialize_filter_option(option) for option in snapshot.available_tags]
        self.active_filters = _serialize_active_filters(snapshot)
        self.clear_filters_href = BROWSE_ROUTE
        self.previous_page_href = (
            build_contract_browse_path(
                query=snapshot.query,
                category_slug=snapshot.category_slug,
                tag=snapshot.tag,
                sort=snapshot.sort,
                page=snapshot.current_page - 1,
            )
            if snapshot.current_page > 1
            else ""
        )
        self.next_page_href = (
            build_contract_browse_path(
                query=snapshot.query,
                category_slug=snapshot.category_slug,
                tag=snapshot.tag,
                sort=snapshot.sort,
                page=snapshot.current_page + 1,
            )
            if snapshot.current_page < snapshot.total_pages
            else ""
        )
        self.pagination_links = [
            {
                "label": str(page_number),
                "href": build_contract_browse_path(
                    query=snapshot.query,
                    category_slug=snapshot.category_slug,
                    tag=snapshot.tag,
                    sort=snapshot.sort,
                    page=page_number,
                ),
                "is_current": page_number == snapshot.current_page,
            }
            for page_number in _visible_page_numbers(snapshot.current_page, snapshot.total_pages)
        ]


def _serialize_summary(summary: ContractBrowseSummary) -> BrowseCardPayload:
    rating_display = build_contract_rating_display(
        average_rating=summary.average_rating,
        rating_count=summary.rating_count,
    )
    return {
        "slug": summary.slug,
        "display_name": summary.display_name,
        "contract_name": summary.contract_name,
        "short_summary": summary.short_summary,
        "featured": summary.featured,
        "version_label": summary.semantic_version or "No published version",
        "author_name": summary.author_name,
        "category_label": summary.primary_category_name,
        "updated_label": format_contract_calendar_date(summary.updated_at),
        "published_label": format_contract_calendar_date(summary.published_at),
        "star_count": str(summary.star_count),
        "rating_headline": rating_display.headline,
        "rating_detail": rating_display.detail,
        "rating_empty": rating_display.empty,
        "tag_preview": list(summary.tag_names[:4]),
    }


def _serialize_filter_option(option: ContractBrowseFilterOption) -> BrowseFilterOptionPayload:
    return {
        "value": option.value,
        "label": option.label,
        "count": str(option.count),
    }


def _serialize_active_filters(snapshot: ContractBrowseSnapshot) -> list[BrowseActiveFilterPayload]:
    category_labels = {option.value: option.label for option in snapshot.available_categories}
    tag_labels = {option.value: option.label for option in snapshot.available_tags}
    filters: list[BrowseActiveFilterPayload] = []
    if snapshot.query:
        filters.append({"label": "Search", "value": snapshot.query})
    if snapshot.category_slug is not None:
        filters.append(
            {
                "label": "Category",
                "value": category_labels.get(snapshot.category_slug, snapshot.category_slug),
            }
        )
    if snapshot.tag is not None:
        filters.append({"label": "Tag", "value": tag_labels.get(snapshot.tag, snapshot.tag)})
    return filters


def _result_count_label(total_results: int) -> str:
    return "1 contract" if total_results == 1 else f"{total_results} contracts"


def _result_window_label(snapshot: ContractBrowseSnapshot) -> str:
    if snapshot.total_results == 0:
        return "No contracts match the current browse state."

    first_result = (snapshot.current_page - 1) * snapshot.page_size + 1
    last_result = first_result + len(snapshot.results) - 1
    return f"Showing {first_result}-{last_result} of {snapshot.total_results}"


def _empty_state_body(snapshot: ContractBrowseSnapshot) -> str:
    if snapshot.query or snapshot.category_slug or snapshot.tag:
        return (
            "Try a different search term or clear one of the active filters to widen the catalog."
        )
    return "Publish more contracts to start populating this public catalog."


def _visible_page_numbers(current_page: int, total_pages: int) -> list[int]:
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, start_page + 4)
    start_page = max(1, end_page - 4)
    return list(range(start_page, end_page + 1))


def _sort_label(sort_value: str) -> str:
    if sort_value == "relevance":
        return "Best match"
    return sort_value.replace("_", " ").title()


__all__ = ["BrowseState"]
