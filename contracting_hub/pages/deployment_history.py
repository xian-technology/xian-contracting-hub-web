"""Authenticated deployment-history page."""

from __future__ import annotations

from typing import Literal

import reflex as rx

from contracting_hub.components import app_shell, page_section
from contracting_hub.states import AuthState, DeploymentHistoryState
from contracting_hub.utils.meta import (
    BROWSE_ROUTE,
    DEPLOYMENT_HISTORY_ROUTE,
    PROFILE_SETTINGS_ROUTE,
)

ROUTE = DEPLOYMENT_HISTORY_ROUTE
ON_LOAD = [AuthState.guard_authenticated_route, DeploymentHistoryState.load_page]


def _message_banner(message, *, tone: Literal["error", "info"]) -> rx.Component:
    color = "tomato" if tone == "error" else "var(--hub-color-accent-strong)"
    border = (
        "1px solid rgba(191, 61, 48, 0.22)"
        if tone == "error"
        else "1px solid rgba(142, 89, 30, 0.22)"
    )
    background = "rgba(255, 244, 242, 0.95)" if tone == "error" else "rgba(255, 249, 239, 0.96)"
    return rx.cond(
        message != "",
        rx.box(
            rx.text(
                message,
                color=color,
                font_weight="600",
            ),
            width="100%",
            padding="0.9rem 1rem",
            border=border,
            border_radius="var(--hub-radius-md)",
            background=background,
        ),
    )


def _status_badge(label: object, color_scheme: object) -> rx.Component:
    return rx.cond(
        color_scheme == "grass",
        _status_badge_with_literal_scheme(label, "grass"),
        rx.cond(
            color_scheme == "bronze",
            _status_badge_with_literal_scheme(label, "bronze"),
            rx.cond(
                color_scheme == "tomato",
                _status_badge_with_literal_scheme(label, "tomato"),
                _status_badge_with_literal_scheme(label, "gray"),
            ),
        ),
    )


def _status_badge_with_literal_scheme(
    label: object,
    color_scheme: Literal["grass", "bronze", "tomato", "gray"],
) -> rx.Component:
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme=color_scheme,
        padding_x="0.85rem",
        padding_y="0.35rem",
    )


def _history_metric(
    label: str,
    value,
    detail=None,
    *,
    mono: bool = False,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(
                label,
                font_size="0.72rem",
                text_transform="uppercase",
                letter_spacing="0.08em",
                color="var(--hub-color-text-muted)",
            ),
            rx.text(
                value,
                font_size="0.98rem",
                font_weight="600",
                font_family=("var(--hub-font-mono)" if mono else "var(--hub-font-body)"),
                color="var(--hub-color-text)",
            ),
            rx.cond(
                detail != "",
                rx.text(
                    detail,
                    font_size="0.88rem",
                    color="var(--hub-color-text-muted)",
                ),
            ),
            align="start",
            gap="var(--hub-space-1)",
            width="100%",
        ),
        width="100%",
        padding="0.95rem 1rem",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.78)",
    )


def _saved_target_shortcut(shortcut) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.flex(
                        rx.text(
                            shortcut["label"],
                            font_size="1rem",
                            font_weight="600",
                            color="var(--hub-color-text)",
                        ),
                        rx.cond(
                            shortcut["is_default"],
                            rx.badge(
                                shortcut["default_badge_label"],
                                radius="full",
                                variant="soft",
                                color_scheme="bronze",
                            ),
                        ),
                        wrap="wrap",
                        gap="var(--hub-space-2)",
                        align="center",
                    ),
                    rx.text(
                        shortcut["playground_id"],
                        font_family="var(--hub-font-mono)",
                        font_size="0.95rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.text(
                        shortcut["last_used_label"],
                        font_size="0.9rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-1)",
                    width="100%",
                ),
                rx.button(
                    "Filter history",
                    type="button",
                    size="2",
                    variant="soft",
                    on_click=DeploymentHistoryState.set_target_filter(shortcut["filter_value"]),
                    custom_attrs={"data-testid": "deployment-history-filter-button"},
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.82)",
        custom_attrs={"data-testid": "deployment-history-shortcut"},
    )


def _saved_target_shortcuts() -> rx.Component:
    shortcuts = rx.cond(
        DeploymentHistoryState.has_saved_target_shortcuts,
        rx.vstack(
            rx.foreach(DeploymentHistoryState.saved_target_shortcuts, _saved_target_shortcut),
            width="100%",
            gap="var(--hub-space-3)",
        ),
        rx.box(
            rx.vstack(
                rx.heading(
                    "No saved playground targets yet.",
                    size="3",
                    font_family="var(--hub-font-display)",
                    color="var(--hub-color-text)",
                ),
                rx.text(
                    "Save a target in profile settings to keep deployment filters close at hand.",
                    color="var(--hub-color-text-muted)",
                ),
                align="start",
                gap="var(--hub-space-2)",
            ),
            width="100%",
            padding="var(--hub-space-5)",
            border="1px dashed var(--hub-color-line)",
            border_radius="var(--hub-radius-md)",
            background="rgba(255, 250, 242, 0.62)",
        ),
    )

    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.badge(
                        "Saved targets",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.heading(
                        "Saved target shortcuts",
                        size="5",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.05em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Filter your recent deployment records by saved playground target "
                            "without reopening the deployment drawer."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="34rem",
                    ),
                    rx.text(
                        DeploymentHistoryState.saved_target_shortcut_count_label,
                        font_size="0.9rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                rx.flex(
                    rx.button(
                        "Show all deployments",
                        type="button",
                        size="2",
                        variant="soft",
                        on_click=DeploymentHistoryState.show_all_deployments,
                    ),
                    rx.link(
                        rx.button("Manage targets", size="2", variant="soft"),
                        href=PROFILE_SETTINGS_ROUTE,
                        text_decoration="none",
                    ),
                    direction=rx.breakpoints(initial="column", sm="row"),
                    gap="var(--hub-space-3)",
                    width=rx.breakpoints(initial="100%", md="auto"),
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            shortcuts,
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        custom_attrs={"data-testid": "deployment-history-shortcuts"},
    )


def _deployment_history_entry(entry) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.link(
                        rx.heading(
                            entry["contract_title"],
                            size="4",
                            font_family="var(--hub-font-display)",
                            color="var(--hub-color-text)",
                        ),
                        href=entry["contract_href"].to(str),
                        text_decoration="none",
                    ),
                    rx.text(
                        entry["contract_name"],
                        font_family="var(--hub-font-mono)",
                        font_size="0.95rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.flex(
                        _status_badge(
                            entry["status_label"],
                            entry["status_color_scheme"],
                        ),
                        rx.badge(
                            entry["version_label"],
                            radius="full",
                            variant="soft",
                            color_scheme="gray",
                        ),
                        rx.cond(
                            entry["transport_label"] != "",
                            rx.badge(
                                entry["transport_label"],
                                radius="full",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        wrap="wrap",
                        gap="var(--hub-space-2)",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.vstack(
                    rx.text(
                        entry["initiated_label"],
                        font_size="0.9rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.text(
                        entry["completed_label"],
                        font_size="0.9rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-1)",
                    width=rx.breakpoints(initial="100%", md="auto"),
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.grid(
                _history_metric(
                    "Target",
                    entry["target_label"],
                    entry["target_detail"],
                ),
                _history_metric(
                    "Playground ID",
                    entry["playground_id"],
                    "",
                    mono=True,
                ),
                rx.cond(
                    entry["external_request_id"] != "",
                    _history_metric(
                        "Request ID",
                        entry["external_request_id"],
                        "",
                        mono=True,
                    ),
                ),
                columns=rx.breakpoints(initial="1", lg="3"),
                gap="var(--hub-space-3)",
                width="100%",
            ),
            _message_banner(entry["error_message"], tone="error"),
            rx.cond(
                entry["redirect_url"] != "",
                rx.link(
                    rx.button("Open playground", size="2"),
                    href=entry["redirect_url"],
                    is_external=True,
                    text_decoration="none",
                ),
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 252, 246, 0.86)",
        custom_attrs={"data-testid": "deployment-history-entry"},
    )


def _empty_history_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                DeploymentHistoryState.history_empty_title,
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                DeploymentHistoryState.history_empty_body,
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            rx.flex(
                rx.link(
                    rx.button("Browse contracts", size="2"),
                    href=BROWSE_ROUTE,
                    text_decoration="none",
                ),
                rx.link(
                    rx.button("Manage saved targets", size="2", variant="soft"),
                    href=PROFILE_SETTINGS_ROUTE,
                    text_decoration="none",
                ),
                direction=rx.breakpoints(initial="column", sm="row"),
                gap="var(--hub-space-3)",
                width=rx.breakpoints(initial="100%", sm="auto"),
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px dashed var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.64)",
    )


def _history_list() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.badge(
                "Recent handoffs",
                radius="full",
                variant="soft",
                color_scheme="bronze",
                width="fit-content",
            ),
            rx.heading(
                "Deployment history",
                size="5",
                font_family="var(--hub-font-display)",
                letter_spacing="-0.05em",
                color="var(--hub-color-text)",
            ),
            rx.text(
                DeploymentHistoryState.active_filter_description,
                color="var(--hub-color-text-muted)",
            ),
            rx.text(
                DeploymentHistoryState.deployment_history_count_label,
                font_size="0.9rem",
                color="var(--hub-color-text-muted)",
            ),
            _message_banner(DeploymentHistoryState.page_error_message, tone="error"),
            rx.cond(
                DeploymentHistoryState.has_visible_deployments,
                rx.vstack(
                    rx.foreach(
                        DeploymentHistoryState.visible_deployment_entries,
                        _deployment_history_entry,
                    ),
                    width="100%",
                    gap="var(--hub-space-4)",
                    custom_attrs={"data-testid": "deployment-history-list"},
                ),
                _empty_history_state(),
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        custom_attrs={"data-testid": "deployment-history-page"},
    )


def index() -> rx.Component:
    """Render the authenticated deployment history page."""
    return app_shell(
        rx.vstack(
            _saved_target_shortcuts(),
            _history_list(),
            width="100%",
            gap="var(--hub-space-6)",
        ),
        page_title="Deployment history",
        page_intro=(
            "Review the playground handoffs you have already triggered, filter them by saved "
            "target, and jump back into your deployment workflow."
        ),
        page_kicker="Authenticated account",
        auth_state=DeploymentHistoryState,
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
