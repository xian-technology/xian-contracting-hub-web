"""Related-contract primitives for public contract detail pages."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components.contract_catalog import contract_metadata_badge
from contracting_hub.components.page_section import page_section


def contract_related_contracts(
    *,
    total_count_label: object,
    outgoing_count_label: object,
    incoming_count_label: object,
    outgoing_relations: object,
    incoming_relations: object,
    has_outgoing_relations: object,
    has_incoming_relations: object,
    **props: object,
) -> rx.Component:
    """Render visible incoming and outgoing contract links."""
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.text(
                        "Linked contracts",
                        font_size="0.75rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        "Relation map",
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Review public dependencies, companions, examples, and "
                            "supersession links without leaving the detail flow."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="44rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    contract_metadata_badge(total_count_label, tone="neutral"),
                    contract_metadata_badge(outgoing_count_label, tone="warning"),
                    contract_metadata_badge(incoming_count_label, tone="success"),
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
                _relation_group(
                    title="Outgoing links",
                    description="Contracts this entry points to, depends on, or supersedes.",
                    count_label=outgoing_count_label,
                    relations=outgoing_relations,
                    has_relations=has_outgoing_relations,
                    empty_title="No outgoing public links",
                    empty_copy=(
                        "This contract does not currently expose public dependencies, "
                        "companions, or replacement links."
                    ),
                ),
                _relation_group(
                    title="Incoming links",
                    description=(
                        "Public contracts that reference this contract from their detail view."
                    ),
                    count_label=incoming_count_label,
                    relations=incoming_relations,
                    has_relations=has_incoming_relations,
                    empty_title="No incoming public links",
                    empty_copy=("No other public contract currently points back to this entry."),
                ),
                columns=rx.breakpoints(initial="1", xl="2"),
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


def _relation_group(
    *,
    title: str,
    description: str,
    count_label: object,
    relations: object,
    has_relations: object,
    empty_title: str,
    empty_copy: str,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading(
                        title,
                        size="4",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        description,
                        color="var(--hub-color-text-muted)",
                        font_size="0.92rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                contract_metadata_badge(count_label, tone="neutral"),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="start"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.cond(
                has_relations,
                rx.vstack(
                    rx.foreach(relations, _related_contract_card),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                _empty_relation_state(empty_title, empty_copy),
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
    )


def _related_contract_card(relation: object) -> rx.Component:
    return rx.link(
        rx.box(
            rx.vstack(
                rx.flex(
                    rx.vstack(
                        rx.heading(
                            relation["display_name"],
                            size="3",
                            font_family="var(--hub-font-display)",
                            color="var(--hub-color-text)",
                        ),
                        rx.text(
                            relation["contract_name"],
                            font_family="var(--hub-font-mono)",
                            font_size="0.92rem",
                            color="var(--hub-color-accent-strong)",
                        ),
                        align="start",
                        gap="var(--hub-space-1)",
                        width="100%",
                    ),
                    rx.flex(
                        contract_metadata_badge(relation["relation_label"], tone="warning"),
                        contract_metadata_badge(
                            relation["primary_category_label"],
                            tone="category",
                        ),
                        contract_metadata_badge(relation["latest_version_label"], tone="neutral"),
                        wrap="wrap",
                        gap="var(--hub-space-2)",
                        justify=rx.breakpoints(initial="start", md="end"),
                        width=rx.breakpoints(initial="100%", md="auto"),
                    ),
                    direction=rx.breakpoints(initial="column", md="row"),
                    align=rx.breakpoints(initial="start", md="start"),
                    justify="between",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                rx.text(
                    relation["short_summary"],
                    color="var(--hub-color-text-muted)",
                    line_height="1.65",
                    width="100%",
                ),
                rx.text(
                    "Author: ",
                    relation["author_label"],
                    color="var(--hub-color-text-muted)",
                    font_size="0.9rem",
                ),
                align="start",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            width="100%",
            padding="var(--hub-space-4)",
            border="1px solid rgba(124, 93, 37, 0.14)",
            border_radius="var(--hub-radius-md)",
            background="rgba(255, 252, 246, 0.88)",
        ),
        href=relation["href"].to(str),
        text_decoration="none",
        color="inherit",
        width="100%",
    )


def _empty_relation_state(title: str, copy: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                title,
                size="3",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                copy,
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border="1px dashed rgba(124, 93, 37, 0.18)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 252, 246, 0.74)",
    )


__all__ = ["contract_related_contracts"]
