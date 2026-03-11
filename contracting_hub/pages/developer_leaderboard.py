"""Public developer leaderboard page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import (
    app_shell,
    contract_rating_summary,
    page_error_state,
    page_loading_state,
    page_section,
)
from contracting_hub.states import AuthState, DeveloperLeaderboardState
from contracting_hub.utils.meta import DEVELOPER_LEADERBOARD_ROUTE

ROUTE = DEVELOPER_LEADERBOARD_ROUTE
ON_LOAD = [AuthState.sync_auth_state, DeveloperLeaderboardState.load_page]

SORT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("star_total", "Most starred"),
    ("weighted_rating", "Top rated"),
    ("contract_count", "Most contracts"),
    ("deployment_count", "Most deployed"),
    ("recent_activity", "Recent activity"),
)
TIMEFRAME_OPTIONS: tuple[tuple[str, str], ...] = (
    ("all_time", "All time"),
    ("recent", "Recent window"),
)
WINDOW_OPTIONS: tuple[tuple[str, str], ...] = (
    ("30", "30 days"),
    ("90", "90 days"),
    ("180", "180 days"),
    ("365", "365 days"),
)


def _control_field(
    label: str,
    control: rx.Component,
    *,
    control_id: str,
    helper: str | None = None,
) -> rx.Component:
    children: list[rx.Component] = [
        rx.el.label(
            label,
            html_for=control_id,
            font_size="0.78rem",
            font_weight="600",
            text_transform="uppercase",
            letter_spacing="0.08em",
            color="var(--hub-color-text-muted)",
        ),
        control,
    ]
    if helper is not None:
        children.append(
            rx.text(
                helper,
                color="var(--hub-color-text-muted)",
                font_size="0.85rem",
            )
        )
    return rx.vstack(
        *children,
        align="start",
        gap="var(--hub-space-2)",
        width="100%",
    )


def _select_style() -> dict[str, str]:
    return {
        "width": "100%",
        "padding": "0.7rem 0.85rem",
        "border": "1px solid var(--hub-color-line)",
        "border_radius": "var(--hub-radius-sm)",
        "background": "rgba(255, 253, 248, 0.98)",
        "color": "var(--hub-color-text)",
        "font_family": "var(--hub-font-body)",
        "font_size": "0.92rem",
        "outline": "none",
    }


def _leaderboard_filters() -> rx.Component:
    fieldset_style = {
        "border": "none",
        "margin": "0",
        "padding": "0",
        "minWidth": "0",
        "width": "100%",
    }
    return page_section(
        rx.vstack(
            rx.vstack(
                rx.badge(
                    "Leaderboard controls",
                    radius="full",
                    variant="soft",
                    color_scheme="bronze",
                    width="fit-content",
                ),
                rx.heading(
                    "Compare public Xian authors quickly.",
                    size="5",
                    font_family="var(--hub-font-display)",
                    letter_spacing="-0.05em",
                    color="var(--hub-color-text)",
                ),
                rx.text(
                    (
                        "Switch between all-time and recent windows, then rank developers by "
                        "published contracts, stars, ratings, deployments, or recent activity."
                    ),
                    color="var(--hub-color-text-muted)",
                ),
                align="start",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.form(
                rx.el.fieldset(
                    rx.el.legend("Developer ranking filters", class_name="hub-visually-hidden"),
                    rx.vstack(
                        _control_field(
                            "Sort by",
                            rx.el.select(
                                *[
                                    rx.el.option(label, value=value)
                                    for value, label in SORT_OPTIONS
                                ],
                                id="leaderboard-sort",
                                name="sort",
                                value=DeveloperLeaderboardState.selected_sort,
                                on_change=DeveloperLeaderboardState.set_selected_sort,
                                style=_select_style(),
                            ),
                            control_id="leaderboard-sort",
                        ),
                        _control_field(
                            "Timeframe",
                            rx.el.select(
                                *[
                                    rx.el.option(label, value=value)
                                    for value, label in TIMEFRAME_OPTIONS
                                ],
                                id="leaderboard-timeframe",
                                name="timeframe",
                                value=DeveloperLeaderboardState.selected_timeframe,
                                on_change=DeveloperLeaderboardState.set_selected_timeframe,
                                style=_select_style(),
                            ),
                            control_id="leaderboard-timeframe",
                        ),
                        _control_field(
                            "Recent window",
                            rx.el.select(
                                *[
                                    rx.el.option(label, value=value)
                                    for value, label in WINDOW_OPTIONS
                                ],
                                id="leaderboard-window",
                                name="window",
                                value=DeveloperLeaderboardState.selected_window_days,
                                on_change=DeveloperLeaderboardState.set_selected_window_days,
                                style=_select_style(),
                            ),
                            control_id="leaderboard-window",
                            helper=(
                                "Used for recent filters, recent-activity ranking, "
                                "and activity context."
                            ),
                        ),
                        rx.flex(
                            rx.button(
                                "Apply ranking",
                                type="submit",
                                size="3",
                                variant="solid",
                                width=rx.breakpoints(initial="100%", sm="auto"),
                            ),
                            rx.link(
                                rx.button(
                                    "Reset",
                                    type="button",
                                    size="3",
                                    variant="soft",
                                    width=rx.breakpoints(initial="100%", sm="auto"),
                                ),
                                href=DeveloperLeaderboardState.clear_filters_href,
                                text_decoration="none",
                                width=rx.breakpoints(initial="100%", sm="auto"),
                            ),
                            direction=rx.breakpoints(initial="column", sm="row"),
                            gap="var(--hub-space-3)",
                            width="100%",
                        ),
                        align="start",
                        gap="var(--hub-space-4)",
                        width="100%",
                    ),
                    style=fieldset_style,
                ),
                on_submit=DeveloperLeaderboardState.apply_filters,
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        custom_attrs={"data-testid": "developer-leaderboard-filters"},
        position=rx.breakpoints(initial="static", lg="sticky"),
        top=rx.breakpoints(initial="0", lg="5.75rem"),
    )


def _summary_chip(label: str, value: object) -> rx.Component:
    return rx.box(
        rx.text(
            label,
            font_size="0.68rem",
            text_transform="uppercase",
            letter_spacing="0.08em",
            color="var(--hub-color-text-muted)",
        ),
        rx.text(
            value,
            font_size="0.92rem",
            font_weight="600",
            color="var(--hub-color-text)",
        ),
        padding="0.65rem 0.85rem",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-sm)",
        background="rgba(255, 250, 242, 0.7)",
        class_name="hub-metric",
    )


def _metric_panel(label: object, value: object) -> rx.Component:
    value_component = (
        value
        if isinstance(value, rx.Component)
        else rx.text(
            value,
            font_size="1rem",
            font_weight="700",
            color="var(--hub-color-text)",
        )
    )
    return rx.box(
        rx.vstack(
            rx.text(
                label,
                font_size="0.72rem",
                font_weight="600",
                text_transform="uppercase",
                letter_spacing="0.08em",
                color="var(--hub-color-text-muted)",
            ),
            value_component,
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-sm)",
        background="rgba(255, 250, 242, 0.7)",
        class_name="hub-metric",
    )


def _leaderboard_card(entry) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.flex(
                    rx.box(
                        rx.text(
                            entry["rank_label"],
                            font_size="1rem",
                            font_weight="700",
                            color="var(--hub-color-accent-strong)",
                        ),
                        min_width="3.25rem",
                        padding="0.95rem 1rem",
                        border="1px solid rgba(124, 93, 37, 0.14)",
                        border_radius="var(--hub-radius-md)",
                        background="rgba(255, 248, 236, 0.9)",
                        text_align="center",
                        flex_shrink="0",
                    ),
                    rx.avatar(
                        fallback=entry["avatar_fallback"],
                        size="5",
                        radius="full",
                        color_scheme="bronze",
                        variant="soft",
                    ),
                    rx.vstack(
                        rx.link(
                            rx.heading(
                                entry["display_name"],
                                size="5",
                                font_family="var(--hub-font-display)",
                                letter_spacing="-0.04em",
                                color="var(--hub-color-text)",
                            ),
                            href=entry["profile_href"].to(str),
                            text_decoration="none",
                            color="inherit",
                        ),
                        rx.text(
                            entry["username_label"],
                            color="var(--hub-color-text-muted)",
                            font_size="0.96rem",
                        ),
                        align="start",
                        gap="var(--hub-space-1)",
                        width="100%",
                    ),
                    align="center",
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                rx.link(
                    rx.button("View profile", size="2", variant="soft"),
                    href=entry["profile_href"].to(str),
                    text_decoration="none",
                ),
                direction=rx.breakpoints(initial="column", lg="row"),
                align=rx.breakpoints(initial="start", lg="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.grid(
                _metric_panel(entry["contracts_label"], entry["contracts_value"]),
                _metric_panel(entry["stars_label"], entry["stars_value"]),
                _metric_panel(
                    "Rating",
                    contract_rating_summary(
                        headline=entry["rating_headline"],
                        detail=entry["rating_detail"],
                        empty=entry["rating_empty"],
                    ),
                ),
                _metric_panel("Recent activity", entry["recent_activity_value"]),
                _metric_panel(entry["deployments_label"], entry["deployments_value"]),
                columns=rx.breakpoints(initial="1", sm="2", xl="5"),
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.text(
                entry["recent_activity_breakdown"],
                color="var(--hub-color-text-muted)",
                font_size="0.9rem",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 253, 248, 0.94)",
        box_shadow="var(--hub-shadow-panel)",
        class_name="hub-card",
        custom_attrs={"data-testid": "developer-leaderboard-card"},
    )


def _leaderboard_empty_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "No ranked developers yet",
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                (
                    "Public leaderboard rows appear after developers publish contracts that "
                    "count toward the catalog KPIs."
                ),
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px dashed var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.68)",
        custom_attrs={"data-testid": "developer-leaderboard-empty"},
    )


def _leaderboard_results() -> rx.Component:
    return rx.box(
        rx.cond(
            DeveloperLeaderboardState.is_loading,
            page_loading_state(
                title="Loading developer rankings",
                body="Refreshing public author KPI totals and ranking context.",
                test_id="developer-leaderboard-loading",
            ),
            rx.cond(
                DeveloperLeaderboardState.has_load_error,
                page_error_state(
                    title="Leaderboard data could not be loaded",
                    body=DeveloperLeaderboardState.load_error_message,
                    test_id="developer-leaderboard-error",
                    action=rx.link(
                        rx.button("Reset leaderboard filters", size="3", variant="soft"),
                        href=DeveloperLeaderboardState.clear_filters_href,
                        text_decoration="none",
                    ),
                ),
                page_section(
                    rx.vstack(
                        rx.flex(
                            rx.vstack(
                                rx.badge(
                                    "Public ranking",
                                    radius="full",
                                    variant="soft",
                                    color_scheme="bronze",
                                    width="fit-content",
                                ),
                                rx.heading(
                                    DeveloperLeaderboardState.developer_count_label,
                                    size="6",
                                    font_family="var(--hub-font-display)",
                                    letter_spacing="-0.05em",
                                    color="var(--hub-color-text)",
                                ),
                                rx.text(
                                    DeveloperLeaderboardState.leaderboard_context,
                                    color="var(--hub-color-text-muted)",
                                    max_width="40rem",
                                ),
                                align="start",
                                gap="var(--hub-space-3)",
                                width="100%",
                            ),
                            rx.flex(
                                _summary_chip(
                                    "Sort",
                                    DeveloperLeaderboardState.selected_sort_label,
                                ),
                                _summary_chip(
                                    "Timeframe",
                                    DeveloperLeaderboardState.selected_timeframe_label,
                                ),
                                _summary_chip(
                                    "Recent window",
                                    DeveloperLeaderboardState.activity_window_label,
                                ),
                                wrap="wrap",
                                gap="var(--hub-space-3)",
                                justify=rx.breakpoints(initial="start", xl="end"),
                            ),
                            direction=rx.breakpoints(initial="column", xl="row"),
                            align=rx.breakpoints(initial="start", xl="center"),
                            justify="between",
                            gap="var(--hub-space-4)",
                            width="100%",
                        ),
                        rx.cond(
                            DeveloperLeaderboardState.has_entries,
                            rx.vstack(
                                rx.foreach(
                                    DeveloperLeaderboardState.leaderboard_entries,
                                    _leaderboard_card,
                                ),
                                width="100%",
                                gap="var(--hub-space-4)",
                            ),
                            _leaderboard_empty_state(),
                        ),
                        align="start",
                        gap="var(--hub-space-5)",
                        width="100%",
                    ),
                    custom_attrs={"data-testid": "developer-leaderboard-results"},
                ),
            ),
        ),
        width="100%",
    )


def index() -> rx.Component:
    """Render the public developer leaderboard shell."""
    return app_shell(
        rx.box(
            rx.grid(
                _leaderboard_filters(),
                _leaderboard_results(),
                columns=rx.breakpoints(initial="1", xl="20rem 1fr"),
                gap="var(--hub-space-6)",
                width="100%",
                align_items="start",
            ),
            width="100%",
            custom_attrs={"data-testid": "developer-leaderboard-page"},
        ),
        page_kicker="Developer leaderboard",
        page_title="Developer Leaderboard",
        page_intro=DeveloperLeaderboardState.page_intro,
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
