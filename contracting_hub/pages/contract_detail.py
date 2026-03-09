"""Public contract-detail page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import (
    ContractCardMetric,
    app_shell,
    contract_detail_header,
    contract_lint_results_panel,
    contract_metadata_badge,
    contract_rating_summary,
    contract_source_viewer,
    contract_version_diff_viewer,
    contract_version_history,
    page_section,
)
from contracting_hub.states import ContractDetailState
from contracting_hub.utils.meta import CONTRACT_DETAIL_ROUTE

ROUTE = CONTRACT_DETAIL_ROUTE
ON_LOAD = ContractDetailState.load_page


def _status_badge(label, color_scheme) -> rx.Component:
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme=color_scheme,
        padding_x="0.85rem",
        padding_y="0.35rem",
    )


def _header_badges() -> rx.Component:
    return rx.flex(
        contract_metadata_badge(ContractDetailState.primary_category_label, tone="category"),
        _status_badge(
            ContractDetailState.contract_status_label,
            ContractDetailState.contract_status_color_scheme,
        ),
        _status_badge(
            ContractDetailState.version_status_label,
            ContractDetailState.version_status_color_scheme,
        ),
        rx.cond(
            ContractDetailState.featured,
            contract_metadata_badge("Featured", tone="featured"),
        ),
        rx.cond(
            ContractDetailState.has_network,
            _status_badge(ContractDetailState.network_label, "gray"),
        ),
        rx.cond(
            ContractDetailState.has_license,
            _status_badge(ContractDetailState.license_label, "gray"),
        ),
        wrap="wrap",
        gap="var(--hub-space-2)",
    )


def _taxonomy() -> rx.Component:
    return rx.vstack(
        rx.vstack(
            rx.text(
                "Categories",
                font_size="0.75rem",
                font_weight="600",
                text_transform="uppercase",
                letter_spacing="0.08em",
                color="var(--hub-color-text-muted)",
            ),
            rx.flex(
                rx.foreach(
                    ContractDetailState.category_labels,
                    lambda category: contract_metadata_badge(category, tone="category"),
                ),
                wrap="wrap",
                gap="var(--hub-space-2)",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        rx.cond(
            ContractDetailState.has_tags,
            rx.vstack(
                rx.text(
                    "Tags",
                    font_size="0.75rem",
                    font_weight="600",
                    text_transform="uppercase",
                    letter_spacing="0.08em",
                    color="var(--hub-color-text-muted)",
                ),
                rx.flex(
                    rx.foreach(
                        ContractDetailState.tag_labels,
                        lambda tag: contract_metadata_badge(tag, tone="neutral"),
                    ),
                    wrap="wrap",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                align="start",
                gap="var(--hub-space-2)",
                width="100%",
            ),
        ),
        align="start",
        gap="var(--hub-space-4)",
        width="100%",
    )


def _author_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(
                "Author",
                font_size="0.75rem",
                font_weight="600",
                text_transform="uppercase",
                letter_spacing="0.08em",
                color="var(--hub-color-text-muted)",
            ),
            rx.hstack(
                rx.box(
                    ContractDetailState.author_initials,
                    width="3rem",
                    height="3rem",
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    border_radius="999px",
                    border="1px solid rgba(124, 93, 37, 0.18)",
                    background=(
                        "linear-gradient(135deg, rgba(233, 208, 156, 0.45) 0%, "
                        "rgba(255, 242, 213, 0.92) 100%)"
                    ),
                    color="var(--hub-color-accent-strong)",
                    font_family="var(--hub-font-display)",
                    font_weight="700",
                    flex_shrink="0",
                ),
                rx.vstack(
                    rx.text(
                        ContractDetailState.author_name,
                        font_weight="600",
                        color="var(--hub-color-text)",
                    ),
                    rx.cond(
                        ContractDetailState.has_author_secondary,
                        rx.text(
                            ContractDetailState.author_secondary,
                            color="var(--hub-color-text-muted)",
                            font_size="0.9rem",
                        ),
                    ),
                    align="start",
                    spacing="1",
                ),
                align="center",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.cond(
                ContractDetailState.has_author_bio,
                rx.text(
                    ContractDetailState.author_bio,
                    color="var(--hub-color-text-muted)",
                ),
            ),
            rx.cond(
                ContractDetailState.has_author_links,
                rx.flex(
                    rx.foreach(
                        ContractDetailState.author_links,
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
        background="rgba(255, 248, 236, 0.76)",
    )


def _header_actions() -> rx.Component:
    return rx.vstack(
        rx.text(
            "Primary actions",
            font_size="0.75rem",
            font_weight="600",
            text_transform="uppercase",
            letter_spacing="0.08em",
            color="var(--hub-color-text-muted)",
        ),
        rx.flex(
            rx.link(
                rx.button("Browse catalog", size="3", variant="solid"),
                href=ContractDetailState.browse_href,
                text_decoration="none",
            ),
            rx.cond(
                ContractDetailState.has_documentation_url,
                rx.link(
                    rx.button("Documentation", size="3", variant="soft"),
                    href=ContractDetailState.documentation_url,
                    target="_blank",
                    rel="noopener noreferrer",
                    text_decoration="none",
                ),
            ),
            rx.cond(
                ContractDetailState.has_source_repository_url,
                rx.link(
                    rx.button("Source repo", size="3", variant="soft"),
                    href=ContractDetailState.source_repository_url,
                    target="_blank",
                    rel="noopener noreferrer",
                    text_decoration="none",
                ),
            ),
            wrap="wrap",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        align="start",
        gap="var(--hub-space-2)",
        width=rx.breakpoints(initial="100%", lg="auto"),
    )


def _detail_metrics() -> tuple[ContractCardMetric, ...]:
    return (
        ContractCardMetric("Version", ContractDetailState.version_label),
        ContractCardMetric("Updated", ContractDetailState.updated_label),
        ContractCardMetric("Stars", ContractDetailState.star_count),
        ContractCardMetric(
            "Rating",
            contract_rating_summary(
                headline=ContractDetailState.rating_headline,
                detail=ContractDetailState.rating_detail,
                empty=ContractDetailState.rating_empty,
            ),
        ),
    )


def _detail_header() -> rx.Component:
    return contract_detail_header(
        badges=_header_badges(),
        context_label=ContractDetailState.header_context_label,
        display_name=ContractDetailState.display_name,
        contract_name=ContractDetailState.contract_name,
        short_summary=ContractDetailState.short_summary,
        long_description=ContractDetailState.long_description,
        taxonomy=_taxonomy(),
        metrics=_detail_metrics(),
        author_panel=_author_panel(),
        actions=_header_actions(),
        custom_attrs={"data-testid": "contract-detail-header"},
    )


def _source_viewer() -> rx.Component:
    return contract_source_viewer(
        source_code=ContractDetailState.selected_version_source_code,
        source_download_url=ContractDetailState.source_download_url,
        source_download_filename=ContractDetailState.source_download_filename,
        version_label=ContractDetailState.version_label,
        line_count_label=ContractDetailState.source_line_count_label,
        has_source_code=ContractDetailState.has_source_code,
        custom_attrs={"data-testid": "contract-source-viewer"},
    )


def _diff_viewer() -> rx.Component:
    return contract_version_diff_viewer(
        selected_version=ContractDetailState.version_label,
        previous_version=ContractDetailState.selected_version_diff_previous_version,
        has_previous_version=ContractDetailState.selected_version_diff_has_previous_version,
        has_diff_content=ContractDetailState.has_selected_version_diff_content,
        added_lines_label=ContractDetailState.selected_version_diff_added_lines_label,
        removed_lines_label=ContractDetailState.selected_version_diff_removed_lines_label,
        line_delta_label=ContractDetailState.selected_version_diff_line_delta_label,
        hunk_count_label=ContractDetailState.selected_version_diff_hunk_count_label,
        context_lines_label=ContractDetailState.selected_version_diff_context_lines_label,
        unified_diff=ContractDetailState.selected_version_diff_unified_text,
        custom_attrs={"data-testid": "contract-version-diff-viewer"},
    )


def _lint_results_panel() -> rx.Component:
    return contract_lint_results_panel(
        selected_version=ContractDetailState.version_label,
        has_lint_report=ContractDetailState.selected_version_has_lint_report,
        lint_status_label=ContractDetailState.selected_version_lint_status_label,
        lint_status_color_scheme=ContractDetailState.selected_version_lint_status_color_scheme,
        lint_summary_copy=ContractDetailState.selected_version_lint_summary_copy,
        issue_count_label=ContractDetailState.selected_version_lint_issue_count_label,
        error_count_label=ContractDetailState.selected_version_lint_error_count_label,
        warning_count_label=ContractDetailState.selected_version_lint_warning_count_label,
        info_count_label=ContractDetailState.selected_version_lint_info_count_label,
        findings=ContractDetailState.selected_version_lint_findings,
        has_findings=ContractDetailState.has_selected_version_lint_findings,
        custom_attrs={"data-testid": "contract-lint-results-panel"},
    )


def _version_history() -> rx.Component:
    return contract_version_history(
        versions=ContractDetailState.available_versions,
        version_count_label=ContractDetailState.version_count_label,
        selected_version=ContractDetailState.version_label,
        selected_version_status_label=ContractDetailState.version_status_label,
        selected_version_status_color_scheme=ContractDetailState.version_status_color_scheme,
        selected_version_published_label=ContractDetailState.published_label,
        selected_version_changelog=ContractDetailState.selected_version_changelog,
        has_selected_version_changelog=ContractDetailState.has_selected_version_changelog,
        selected_version_is_latest_public=ContractDetailState.selected_version_is_latest_public,
        custom_attrs={"data-testid": "contract-version-history"},
    )


def _loading_state() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.heading(
                "Loading contract details...",
                size="5",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                "The contract header is being prepared from the current route.",
                color="var(--hub-color-text-muted)",
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        custom_attrs={"data-testid": "contract-detail-loading"},
    )


def _missing_state() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.heading(
                "Contract not found",
                size="5",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                "This slug does not resolve to a published contract in the public catalog.",
                color="var(--hub-color-text-muted)",
                max_width="34rem",
            ),
            rx.link(
                rx.button("Browse published contracts", size="3", variant="solid"),
                href=ContractDetailState.browse_href,
                text_decoration="none",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        custom_attrs={"data-testid": "contract-detail-missing"},
    )


def index() -> rx.Component:
    """Render the public contract detail shell and header surface."""
    return app_shell(
        rx.box(
            rx.cond(
                ContractDetailState.is_ready,
                rx.vstack(
                    _detail_header(),
                    _version_history(),
                    _lint_results_panel(),
                    _diff_viewer(),
                    _source_viewer(),
                    align="start",
                    gap="var(--hub-space-7)",
                    width="100%",
                ),
                rx.cond(
                    ContractDetailState.is_missing,
                    _missing_state(),
                    _loading_state(),
                ),
            ),
            width="100%",
            custom_attrs={"data-testid": "contract-detail-page"},
        )
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
