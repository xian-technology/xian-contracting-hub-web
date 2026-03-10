"""Shared page-level loading and failure states."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components.page_section import page_section


def _page_state_panel(
    *,
    badge_label: str,
    title: str,
    body: str,
    color_scheme: str,
    test_id: str,
    actions: rx.Component | None = None,
) -> rx.Component:
    children: list[rx.Component] = [
        rx.badge(
            badge_label,
            radius="full",
            variant="soft",
            color_scheme=color_scheme,
            width="fit-content",
        ),
        rx.heading(
            title,
            size="5",
            font_family="var(--hub-font-display)",
            letter_spacing="-0.05em",
            color="var(--hub-color-text)",
        ),
        rx.text(
            body,
            color="var(--hub-color-text-muted)",
            max_width="36rem",
        ),
    ]
    if actions is not None:
        children.append(actions)

    return page_section(
        rx.vstack(
            *children,
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        custom_attrs={"data-testid": test_id},
    )


def page_loading_state(*, title: str, body: str, test_id: str) -> rx.Component:
    """Render a consistent page-level loading panel."""
    return _page_state_panel(
        badge_label="Loading",
        title=title,
        body=body,
        color_scheme="bronze",
        test_id=test_id,
    )


def page_error_state(
    *,
    title: str,
    body: str,
    test_id: str,
    action: rx.Component | None = None,
) -> rx.Component:
    """Render a consistent page-level failure panel."""
    return _page_state_panel(
        badge_label="Load failed",
        title=title,
        body=body,
        color_scheme="tomato",
        test_id=test_id,
        actions=action,
    )


__all__ = ["page_error_state", "page_loading_state"]
