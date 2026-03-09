"""Contract source-code viewer primitives."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components.contract_catalog import contract_metadata_badge
from contracting_hub.components.page_section import page_section


def contract_source_viewer(
    *,
    source_code: object,
    source_download_url: object,
    source_download_filename: object,
    version_label: object,
    line_count_label: object,
    has_source_code: object,
    **props: object,
) -> rx.Component:
    """Render a syntax-highlighted Python source viewer with copy and download actions."""
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.text(
                        "Contract source",
                        font_size="0.75rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        "Python viewer",
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        "Read, copy, or download the currently selected public source snapshot.",
                        color="var(--hub-color-text-muted)",
                        max_width="38rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.vstack(
                    rx.flex(
                        contract_metadata_badge("Python", tone="neutral"),
                        rx.cond(
                            version_label,
                            _viewer_badge(version_label),
                        ),
                        rx.cond(
                            has_source_code,
                            _viewer_badge(line_count_label),
                        ),
                        wrap="wrap",
                        gap="var(--hub-space-2)",
                        justify=rx.breakpoints(initial="start", md="end"),
                        width="100%",
                    ),
                    rx.cond(
                        has_source_code,
                        rx.flex(
                            rx.button(
                                "Copy code",
                                size="2",
                                variant="soft",
                                on_click=rx.set_clipboard(source_code),
                            ),
                            rx.button(
                                "Download .py",
                                size="2",
                                variant="soft",
                                on_click=rx.download(
                                    data=source_download_url,
                                    filename=source_download_filename,
                                ),
                            ),
                            wrap="wrap",
                            gap="var(--hub-space-3)",
                            justify=rx.breakpoints(initial="start", md="end"),
                            width="100%",
                        ),
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width=rx.breakpoints(initial="100%", md="auto"),
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="end"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.cond(
                has_source_code,
                rx.box(
                    rx.code_block(
                        source_code,
                        language="python",
                        theme=rx.code_block.themes.one_light,
                        show_line_numbers=True,
                        wrap_long_lines=True,
                        custom_style={
                            "margin": "0",
                            "padding": "1.25rem",
                            "fontFamily": "var(--hub-font-mono)",
                            "fontSize": "0.92rem",
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
                _empty_source_state(),
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        **props,
    )


def _viewer_badge(label: object) -> rx.Component:
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme="gray",
        padding_x="0.85rem",
        padding_y="0.35rem",
    )


def _empty_source_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "Source unavailable",
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                "The selected public version does not currently expose a source snapshot.",
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px dashed rgba(124, 93, 37, 0.24)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 248, 236, 0.56)",
    )


__all__ = ["contract_source_viewer"]
