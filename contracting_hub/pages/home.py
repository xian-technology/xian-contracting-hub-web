"""Public landing page for the smart contract hub."""

from __future__ import annotations

from datetime import datetime

import reflex as rx

from contracting_hub.components import app_shell, page_section
from contracting_hub.services.homepage import (
    HomePageContractSummary,
    HomePageSnapshot,
    load_public_home_page_snapshot_safe,
)
from contracting_hub.utils.meta import APP_NAME, HOME_BADGE_TEXT, HOME_ROUTE, HOME_TAGLINE

ROUTE = HOME_ROUTE


def _format_calendar_date(value: datetime | None) -> str:
    """Render one UTC-ish timestamp as a compact calendar label."""
    if value is None:
        return "Pending"
    return value.strftime("%b %d, %Y").replace(" 0", " ")


def _format_rating_summary(summary: HomePageContractSummary) -> str:
    """Render one concise rating summary for a contract card."""
    if summary.rating_count == 0 or summary.average_rating is None:
        return "No ratings yet"
    return f"{summary.average_rating:.1f} avg from {summary.rating_count}"


def _resolve_contract_context(summary: HomePageContractSummary, section_key: str) -> str:
    """Return the section-specific context line rendered in each summary card."""
    if section_key == "recently_deployed":
        return f"Last deployed {_format_calendar_date(summary.latest_deployment_at)}"
    if section_key == "featured" and summary.published_at is not None:
        return f"Published {_format_calendar_date(summary.published_at)}"
    return f"Updated {_format_calendar_date(summary.updated_at)}"


def _summary_metric(label: str, value: str) -> rx.Component:
    """Render one compact metric chip inside a homepage card."""
    return rx.box(
        rx.text(
            label,
            font_size="0.72rem",
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
        padding="0.85rem 1rem",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 249, 239, 0.8)",
    )


def _contract_summary_card(
    summary: HomePageContractSummary,
    *,
    section_key: str,
) -> rx.Component:
    """Render one home-page contract card."""
    tag_preview = summary.tag_names[:3]
    status_label = summary.status.value.replace("_", " ").title()

    return rx.box(
        rx.vstack(
            rx.flex(
                rx.flex(
                    rx.badge(
                        summary.primary_category_name or "Uncategorized",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                    ),
                    rx.badge(
                        status_label,
                        radius="full",
                        variant="soft",
                        color_scheme="grass" if summary.status.value == "published" else "orange",
                    ),
                    *(
                        [
                            rx.badge(
                                "Featured",
                                radius="full",
                                variant="soft",
                                color_scheme="gold",
                            )
                        ]
                        if summary.featured
                        else []
                    ),
                    wrap="wrap",
                    gap="var(--hub-space-2)",
                ),
                rx.text(
                    _resolve_contract_context(summary, section_key),
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
                rx.heading(
                    summary.display_name,
                    size="4",
                    font_family="var(--hub-font-display)",
                    letter_spacing="-0.04em",
                    color="var(--hub-color-text)",
                ),
                rx.text(
                    summary.contract_name,
                    font_family="var(--hub-font-mono)",
                    font_size="0.88rem",
                    color="var(--hub-color-accent-strong)",
                ),
                rx.text(
                    summary.short_summary,
                    color="var(--hub-color-text-muted)",
                ),
                align="start",
                spacing="2",
                width="100%",
            ),
            rx.grid(
                _summary_metric(
                    "Version",
                    summary.semantic_version or "No published version",
                ),
                _summary_metric("Stars", str(summary.star_count)),
                _summary_metric("Rating", _format_rating_summary(summary)),
                _summary_metric("Deploys", str(summary.deployment_count)),
                columns=rx.breakpoints(initial="1", sm="2"),
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.flex(
                rx.text(
                    f"Author: {summary.author_name or 'Curated entry'}",
                    font_size="0.88rem",
                    color="var(--hub-color-text-muted)",
                ),
                rx.flex(
                    *[
                        rx.badge(
                            tag,
                            radius="full",
                            variant="soft",
                            color_scheme="gray",
                        )
                        for tag in tag_preview
                    ],
                    wrap="wrap",
                    gap="var(--hub-space-2)",
                ),
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
    )


def _empty_section_copy(title: str, body: str) -> rx.Component:
    """Render the default empty state used by homepage sections."""
    return rx.box(
        rx.vstack(
            rx.heading(
                title,
                size="3",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                body,
                color="var(--hub-color-text-muted)",
            ),
            align="start",
            gap="var(--hub-space-2)",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px dashed var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.65)",
    )


def _home_section(
    title: str,
    eyebrow: str,
    description: str,
    summaries: tuple[HomePageContractSummary, ...],
    *,
    section_key: str,
    test_id: str,
    empty_title: str,
    empty_body: str,
) -> rx.Component:
    """Render one section of homepage contract summaries."""
    content = (
        rx.vstack(
            *[_contract_summary_card(summary, section_key=section_key) for summary in summaries],
            width="100%",
            gap="var(--hub-space-4)",
        )
        if summaries
        else _empty_section_copy(empty_title, empty_body)
    )

    return page_section(
        rx.vstack(
            rx.vstack(
                rx.badge(
                    eyebrow,
                    radius="full",
                    variant="soft",
                    color_scheme="bronze",
                    width="fit-content",
                ),
                rx.heading(
                    title,
                    size="6",
                    font_family="var(--hub-font-display)",
                    letter_spacing="-0.05em",
                    color="var(--hub-color-text)",
                ),
                rx.text(
                    description,
                    color="var(--hub-color-text-muted)",
                    max_width="34rem",
                ),
                align="start",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            content,
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        custom_attrs={"data-testid": test_id},
    )


def _home_overview(snapshot: HomePageSnapshot) -> rx.Component:
    """Render the top-level homepage overview panel."""
    return page_section(
        rx.grid(
            rx.vstack(
                rx.badge(
                    "Public catalog",
                    radius="full",
                    variant="soft",
                    color_scheme="bronze",
                    width="fit-content",
                ),
                rx.heading(
                    "Curated contracts surfaced by signal, freshness, and deployment activity.",
                    size="7",
                    font_family="var(--hub-font-display)",
                    letter_spacing="-0.06em",
                    color="var(--hub-color-text)",
                    max_width="32rem",
                ),
                rx.text(
                    (
                        "Featured entries highlight editorial picks, trending ranks by public "
                        "engagement, recently updated tracks fresh releases, and recently "
                        "deployed surfaces contracts that are actively reaching playgrounds."
                    ),
                    size="4",
                    color="var(--hub-color-text-muted)",
                    max_width="38rem",
                ),
                align="start",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.grid(
                _summary_metric("Featured", str(len(snapshot.featured_contracts))),
                _summary_metric("Trending", str(len(snapshot.trending_contracts))),
                _summary_metric("Updated", str(len(snapshot.recently_updated_contracts))),
                _summary_metric("Deployed", str(len(snapshot.recently_deployed_contracts))),
                columns="2",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", lg="2"),
            gap="var(--hub-space-6)",
            width="100%",
            align_items="center",
        ),
        custom_attrs={"data-testid": "home-overview"},
    )


def index() -> rx.Component:
    """Render the public homepage with the core discovery sections."""
    snapshot = load_public_home_page_snapshot_safe()
    return app_shell(
        _home_overview(snapshot),
        rx.grid(
            _home_section(
                "Featured Contracts",
                "Editorial Picks",
                "Curated contracts the hub wants every Xian developer to notice first.",
                snapshot.featured_contracts,
                section_key="featured",
                test_id="home-section-featured",
                empty_title="No featured contracts yet",
                empty_body=(
                    "Promote published contracts from the admin workspace to fill this shelf."
                ),
            ),
            _home_section(
                "Trending Now",
                "Public Momentum",
                (
                    "Sorted by aggregate stars, ratings, and deployment activity "
                    "across published contracts."
                ),
                snapshot.trending_contracts,
                section_key="trending",
                test_id="home-section-trending",
                empty_title="No trending contracts yet",
                empty_body="Published contracts will appear here once the hub records engagement.",
            ),
            _home_section(
                "Recently Updated",
                "Fresh Releases",
                (
                    "The latest published or deprecated contracts to receive new "
                    "source, metadata, or release updates."
                ),
                snapshot.recently_updated_contracts,
                section_key="recently_updated",
                test_id="home-section-updated",
                empty_title="No recent updates yet",
                empty_body="Publish a contract version to start building this timeline.",
            ),
            _home_section(
                "Recently Deployed",
                "Playground Activity",
                (
                    "Contracts with the most recent non-failed deployment handoffs "
                    "to the Xian playground."
                ),
                snapshot.recently_deployed_contracts,
                section_key="recently_deployed",
                test_id="home-section-deployed",
                empty_title="No deployments recorded yet",
                empty_body=(
                    "Deployment history will populate here after authenticated users "
                    "send contracts to a playground."
                ),
            ),
            columns=rx.breakpoints(initial="1", xl="2"),
            gap="var(--hub-space-5)",
            width="100%",
        ),
        page_kicker=HOME_BADGE_TEXT,
        page_title=APP_NAME,
        page_intro=HOME_TAGLINE,
    )
