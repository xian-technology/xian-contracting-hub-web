"""Reusable contract-catalog presentation primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import reflex as rx

MetadataBadgeTone = Literal["category", "featured", "neutral", "success", "warning"]

_METADATA_BADGE_COLOR_SCHEMES: dict[MetadataBadgeTone, str] = {
    "category": "bronze",
    "featured": "gold",
    "neutral": "gray",
    "success": "grass",
    "warning": "orange",
}


@dataclass(frozen=True)
class ContractCardMetric:
    """One metric rendered inside a contract card."""

    label: str
    value: object


def contract_metadata_badge(
    label: object,
    *,
    tone: MetadataBadgeTone = "neutral",
    **props: object,
) -> rx.Component:
    """Render one shared metadata badge for catalog surfaces."""
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme=_METADATA_BADGE_COLOR_SCHEMES[tone],
        **props,
    )


def contract_rating_summary(
    *,
    headline: object,
    detail: object = "",
    empty: bool | rx.Var = False,
    **props: object,
) -> rx.Component:
    """Render one shared rating summary block for cards and headers."""
    return rx.cond(
        empty,
        rx.text(
            headline,
            font_size="0.96rem",
            font_weight="500",
            color="var(--hub-color-text-muted)",
            **props,
        ),
        rx.vstack(
            rx.text(
                headline,
                font_size="0.98rem",
                font_weight="600",
                color="var(--hub-color-text)",
            ),
            rx.text(
                detail,
                font_size="0.76rem",
                color="var(--hub-color-text-muted)",
            ),
            align="start",
            spacing="1",
            **props,
        ),
    )


def contract_card(
    *,
    badges: rx.Component,
    context_label: object,
    display_name: object,
    contract_name: object,
    short_summary: object,
    metrics: tuple[ContractCardMetric, ...] | list[ContractCardMetric],
    author_name: object,
    tags: rx.Component,
    metric_columns: object,
    href: str | rx.Var[str] | None = None,
    **props: object,
) -> rx.Component:
    """Render one reusable contract summary card."""
    title = rx.heading(
        display_name,
        size="4",
        font_family="var(--hub-font-display)",
        letter_spacing="-0.04em",
        color="var(--hub-color-text)",
    )
    title_component = (
        rx.link(title, href=href, text_decoration="none", color="inherit")
        if href is not None
        else title
    )

    return rx.box(
        rx.vstack(
            rx.flex(
                badges,
                rx.text(
                    context_label,
                    font_size="0.82rem",
                    color="var(--hub-color-text-muted)",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.vstack(
                title_component,
                rx.text(
                    contract_name,
                    font_family="var(--hub-font-mono)",
                    font_size="0.88rem",
                    color="var(--hub-color-accent-strong)",
                ),
                rx.text(
                    short_summary,
                    color="var(--hub-color-text-muted)",
                ),
                align="start",
                spacing="2",
                width="100%",
            ),
            rx.grid(
                *[_contract_metric(metric) for metric in metrics],
                columns=metric_columns,
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.flex(
                rx.text(
                    "Author: ",
                    author_name,
                    font_size="0.88rem",
                    color="var(--hub-color-text-muted)",
                ),
                tags,
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 252, 246, 0.88)",
        **props,
    )


def _contract_metric(metric: ContractCardMetric) -> rx.Component:
    value_component = (
        metric.value
        if isinstance(metric.value, rx.Component)
        else rx.text(
            metric.value,
            font_size="0.96rem",
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
        padding="0.85rem 1rem",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 249, 239, 0.82)",
    )


__all__ = [
    "ContractCardMetric",
    "contract_card",
    "contract_metadata_badge",
    "contract_rating_summary",
]
