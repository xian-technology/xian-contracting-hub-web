"""Version-history and changelog primitives for public contract pages."""

from __future__ import annotations

from typing import Literal

import reflex as rx

from contracting_hub.components.contract_catalog import contract_metadata_badge
from contracting_hub.components.page_section import page_section


def contract_version_history(
    *,
    versions: object,
    version_count_label: object,
    selected_version: object,
    selected_version_status_label: object,
    selected_version_status_color_scheme: object,
    selected_version_published_label: object,
    selected_version_changelog: object,
    has_selected_version_changelog: object,
    selected_version_is_latest_public: object,
    **props: object,
) -> rx.Component:
    """Render one public version selector with changelog context."""
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.text(
                        "Version history",
                        font_size="0.75rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        "Release selector",
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Jump between public releases to inspect source snapshots, "
                            "status changes, and release notes."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="40rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    contract_metadata_badge(version_count_label, tone="neutral"),
                    rx.cond(
                        selected_version,
                        contract_metadata_badge(selected_version, tone="category"),
                    ),
                    wrap="wrap",
                    gap="var(--hub-space-2)",
                    justify=rx.breakpoints(initial="start", md="end"),
                    width=rx.breakpoints(initial="100%", md="auto"),
                ),
                direction=rx.breakpoints(initial="column", lg="row"),
                align=rx.breakpoints(initial="start", lg="end"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.grid(
                rx.vstack(
                    rx.foreach(versions, _version_selector_item),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                rx.box(
                    rx.vstack(
                        rx.flex(
                            rx.vstack(
                                rx.text(
                                    "Release notes",
                                    font_size="0.75rem",
                                    font_weight="600",
                                    text_transform="uppercase",
                                    letter_spacing="0.08em",
                                    color="var(--hub-color-text-muted)",
                                ),
                                rx.heading(
                                    selected_version,
                                    size="4",
                                    font_family="var(--hub-font-display)",
                                    color="var(--hub-color-text)",
                                ),
                                rx.text(
                                    "Published ",
                                    selected_version_published_label,
                                    color="var(--hub-color-text-muted)",
                                ),
                                align="start",
                                gap="var(--hub-space-2)",
                                width="100%",
                            ),
                            rx.flex(
                                _status_badge(
                                    selected_version_status_label,
                                    selected_version_status_color_scheme,
                                ),
                                rx.cond(
                                    selected_version_is_latest_public,
                                    contract_metadata_badge("Latest public", tone="success"),
                                    contract_metadata_badge("Historical release", tone="neutral"),
                                ),
                                wrap="wrap",
                                gap="var(--hub-space-2)",
                                justify=rx.breakpoints(initial="start", md="end"),
                                width=rx.breakpoints(initial="100%", md="auto"),
                            ),
                            direction=rx.breakpoints(initial="column", md="row"),
                            align=rx.breakpoints(initial="start", md="start"),
                            justify="between",
                            gap="var(--hub-space-4)",
                            width="100%",
                        ),
                        rx.cond(
                            has_selected_version_changelog,
                            rx.text(
                                selected_version_changelog,
                                color="var(--hub-color-text)",
                                line_height="1.7",
                                white_space="pre-wrap",
                                width="100%",
                            ),
                            _empty_changelog_state(),
                        ),
                        align="start",
                        gap="var(--hub-space-4)",
                        width="100%",
                    ),
                    width="100%",
                    height="100%",
                    padding="var(--hub-space-5)",
                    border="1px solid rgba(124, 93, 37, 0.14)",
                    border_radius="var(--hub-radius-md)",
                    background="rgba(255, 248, 236, 0.74)",
                ),
                columns=rx.breakpoints(initial="1", xl="1.1fr 0.9fr"),
                gap="var(--hub-space-5)",
                width="100%",
                align_items="start",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        **props,
    )


def _version_selector_item(version: object) -> rx.Component:
    return rx.link(
        rx.box(
            rx.vstack(
                rx.flex(
                    rx.vstack(
                        rx.text(
                            version["semantic_version"],
                            font_family="var(--hub-font-mono)",
                            font_size="1rem",
                            font_weight="600",
                            color="var(--hub-color-accent-strong)",
                        ),
                        rx.text(
                            "Published ",
                            version["published_label"],
                            color="var(--hub-color-text-muted)",
                            font_size="0.88rem",
                        ),
                        align="start",
                        gap="var(--hub-space-1)",
                        width="100%",
                    ),
                    rx.flex(
                        rx.cond(
                            version["is_selected"],
                            contract_metadata_badge("Viewing", tone="category"),
                        ),
                        rx.cond(
                            version["is_latest_public"],
                            contract_metadata_badge("Latest", tone="success"),
                        ),
                        _status_badge(
                            version["status_label"],
                            version["status_color_scheme"],
                        ),
                        wrap="wrap",
                        gap="var(--hub-space-2)",
                        justify=rx.breakpoints(initial="start", md="end"),
                        width=rx.breakpoints(initial="100%", md="auto"),
                    ),
                    direction=rx.breakpoints(initial="column", md="row"),
                    align=rx.breakpoints(initial="start", md="center"),
                    justify="between",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                align="start",
                gap="var(--hub-space-2)",
                width="100%",
            ),
            width="100%",
            padding="var(--hub-space-4)",
            border="1px solid var(--hub-color-line)",
            border_radius="var(--hub-radius-sm)",
            background=rx.cond(
                version["is_selected"],
                "rgba(255, 245, 225, 0.96)",
                "rgba(255, 253, 248, 0.88)",
            ),
            class_name="hub-version-item",
        ),
        href=version["href"].to(str),
        text_decoration="none",
        color="inherit",
        width="100%",
    )


def _status_badge(label: object, color_scheme: object) -> rx.Component:
    return rx.cond(
        color_scheme == "grass",
        _status_badge_with_literal_scheme(label, "grass"),
        rx.cond(
            color_scheme == "orange",
            _status_badge_with_literal_scheme(label, "orange"),
            _status_badge_with_literal_scheme(label, "gray"),
        ),
    )


def _status_badge_with_literal_scheme(
    label: object,
    color_scheme: Literal["grass", "orange", "gray"],
) -> rx.Component:
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme=color_scheme,
        padding_x="0.85rem",
        padding_y="0.35rem",
    )


def _empty_changelog_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "No changelog published",
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                (
                    "This public release does not yet include release notes. "
                    "You can still inspect the source snapshot and status metadata."
                ),
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border="1px dashed rgba(124, 93, 37, 0.24)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 251, 244, 0.72)",
    )


__all__ = ["contract_version_history"]
