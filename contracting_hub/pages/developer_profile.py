"""Public developer-profile page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import (
    ContractCardMetric,
    app_shell,
    contract_card,
    contract_metadata_badge,
    contract_rating_summary,
    page_section,
)
from contracting_hub.states import AuthState, DeveloperProfileState
from contracting_hub.utils.meta import DEVELOPER_PROFILE_ROUTE

ROUTE = DEVELOPER_PROFILE_ROUTE
ON_LOAD = [AuthState.sync_auth_state, DeveloperProfileState.load_page]


def _summary_card(label: str, value: object, helper: object) -> rx.Component:
    value_component = (
        value
        if isinstance(value, rx.Component)
        else rx.text(
            value,
            font_size="1.3rem",
            font_weight="700",
            color="var(--hub-color-text)",
        )
    )
    return rx.box(
        rx.vstack(
            rx.text(
                label,
                font_size="0.74rem",
                font_weight="600",
                text_transform="uppercase",
                letter_spacing="0.08em",
                color="var(--hub-color-text-muted)",
            ),
            value_component,
            rx.text(
                helper,
                color="var(--hub-color-text-muted)",
                font_size="0.9rem",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 249, 239, 0.82)",
    )


def _profile_overview() -> rx.Component:
    return page_section(
        rx.grid(
            rx.box(
                rx.vstack(
                    rx.badge(
                        "Profile overview",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.flex(
                        rx.avatar(
                            fallback=DeveloperProfileState.avatar_fallback,
                            size="7",
                            radius="full",
                            color_scheme="bronze",
                            variant="soft",
                        ),
                        rx.vstack(
                            rx.heading(
                                DeveloperProfileState.page_title,
                                size="6",
                                font_family="var(--hub-font-display)",
                                letter_spacing="-0.05em",
                                color="var(--hub-color-text)",
                            ),
                            rx.text(
                                DeveloperProfileState.profile_secondary,
                                color="var(--hub-color-text-muted)",
                                font_size="1rem",
                            ),
                            align="start",
                            gap="var(--hub-space-1)",
                            width="100%",
                        ),
                        direction=rx.breakpoints(initial="column", sm="row"),
                        align=rx.breakpoints(initial="start", sm="center"),
                        gap="var(--hub-space-4)",
                        width="100%",
                    ),
                    rx.cond(
                        DeveloperProfileState.has_bio,
                        rx.text(
                            DeveloperProfileState.bio,
                            color="var(--hub-color-text-muted)",
                            max_width="34rem",
                        ),
                    ),
                    rx.cond(
                        DeveloperProfileState.has_profile_links,
                        rx.flex(
                            rx.foreach(
                                DeveloperProfileState.profile_links,
                                lambda link: rx.link(
                                    link["label"],
                                    href=link["href"],
                                    target="_blank",
                                    rel="noopener noreferrer",
                                    color="var(--hub-color-accent-strong)",
                                    text_decoration="underline",
                                ),
                            ),
                            wrap="wrap",
                            gap="var(--hub-space-3)",
                            width="100%",
                        ),
                    ),
                    align="start",
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                width="100%",
                padding="var(--hub-space-5)",
                border="1px solid rgba(124, 93, 37, 0.14)",
                border_radius="var(--hub-radius-md)",
                background="rgba(255, 248, 236, 0.78)",
            ),
            rx.vstack(
                rx.flex(
                    rx.badge(
                        "Published signals",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.badge(
                        DeveloperProfileState.activity_window_label,
                        radius="full",
                        variant="soft",
                        color_scheme="gray",
                        width="fit-content",
                    ),
                    wrap="wrap",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.grid(
                    _summary_card(
                        "Published contracts",
                        DeveloperProfileState.published_contract_count_text,
                        "Contracts currently counted in public KPI totals.",
                    ),
                    _summary_card(
                        "Stars received",
                        DeveloperProfileState.star_total_text,
                        "Favorites collected across published contracts.",
                    ),
                    _summary_card(
                        "Weighted rating",
                        contract_rating_summary(
                            headline=DeveloperProfileState.rating_headline,
                            detail=DeveloperProfileState.rating_detail,
                            empty=DeveloperProfileState.rating_empty,
                        ),
                        "Aggregate score across published contract ratings.",
                    ),
                    _summary_card(
                        "Deployments",
                        DeveloperProfileState.deployment_count_text,
                        "Recorded playground handoffs across published releases.",
                    ),
                    columns=rx.breakpoints(initial="1", md="2"),
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                _summary_card(
                    "Recent activity",
                    DeveloperProfileState.recent_activity_count_text,
                    DeveloperProfileState.recent_activity_breakdown,
                ),
                align="start",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", xl="2"),
            gap="var(--hub-space-5)",
            width="100%",
            align_items="start",
        ),
        custom_attrs={"data-testid": "developer-profile-overview"},
    )


def _authored_contract_card(card) -> rx.Component:
    return contract_card(
        badges=rx.flex(
            contract_metadata_badge(card["category_label"], tone="category"),
            rx.cond(
                card["status_is_published"],
                contract_metadata_badge(card["status_label"], tone="success"),
                contract_metadata_badge(card["status_label"], tone="warning"),
            ),
            rx.cond(
                card["featured"],
                contract_metadata_badge("Featured", tone="featured"),
            ),
            wrap="wrap",
            gap="var(--hub-space-2)",
        ),
        context_label=card["updated_context"],
        display_name=card["display_name"],
        contract_name=card["contract_name"],
        short_summary=card["short_summary"],
        metrics=(
            ContractCardMetric("Version", card["version_label"]),
            ContractCardMetric("Stars", card["star_count"]),
            ContractCardMetric(
                "Rating",
                contract_rating_summary(
                    headline=card["rating_headline"],
                    detail=card["rating_detail"],
                    empty=card["rating_empty"],
                ),
            ),
            ContractCardMetric("Deploys", card["deployment_count"]),
        ),
        author_name=DeveloperProfileState.page_title,
        tags=rx.flex(
            rx.foreach(
                card["tag_preview"],
                lambda tag: contract_metadata_badge(tag, tone="neutral"),
            ),
            wrap="wrap",
            gap="var(--hub-space-2)",
        ),
        metric_columns=rx.breakpoints(initial="1", sm="2"),
        href=card["detail_href"],
        custom_attrs={"data-testid": "developer-authored-contract-card"},
    )


def _authored_contracts_empty_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "No public authored contracts yet",
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                (
                    "Draft work stays private, so this profile will populate after the first "
                    "public contract is published."
                ),
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            rx.link(
                "Browse the public catalog",
                href=DeveloperProfileState.browse_href,
                color="var(--hub-color-accent-strong)",
                text_decoration="underline",
            ),
            align="start",
            gap="var(--hub-space-3)",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px dashed var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.68)",
    )


def _authored_contracts_section() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.badge(
                        "Authored contracts",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.heading(
                        DeveloperProfileState.authored_contract_count_label,
                        size="6",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.05em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Public releases are ordered by the latest visible catalog update so "
                            "fresh work stays near the top."
                        ),
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                DeveloperProfileState.has_authored_contracts,
                rx.vstack(
                    rx.foreach(
                        DeveloperProfileState.authored_contracts,
                        _authored_contract_card,
                    ),
                    width="100%",
                    gap="var(--hub-space-4)",
                ),
                _authored_contracts_empty_state(),
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        custom_attrs={"data-testid": "developer-profile-contracts"},
    )


def _loading_state() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.heading(
                "Loading developer profile",
                size="5",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                "Resolving public profile data and authored contract metrics.",
                color="var(--hub-color-text-muted)",
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        custom_attrs={"data-testid": "developer-profile-loading"},
    )


def _missing_state() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.heading(
                "Developer not found",
                size="5",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                "This public developer profile does not exist or is not yet available.",
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            rx.link(
                rx.button("Browse public contracts", size="3", variant="solid"),
                href=DeveloperProfileState.browse_href,
                text_decoration="none",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        custom_attrs={"data-testid": "developer-profile-missing"},
    )


def index() -> rx.Component:
    """Render the public developer-profile shell."""
    return app_shell(
        rx.box(
            rx.cond(
                DeveloperProfileState.is_ready,
                rx.vstack(
                    _profile_overview(),
                    _authored_contracts_section(),
                    align="start",
                    gap="var(--hub-space-7)",
                    width="100%",
                ),
                rx.cond(
                    DeveloperProfileState.is_missing,
                    _missing_state(),
                    _loading_state(),
                ),
            ),
            width="100%",
            custom_attrs={"data-testid": "developer-profile-page"},
        ),
        page_kicker="Developer identity",
        page_title=DeveloperProfileState.page_title,
        page_intro=DeveloperProfileState.page_intro,
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
