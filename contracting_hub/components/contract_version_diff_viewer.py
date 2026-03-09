"""Version-diff primitives for public contract pages."""

from __future__ import annotations

from typing import Literal

import reflex as rx

from contracting_hub.components.contract_catalog import contract_metadata_badge
from contracting_hub.components.page_section import page_section


def contract_version_diff_viewer(
    *,
    selected_version: object,
    previous_version: object,
    has_previous_version: object,
    has_diff_content: object,
    added_lines_label: object,
    removed_lines_label: object,
    line_delta_label: object,
    hunk_count_label: object,
    context_lines_label: object,
    unified_diff: object,
    **props: object,
) -> rx.Component:
    """Render one unified public diff against the previous visible release."""
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.text(
                        "Version diff",
                        font_size="0.75rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        "Change viewer",
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Compare the selected public release against the previous visible "
                            "baseline without leaving the detail page."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="40rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    rx.cond(
                        selected_version,
                        contract_metadata_badge(selected_version, tone="category"),
                    ),
                    rx.cond(
                        has_previous_version,
                        contract_metadata_badge(previous_version, tone="neutral"),
                        contract_metadata_badge("Initial release", tone="neutral"),
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
            rx.cond(
                has_previous_version,
                _diff_ready_state(
                    selected_version=selected_version,
                    previous_version=previous_version,
                    has_diff_content=has_diff_content,
                    added_lines_label=added_lines_label,
                    removed_lines_label=removed_lines_label,
                    line_delta_label=line_delta_label,
                    hunk_count_label=hunk_count_label,
                    context_lines_label=context_lines_label,
                    unified_diff=unified_diff,
                ),
                _initial_release_state(selected_version),
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        **props,
    )


def _diff_ready_state(
    *,
    selected_version: object,
    previous_version: object,
    has_diff_content: object,
    added_lines_label: object,
    removed_lines_label: object,
    line_delta_label: object,
    hunk_count_label: object,
    context_lines_label: object,
    unified_diff: object,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.grid(
                _comparison_card(
                    title="Previous visible release",
                    version_label=previous_version,
                    accent="previous",
                ),
                _comparison_card(
                    title="Current selection",
                    version_label=selected_version,
                    accent="current",
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.flex(
                _metric_badge(added_lines_label, "grass"),
                _metric_badge(removed_lines_label, "tomato"),
                _metric_badge(line_delta_label, "gray"),
                _metric_badge(hunk_count_label, "gray"),
                _metric_badge(context_lines_label, "gray"),
                wrap="wrap",
                gap="var(--hub-space-2)",
                width="100%",
            ),
            rx.cond(
                has_diff_content,
                rx.vstack(
                    rx.vstack(
                        rx.text(
                            "Unified diff",
                            font_size="0.75rem",
                            font_weight="600",
                            text_transform="uppercase",
                            letter_spacing="0.08em",
                            color="var(--hub-color-text-muted)",
                        ),
                        rx.text(
                            "Only public predecessors are compared in this view.",
                            color="var(--hub-color-text-muted)",
                        ),
                        align="start",
                        gap="var(--hub-space-2)",
                        width="100%",
                    ),
                    rx.box(
                        rx.code_block(
                            unified_diff,
                            language="diff",
                            theme=rx.code_block.themes.one_light,
                            show_line_numbers=True,
                            wrap_long_lines=False,
                            custom_style={
                                "margin": "0",
                                "padding": "1.25rem",
                                "fontFamily": "var(--hub-font-mono)",
                                "fontSize": "0.88rem",
                                "lineHeight": "1.7",
                                "minWidth": "100%",
                            },
                        ),
                        width="100%",
                        overflow_x="auto",
                        border="1px solid rgba(124, 93, 37, 0.16)",
                        border_radius="var(--hub-radius-md)",
                        background="rgba(255, 251, 244, 0.96)",
                    ),
                    align="start",
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                _no_changes_state(
                    previous_version=previous_version,
                    selected_version=selected_version,
                ),
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid rgba(124, 93, 37, 0.14)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 248, 236, 0.72)",
    )


def _comparison_card(
    *,
    title: str,
    version_label: object,
    accent: Literal["previous", "current"],
) -> rx.Component:
    background = (
        "rgba(255, 252, 246, 0.92)"
        if accent == "previous"
        else "linear-gradient(135deg, rgba(255, 239, 208, 0.92) 0%, rgba(255, 246, 228, 0.96) 100%)"
    )
    border_color = "rgba(124, 93, 37, 0.14)" if accent == "previous" else "rgba(181, 119, 28, 0.24)"
    text_color = (
        "var(--hub-color-accent-strong)" if accent == "current" else "var(--hub-color-text)"
    )
    return rx.box(
        rx.vstack(
            rx.text(
                title,
                font_size="0.75rem",
                font_weight="600",
                text_transform="uppercase",
                letter_spacing="0.08em",
                color="var(--hub-color-text-muted)",
            ),
            rx.text(
                version_label,
                font_family="var(--hub-font-mono)",
                font_size="1rem",
                font_weight="700",
                color=text_color,
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border=f"1px solid {border_color}",
        border_radius="var(--hub-radius-md)",
        background=background,
    )


def _metric_badge(
    label: object,
    color_scheme: Literal["grass", "tomato", "gray"],
) -> rx.Component:
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme=color_scheme,
        padding_x="0.85rem",
        padding_y="0.35rem",
    )


def _initial_release_state(selected_version: object) -> rx.Component:
    return _empty_state(
        title="Initial public release",
        body=rx.text(
            "Version ",
            selected_version,
            (
                " is the first visible release for this contract, so there is no "
                "earlier public baseline to compare yet."
            ),
            color="var(--hub-color-text-muted)",
            max_width="38rem",
        ),
    )


def _no_changes_state(
    *,
    previous_version: object,
    selected_version: object,
) -> rx.Component:
    return _empty_state(
        title="No source changes detected",
        body=rx.text(
            "Versions ",
            previous_version,
            " and ",
            selected_version,
            " currently expose the same public source snapshot.",
            color="var(--hub-color-text-muted)",
            max_width="38rem",
        ),
    )


def _empty_state(*, title: str, body: rx.Component) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                title,
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            body,
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px dashed rgba(124, 93, 37, 0.24)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 251, 244, 0.78)",
    )


__all__ = ["contract_version_diff_viewer"]
