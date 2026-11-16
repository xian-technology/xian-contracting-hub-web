"""Compact catalog metric used by home and leaderboard summaries."""

import reflex as rx


def catalog_metric(label: str, value: object) -> rx.Component:
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
            font_size="0.95rem",
            font_weight="600",
            color="var(--hub-color-text)",
        ),
        padding="0.75rem 0.85rem",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-sm)",
        background="rgba(255, 250, 242, 0.7)",
        class_name="hub-metric",
    )
