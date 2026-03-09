"""Public contract-detail header primitives."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components.contract_catalog import ContractCardMetric


def contract_detail_header(
    *,
    badges: rx.Component,
    context_label: object,
    display_name: object,
    contract_name: object,
    short_summary: object,
    long_description: object,
    taxonomy: rx.Component,
    metrics: tuple[ContractCardMetric, ...] | list[ContractCardMetric],
    author_panel: rx.Component,
    actions: rx.Component,
    **props: object,
) -> rx.Component:
    """Render the shared hero/header shell for one contract detail page."""
    return rx.box(
        rx.vstack(
            rx.flex(
                badges,
                actions,
                direction=rx.breakpoints(initial="column", lg="row"),
                align=rx.breakpoints(initial="start", lg="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.grid(
                rx.vstack(
                    rx.text(
                        context_label,
                        font_size="0.82rem",
                        font_weight="600",
                        letter_spacing="0.04em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        display_name,
                        size="8",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.06em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        contract_name,
                        font_family="var(--hub-font-mono)",
                        font_size="0.98rem",
                        color="var(--hub-color-accent-strong)",
                    ),
                    rx.text(
                        short_summary,
                        size="4",
                        color="var(--hub-color-text)",
                        max_width="42rem",
                    ),
                    rx.text(
                        long_description,
                        color="var(--hub-color-text-muted)",
                        max_width="54rem",
                    ),
                    taxonomy,
                    align="start",
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                author_panel,
                columns=rx.breakpoints(initial="1", xl="2"),
                gap="var(--hub-space-6)",
                width="100%",
                align_items="start",
            ),
            rx.grid(
                *[_detail_metric(metric) for metric in metrics],
                columns=rx.breakpoints(initial="1", sm="2", xl="4"),
                gap="var(--hub-space-3)",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-6)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-8)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-lg)",
        background=(
            "linear-gradient(180deg, rgba(255, 252, 246, 0.96) 0%, rgba(248, 241, 230, 0.92) 100%)"
        ),
        box_shadow="var(--hub-shadow-panel)",
        **props,
    )


def _detail_metric(metric: ContractCardMetric) -> rx.Component:
    value_component = (
        metric.value
        if isinstance(metric.value, rx.Component)
        else rx.text(
            metric.value,
            font_size="1rem",
            font_weight="600",
            color="var(--hub-color-text)",
        )
    )
    return rx.box(
        rx.text(
            metric.label,
            font_size="0.72rem",
            text_transform="uppercase",
            letter_spacing="0.08em",
            color="var(--hub-color-text-muted)",
        ),
        value_component,
        padding="1rem 1.1rem",
        border="1px solid rgba(124, 93, 37, 0.14)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 248, 236, 0.84)",
    )


__all__ = ["contract_detail_header"]
