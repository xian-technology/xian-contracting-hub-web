"""Public browse page for contract discovery."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import (
    ContractCardMetric,
    app_shell,
    contract_card,
    contract_metadata_badge,
    contract_rating_summary,
    page_error_state,
    page_loading_state,
    page_section,
)
from contracting_hub.states import AuthState, BrowseState
from contracting_hub.utils.meta import BROWSE_ROUTE

ROUTE = BROWSE_ROUTE
ON_LOAD = [AuthState.sync_auth_state, BrowseState.load_page]

SORT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("relevance", "Best match"),
    ("featured", "Featured"),
    ("newest", "Newest"),
    ("recently_updated", "Recently updated"),
    ("most_starred", "Most starred"),
    ("top_rated", "Top rated"),
    ("alphabetical", "Alphabetical"),
)


def _filter_field(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(
            label,
            font_size="0.78rem",
            font_weight="600",
            text_transform="uppercase",
            letter_spacing="0.08em",
            color="var(--hub-color-text-muted)",
        ),
        control,
        align="start",
        gap="var(--hub-space-2)",
        width="100%",
    )


def _browse_filters() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.vstack(
                rx.badge(
                    "Browse Controls",
                    radius="full",
                    variant="soft",
                    color_scheme="bronze",
                    width="fit-content",
                ),
                rx.heading(
                    "Find the right contract quickly.",
                    size="5",
                    font_family="var(--hub-font-display)",
                    letter_spacing="-0.05em",
                    color="var(--hub-color-text)",
                ),
                rx.text(
                    (
                        "Search across contract names, descriptions, authors, tags, "
                        "and categories, then narrow the catalog with lightweight filters."
                    ),
                    color="var(--hub-color-text-muted)",
                ),
                align="start",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.form(
                rx.vstack(
                    _filter_field(
                        "Search",
                        rx.input(
                            name="query",
                            value=BrowseState.search_query,
                            on_change=BrowseState.set_search_query,
                            placeholder="Search by name, author, tag, or category",
                            size="3",
                            variant="surface",
                            width="100%",
                        ),
                    ),
                    _filter_field(
                        "Category",
                        rx.el.select(
                            rx.el.option("All categories", value=""),
                            rx.foreach(
                                BrowseState.category_options,
                                lambda option: rx.el.option(
                                    option["label"],
                                    " (",
                                    option["count"],
                                    ")",
                                    value=option["value"],
                                ),
                            ),
                            name="category",
                            value=BrowseState.selected_category,
                            on_change=BrowseState.set_selected_category,
                            style=_select_style(),
                        ),
                    ),
                    _filter_field(
                        "Tag",
                        rx.el.select(
                            rx.el.option("All tags", value=""),
                            rx.foreach(
                                BrowseState.tag_options,
                                lambda option: rx.el.option(
                                    option["label"],
                                    " (",
                                    option["count"],
                                    ")",
                                    value=option["value"],
                                ),
                            ),
                            name="tag",
                            value=BrowseState.selected_tag,
                            on_change=BrowseState.set_selected_tag,
                            style=_select_style(),
                        ),
                    ),
                    _filter_field(
                        "Sort",
                        rx.el.select(
                            *[rx.el.option(label, value=value) for value, label in SORT_OPTIONS],
                            name="sort",
                            value=BrowseState.selected_sort,
                            on_change=BrowseState.set_selected_sort,
                            style=_select_style(),
                        ),
                    ),
                    rx.flex(
                        rx.button(
                            "Apply filters",
                            type="submit",
                            size="3",
                            variant="solid",
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                        rx.link(
                            rx.button(
                                "Clear",
                                type="button",
                                size="3",
                                variant="soft",
                                width=rx.breakpoints(initial="100%", sm="auto"),
                            ),
                            href=BrowseState.clear_filters_href,
                            text_decoration="none",
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                        direction=rx.breakpoints(initial="column", sm="row"),
                        width="100%",
                        gap="var(--hub-space-3)",
                    ),
                    align="start",
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                on_submit=BrowseState.apply_filters,
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        custom_attrs={"data-testid": "browse-filters"},
        position=rx.breakpoints(initial="static", lg="sticky"),
        top=rx.breakpoints(initial="0", lg="5.75rem"),
    )


def _select_style() -> dict[str, str]:
    return {
        "width": "100%",
        "padding": "0.85rem 1rem",
        "border": "1px solid var(--hub-color-line)",
        "border_radius": "var(--hub-radius-md)",
        "background": "rgba(255, 252, 246, 0.98)",
        "color": "var(--hub-color-text)",
        "font_family": "var(--hub-font-body)",
        "font_size": "0.98rem",
        "outline": "none",
        "box_shadow": "inset 0 1px 0 rgba(255, 255, 255, 0.75)",
    }


def _summary_chip(label: str, value) -> rx.Component:
    value_component = (
        value
        if isinstance(value, rx.Component)
        else rx.text(
            value,
            font_size="0.96rem",
            font_weight="600",
            color="var(--hub-color-text)",
        )
    )
    return rx.box(
        rx.text(
            label,
            font_size="0.72rem",
            text_transform="uppercase",
            letter_spacing="0.08em",
            color="var(--hub-color-text-muted)",
        ),
        value_component,
        padding="0.85rem 1rem",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 249, 239, 0.82)",
    )


def _active_filter_badge(filter_item) -> rx.Component:
    return rx.badge(
        filter_item["label"],
        ": ",
        filter_item["value"],
        radius="full",
        variant="soft",
        color_scheme="gray",
        padding_x="0.8rem",
        padding_y="0.35rem",
    )


def _browse_result_card(card) -> rx.Component:
    return contract_card(
        badges=rx.flex(
            contract_metadata_badge(card["category_label"], tone="category"),
            rx.cond(
                card["featured"],
                contract_metadata_badge("Featured", tone="featured"),
            ),
            wrap="wrap",
            gap="var(--hub-space-2)",
        ),
        context_label=card["updated_label"],
        display_name=card["display_name"],
        contract_name=card["contract_name"],
        short_summary=card["short_summary"],
        metrics=(
            ContractCardMetric("Version", card["version_label"]),
            ContractCardMetric("Stars", card["star_count"]),
            ContractCardMetric(
                "Rating",
                contract_rating_summary(
                    headline=card["rating_headline"],
                    detail=card["rating_detail"],
                    empty=card["rating_empty"],
                ),
            ),
        ),
        author_name=card["author_name"],
        tags=rx.flex(
            rx.foreach(
                card["tag_preview"],
                lambda tag: contract_metadata_badge(tag, tone="neutral"),
            ),
            wrap="wrap",
            gap="var(--hub-space-2)",
        ),
        metric_columns=rx.breakpoints(initial="1", sm="3"),
        href=card["detail_href"],
        custom_attrs={"data-testid": "browse-result-card"},
    )


def _results_empty_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "No contracts found",
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                BrowseState.empty_state_body,
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            rx.link(
                "Reset the browse view",
                href=BrowseState.clear_filters_href,
                color="var(--hub-color-accent-strong)",
                text_decoration="underline",
            ),
            align="start",
            gap="var(--hub-space-3)",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px dashed var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.68)",
    )


def _pagination_link(page_link) -> rx.Component:
    return rx.cond(
        page_link["is_current"],
        rx.box(
            page_link["label"],
            min_width="2.5rem",
            padding="0.65rem 0.85rem",
            border="1px solid var(--hub-color-accent)",
            border_radius="var(--hub-radius-pill)",
            background="var(--hub-color-accent-soft)",
            color="var(--hub-color-accent-strong)",
            font_weight="600",
            text_align="center",
        ),
        rx.link(
            rx.box(
                page_link["label"],
                min_width="2.5rem",
                padding="0.65rem 0.85rem",
                border="1px solid var(--hub-color-line)",
                border_radius="var(--hub-radius-pill)",
                background="rgba(255, 252, 246, 0.9)",
                color="var(--hub-color-text)",
                text_align="center",
            ),
            href=page_link["href"],
            text_decoration="none",
        ),
    )


def _pagination_controls() -> rx.Component:
    return rx.flex(
        rx.cond(
            BrowseState.previous_page_href != "",
            rx.link(
                rx.button("Previous", variant="soft", size="2"),
                href=BrowseState.previous_page_href,
                text_decoration="none",
            ),
            rx.button("Previous", variant="soft", size="2", disabled=True),
        ),
        rx.flex(
            rx.foreach(BrowseState.pagination_links, _pagination_link),
            wrap="wrap",
            gap="var(--hub-space-2)",
            justify="center",
        ),
        rx.cond(
            BrowseState.next_page_href != "",
            rx.link(
                rx.button("Next", variant="soft", size="2"),
                href=BrowseState.next_page_href,
                text_decoration="none",
            ),
            rx.button("Next", variant="soft", size="2", disabled=True),
        ),
        direction=rx.breakpoints(initial="column", md="row"),
        align="center",
        justify="between",
        gap="var(--hub-space-4)",
        width="100%",
    )


def _browse_results() -> rx.Component:
    return rx.box(
        rx.cond(
            BrowseState.is_loading,
            page_loading_state(
                title="Loading catalog results",
                body="Refreshing public contract results and active filter summaries.",
                test_id="browse-results-loading",
            ),
            rx.cond(
                BrowseState.has_load_error,
                page_error_state(
                    title="Browse results could not be loaded",
                    body=BrowseState.load_error_message,
                    test_id="browse-results-error",
                    action=rx.link(
                        rx.button("Reset browse view", size="3", variant="soft"),
                        href=BrowseState.clear_filters_href,
                        text_decoration="none",
                    ),
                ),
                page_section(
                    rx.vstack(
                        rx.flex(
                            rx.vstack(
                                rx.badge(
                                    "Public Catalog",
                                    radius="full",
                                    variant="soft",
                                    color_scheme="bronze",
                                    width="fit-content",
                                ),
                                rx.heading(
                                    BrowseState.result_count_label,
                                    size="6",
                                    font_family="var(--hub-font-display)",
                                    letter_spacing="-0.05em",
                                    color="var(--hub-color-text)",
                                ),
                                rx.text(
                                    BrowseState.result_window_label,
                                    color="var(--hub-color-text-muted)",
                                ),
                                align="start",
                                gap="var(--hub-space-3)",
                                width="100%",
                            ),
                            rx.grid(
                                _summary_chip(
                                    "Page",
                                    rx.text(BrowseState.current_page, "/", BrowseState.total_pages),
                                ),
                                _summary_chip("Sort", BrowseState.selected_sort_label),
                                columns=rx.breakpoints(initial="1", sm="2"),
                                gap="var(--hub-space-3)",
                                width=rx.breakpoints(initial="100%", md="auto"),
                            ),
                            direction=rx.breakpoints(initial="column", xl="row"),
                            align=rx.breakpoints(initial="start", xl="center"),
                            justify="between",
                            gap="var(--hub-space-4)",
                            width="100%",
                        ),
                        rx.cond(
                            BrowseState.has_active_filters,
                            rx.flex(
                                rx.foreach(BrowseState.active_filters, _active_filter_badge),
                                wrap="wrap",
                                gap="var(--hub-space-2)",
                                width="100%",
                            ),
                        ),
                        rx.cond(
                            BrowseState.has_results,
                            rx.vstack(
                                rx.foreach(BrowseState.result_cards, _browse_result_card),
                                _pagination_controls(),
                                width="100%",
                                gap="var(--hub-space-4)",
                            ),
                            _results_empty_state(),
                        ),
                        align="start",
                        gap="var(--hub-space-5)",
                        width="100%",
                    ),
                    custom_attrs={"data-testid": "browse-results"},
                ),
            ),
        ),
        width="100%",
    )


def index() -> rx.Component:
    """Render the public browse page with URL-synced filters."""
    return app_shell(
        rx.flex(
            rx.box(
                _browse_filters(),
                width=rx.breakpoints(initial="100%", lg="20rem"),
                flex_shrink="0",
            ),
            rx.box(
                _browse_results(),
                flex="1",
                width="100%",
            ),
            direction=rx.breakpoints(initial="column", lg="row"),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        page_kicker="Catalog Discovery",
        page_title="Browse Contracts",
        page_intro=(
            "Search, filter, sort, and page through the curated Xian catalog without "
            "losing shareable URL state."
        ),
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
