"""Public landing page for the smart contract hub."""

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
from contracting_hub.services.homepage import (
    HomePageContractSummary,
    HomePageSnapshot,
    load_public_home_page_snapshot_safe,
)
from contracting_hub.states import AuthState
from contracting_hub.utils import build_contract_rating_display, format_contract_calendar_date
from contracting_hub.utils.meta import (
    APP_NAME,
    HOME_BADGE_TEXT,
    HOME_ROUTE,
    HOME_TAGLINE,
    build_contract_detail_path,
)

ROUTE = HOME_ROUTE
ON_LOAD = AuthState.sync_auth_state


def _resolve_contract_context(summary: HomePageContractSummary, section_key: str) -> str:
    """Return the section-specific context line rendered in each summary card."""
    if section_key == "recently_deployed":
        return f"Last deployed {format_contract_calendar_date(summary.latest_deployment_at)}"
    if section_key == "featured" and summary.published_at is not None:
        return f"Published {format_contract_calendar_date(summary.published_at)}"
    return f"Updated {format_contract_calendar_date(summary.updated_at)}"


def _summary_metric(label: str, value: str) -> rx.Component:
    """Render one compact metric chip inside a homepage card."""
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


def _contract_summary_card(
    summary: HomePageContractSummary,
    *,
    section_key: str,
) -> rx.Component:
    """Render one home-page contract card."""
    tag_preview = summary.tag_names[:3]
    status_label = summary.status.value.replace("_", " ").title()
    rating_display = build_contract_rating_display(
        average_rating=summary.average_rating,
        rating_count=summary.rating_count,
    )
    return contract_card(
        badges=rx.flex(
            contract_metadata_badge(
                summary.primary_category_name or "Uncategorized",
                tone="category",
            ),
            contract_metadata_badge(
                status_label,
                tone="success" if summary.status.value == "published" else "warning",
            ),
            *([contract_metadata_badge("Featured", tone="featured")] if summary.featured else []),
            wrap="wrap",
            gap="var(--hub-space-2)",
        ),
        context_label=_resolve_contract_context(summary, section_key),
        display_name=summary.display_name,
        contract_name=summary.contract_name,
        short_summary=summary.short_summary,
        metrics=(
            ContractCardMetric("Version", summary.semantic_version or "No published version"),
            ContractCardMetric("Stars", str(summary.star_count)),
            ContractCardMetric(
                "Rating",
                contract_rating_summary(
                    headline=rating_display.headline,
                    detail=rating_display.detail,
                    empty=rating_display.empty,
                ),
            ),
            ContractCardMetric("Deploys", str(summary.deployment_count)),
        ),
        author_name=summary.author_name or "Curated entry",
        tags=rx.flex(
            *[contract_metadata_badge(tag, tone="neutral") for tag in tag_preview],
            wrap="wrap",
            gap="var(--hub-space-2)",
        ),
        metric_columns=rx.breakpoints(initial="1", sm="2"),
        href=build_contract_detail_path(summary.slug),
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
                rx.heading(
                    "Curated contracts surfaced by signal, freshness, and deployment activity.",
                    size="6",
                    font_family="var(--hub-font-display)",
                    letter_spacing="-0.04em",
                    color="var(--hub-color-text)",
                    max_width="32rem",
                ),
                rx.text(
                    (
                        "Featured entries highlight editorial picks, trending ranks by "
                        "engagement, recently updated tracks fresh releases, and recently "
                        "deployed surfaces contracts reaching playgrounds."
                    ),
                    color="var(--hub-color-text-muted)",
                    max_width="38rem",
                    font_size="0.95rem",
                    line_height="1.6",
                ),
                align="start",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.grid(
                _summary_metric("Featured", str(len(snapshot.featured_contracts))),
                _summary_metric("Trending", str(len(snapshot.trending_contracts))),
                _summary_metric("Updated", str(len(snapshot.recently_updated_contracts))),
                _summary_metric("Deployed", str(len(snapshot.recently_deployed_contracts))),
                columns="2",
                gap="var(--hub-space-2)",
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", lg="3fr 2fr"),
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
