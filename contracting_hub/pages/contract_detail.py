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
    contract_related_contracts,
    contract_source_viewer,
    contract_version_diff_viewer,
    contract_version_history,
    page_section,
)
from contracting_hub.states import AuthState, ContractDetailState
from contracting_hub.utils.meta import CONTRACT_DETAIL_ROUTE, PROFILE_SETTINGS_ROUTE

ROUTE = CONTRACT_DETAIL_ROUTE
ON_LOAD = [AuthState.sync_auth_state, ContractDetailState.load_page]


def _status_badge(label, color_scheme) -> rx.Component:
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme=color_scheme,
        padding_x="0.85rem",
        padding_y="0.35rem",
    )


def _field_label(label: str) -> rx.Component:
    return rx.text(
        label,
        font_size="0.75rem",
        font_weight="600",
        text_transform="uppercase",
        letter_spacing="0.08em",
        color="var(--hub-color-text-muted)",
    )


def _field_error(message) -> rx.Component:
    return rx.cond(
        message != "",
        rx.text(
            message,
            color="tomato",
            font_size="0.9rem",
        ),
    )


def _surface_input(**props: object) -> rx.Component:
    return rx.input(
        size="3",
        variant="surface",
        width="100%",
        **props,
    )


def _select_style() -> dict[str, str]:
    return {
        "width": "100%",
        "padding": "0.85rem 1rem",
        "border": "1px solid var(--hub-color-line)",
        "borderRadius": "var(--hub-radius-md)",
        "background": "rgba(255, 252, 246, 0.98)",
        "color": "var(--hub-color-text)",
        "fontFamily": "var(--hub-font-body)",
        "fontSize": "0.98rem",
        "outline": "none",
        "boxShadow": "inset 0 1px 0 rgba(255, 255, 255, 0.75)",
    }


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


def _feedback_banner(message, *, tone: str, test_id: str) -> rx.Component:
    color = "tomato" if tone == "error" else "var(--hub-color-accent-strong)"
    border = (
        "1px solid rgba(191, 61, 48, 0.22)"
        if tone == "error"
        else "1px solid rgba(142, 89, 30, 0.22)"
    )
    background = "rgba(255, 244, 242, 0.95)" if tone == "error" else "rgba(255, 249, 239, 0.96)"
    return rx.cond(
        message != "",
        rx.box(
            rx.text(
                message,
                color=color,
                font_weight="600",
            ),
            width="100%",
            padding="0.9rem 1rem",
            border=border,
            border_radius="var(--hub-radius-md)",
            background=background,
            custom_attrs={"data-testid": test_id},
        ),
    )


def _star_button() -> rx.Component:
    starred_button = rx.button(
        ContractDetailState.star_button_label,
        type="button",
        size="3",
        variant="solid",
        color_scheme="bronze",
        on_click=ContractDetailState.toggle_star,
        disabled=ContractDetailState.star_pending,
        custom_attrs={"data-testid": "contract-star-toggle"},
    )
    default_button = rx.button(
        ContractDetailState.star_button_label,
        type="button",
        size="3",
        variant="soft",
        color_scheme="gray",
        on_click=ContractDetailState.toggle_star,
        disabled=ContractDetailState.star_pending,
        custom_attrs={"data-testid": "contract-star-toggle"},
    )
    return rx.cond(
        ContractDetailState.starred_by_current_user,
        starred_button,
        default_button,
    )


def _rating_button(score: int) -> rx.Component:
    selected_button = rx.button(
        str(score),
        type="button",
        size="2",
        variant="solid",
        color_scheme="bronze",
        on_click=ContractDetailState.submit_rating(score),
        disabled=ContractDetailState.rating_pending,
        custom_attrs={"data-testid": f"contract-rating-option-{score}"},
    )
    unselected_button = rx.button(
        str(score),
        type="button",
        size="2",
        variant="soft",
        color_scheme="gray",
        on_click=ContractDetailState.submit_rating(score),
        disabled=ContractDetailState.rating_pending,
        custom_attrs={"data-testid": f"contract-rating-option-{score}"},
    )
    return rx.cond(
        ContractDetailState.current_user_rating_score == score,
        selected_button,
        unselected_button,
    )


def _engagement_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.vstack(
                rx.text(
                    "Engagement",
                    font_size="0.75rem",
                    font_weight="600",
                    text_transform="uppercase",
                    letter_spacing="0.08em",
                    color="var(--hub-color-text-muted)",
                ),
                rx.text(
                    "Save this release or rate it inline without leaving the detail page.",
                    color="var(--hub-color-text-muted)",
                    font_size="0.92rem",
                ),
                align="start",
                gap="var(--hub-space-2)",
                width="100%",
            ),
            _feedback_banner(
                ContractDetailState.engagement_success_message,
                tone="success",
                test_id="contract-engagement-success",
            ),
            _feedback_banner(
                ContractDetailState.engagement_error_message,
                tone="error",
                test_id="contract-engagement-error",
            ),
            rx.cond(
                ContractDetailState.engagement_login_prompt_message != "",
                _feedback_banner(
                    ContractDetailState.engagement_login_prompt_message,
                    tone="success",
                    test_id="contract-engagement-login-prompt",
                ),
            ),
            rx.box(
                rx.vstack(
                    _star_button(),
                    rx.text(
                        ContractDetailState.star_button_helper,
                        color="var(--hub-color-text)",
                        font_weight="500",
                    ),
                    rx.text(
                        ContractDetailState.star_total_label,
                        color="var(--hub-color-text-muted)",
                        font_size="0.9rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                width="100%",
                padding="var(--hub-space-4)",
                border="1px solid rgba(124, 93, 37, 0.14)",
                border_radius="var(--hub-radius-md)",
                background="rgba(255, 252, 246, 0.84)",
            ),
            rx.box(
                rx.vstack(
                    rx.text(
                        "Rate this release",
                        font_weight="600",
                        color="var(--hub-color-text)",
                    ),
                    rx.flex(
                        _rating_button(1),
                        _rating_button(2),
                        _rating_button(3),
                        _rating_button(4),
                        _rating_button(5),
                        wrap="wrap",
                        gap="var(--hub-space-2)",
                        width="100%",
                    ),
                    rx.cond(
                        ContractDetailState.is_authenticated,
                        rx.text(
                            ContractDetailState.current_user_rating_label,
                            color="var(--hub-color-text-muted)",
                            font_size="0.9rem",
                        ),
                        rx.text(
                            ContractDetailState.engagement_login_copy,
                            color="var(--hub-color-text-muted)",
                            font_size="0.9rem",
                        ),
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                width="100%",
                padding="var(--hub-space-4)",
                border="1px solid rgba(124, 93, 37, 0.14)",
                border_radius="var(--hub-radius-md)",
                background="rgba(255, 252, 246, 0.84)",
            ),
            rx.cond(
                ContractDetailState.is_authenticated,
                rx.fragment(),
                rx.button(
                    "Log in to engage",
                    type="button",
                    size="3",
                    variant="soft",
                    color_scheme="bronze",
                    on_click=ContractDetailState.begin_engagement_login,
                    custom_attrs={"data-testid": "contract-engagement-login"},
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
        background="rgba(255, 248, 236, 0.82)",
        custom_attrs={"data-testid": "contract-engagement-panel"},
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
            rx.cond(
                ContractDetailState.is_authenticated,
                rx.button(
                    "Deploy version",
                    type="button",
                    size="3",
                    variant="solid",
                    color_scheme="bronze",
                    on_click=ContractDetailState.open_deployment_drawer,
                    custom_attrs={"data-testid": "contract-deployment-trigger"},
                ),
                rx.button(
                    "Log in to deploy",
                    type="button",
                    size="3",
                    variant="solid",
                    color_scheme="bronze",
                    on_click=ContractDetailState.begin_deployment_login,
                    custom_attrs={"data-testid": "contract-deployment-trigger"},
                ),
            ),
            rx.link(
                rx.button("Browse catalog", size="3", variant="soft"),
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
        _engagement_panel(),
        align="start",
        gap="var(--hub-space-4)",
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


def _related_contracts_section() -> rx.Component:
    return contract_related_contracts(
        total_count_label=ContractDetailState.related_contract_count_label,
        outgoing_count_label=ContractDetailState.outgoing_related_contract_count_label,
        incoming_count_label=ContractDetailState.incoming_related_contract_count_label,
        outgoing_relations=ContractDetailState.outgoing_related_contracts,
        incoming_relations=ContractDetailState.incoming_related_contracts,
        has_outgoing_relations=ContractDetailState.has_outgoing_related_contracts,
        has_incoming_relations=ContractDetailState.has_incoming_related_contracts,
        custom_attrs={"data-testid": "contract-related-contracts"},
    )


def _deployment_result_card() -> rx.Component:
    return rx.cond(
        ContractDetailState.has_deployment_result,
        rx.box(
            rx.vstack(
                rx.flex(
                    _status_badge(
                        ContractDetailState.deployment_result_status_label,
                        ContractDetailState.deployment_result_status_color_scheme,
                    ),
                    rx.cond(
                        ContractDetailState.has_deployment_result_transport_label,
                        _status_badge(
                            ContractDetailState.deployment_result_transport_label,
                            "gray",
                        ),
                    ),
                    wrap="wrap",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.text(
                    ContractDetailState.deployment_result_message,
                    font_weight="600",
                    color="var(--hub-color-text)",
                ),
                rx.cond(
                    ContractDetailState.has_deployment_result_detail,
                    rx.text(
                        ContractDetailState.deployment_result_detail,
                        color="var(--hub-color-text-muted)",
                        font_size="0.95rem",
                    ),
                ),
                rx.cond(
                    ContractDetailState.has_deployment_result_external_request_id,
                    rx.text(
                        "External request ID: ",
                        ContractDetailState.deployment_result_external_request_id,
                        color="var(--hub-color-text-muted)",
                        font_size="0.95rem",
                    ),
                ),
                rx.cond(
                    ContractDetailState.has_deployment_result_redirect_url,
                    rx.link(
                        rx.button(
                            "Open playground",
                            type="button",
                            size="3",
                            variant="solid",
                            color_scheme="bronze",
                        ),
                        href=ContractDetailState.deployment_result_redirect_url,
                        target="_blank",
                        rel="noopener noreferrer",
                        text_decoration="none",
                        width="fit-content",
                    ),
                ),
                align="start",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            width="100%",
            padding="var(--hub-space-4)",
            border="1px solid rgba(124, 93, 37, 0.16)",
            border_radius="var(--hub-radius-md)",
            background="rgba(255, 251, 243, 0.92)",
            custom_attrs={"data-testid": "contract-deployment-result"},
        ),
    )


def _ad_hoc_target_input() -> rx.Component:
    return rx.vstack(
        _field_label("Playground ID"),
        _surface_input(
            name="playground_id",
            value=ContractDetailState.deployment_ad_hoc_playground_id,
            on_change=ContractDetailState.set_deployment_ad_hoc_playground_id,
            placeholder="sandbox-alpha",
            required=True,
        ),
        rx.text(
            "Ad hoc playground IDs are trimmed but otherwise treated as opaque values.",
            color="var(--hub-color-text-muted)",
            font_size="0.9rem",
        ),
        _field_error(ContractDetailState.deployment_playground_id_error),
        align="start",
        gap="var(--hub-space-2)",
        width="100%",
    )


def _deployment_target_controls() -> rx.Component:
    saved_target_select = rx.vstack(
        _field_label("Saved target"),
        rx.el.select(
            rx.foreach(
                ContractDetailState.deployment_saved_targets,
                lambda target: rx.el.option(
                    target["option_label"],
                    value=target["id"].to(str),
                ),
            ),
            name="playground_target_id",
            value=ContractDetailState.deployment_saved_target_id,
            on_change=ContractDetailState.set_deployment_saved_target_id,
            style=_select_style(),
        ),
        rx.text(
            ContractDetailState.deployment_target_count_label,
            color="var(--hub-color-text-muted)",
            font_size="0.9rem",
        ),
        rx.link(
            "Manage saved targets",
            href=PROFILE_SETTINGS_ROUTE,
            color="var(--hub-color-accent-strong)",
            text_decoration="underline",
        ),
        _field_error(ContractDetailState.deployment_saved_target_error),
        align="start",
        gap="var(--hub-space-2)",
        width="100%",
    )
    return rx.cond(
        ContractDetailState.has_deployment_saved_targets,
        rx.vstack(
            _field_label("Target source"),
            rx.el.select(
                rx.el.option("Saved target", value="saved"),
                rx.el.option("Ad hoc ID", value="ad_hoc"),
                name="target_mode",
                value=ContractDetailState.deployment_target_mode,
                on_change=ContractDetailState.set_deployment_target_mode,
                style=_select_style(),
            ),
            rx.cond(
                ContractDetailState.using_saved_deployment_target,
                saved_target_select,
                _ad_hoc_target_input(),
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        rx.vstack(
            _ad_hoc_target_input(),
            rx.text(
                "No saved playground targets yet.",
                color="var(--hub-color-text-muted)",
                font_size="0.9rem",
            ),
            rx.link(
                "Add saved targets in profile settings",
                href=PROFILE_SETTINGS_ROUTE,
                color="var(--hub-color-accent-strong)",
                text_decoration="underline",
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
    )


def _deployment_drawer() -> rx.Component:
    drawer_panel = rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.text(
                        "Deploy to Xian playground",
                        font_size="0.78rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        "Choose a version and target",
                        size="5",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.05em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        "Use a saved playground target or paste an ad hoc ID, then "
                        "record the deployment handoff.",
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.button(
                    "Close",
                    type="button",
                    size="2",
                    variant="soft",
                    on_click=ContractDetailState.close_deployment_drawer,
                    disabled=ContractDetailState.deployment_pending,
                ),
                align="start",
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            _feedback_banner(
                ContractDetailState.deployment_form_error,
                tone="error",
                test_id="contract-deployment-form-error",
            ),
            rx.form(
                rx.vstack(
                    rx.vstack(
                        _field_label("Version"),
                        rx.el.select(
                            rx.foreach(
                                ContractDetailState.available_versions,
                                lambda version: rx.el.option(
                                    version["semantic_version"],
                                    value=version["semantic_version"],
                                ),
                            ),
                            name="semantic_version",
                            value=ContractDetailState.deployment_version,
                            on_change=ContractDetailState.set_deployment_version,
                            style=_select_style(),
                        ),
                        _field_error(ContractDetailState.deployment_version_error),
                        align="start",
                        gap="var(--hub-space-2)",
                        width="100%",
                    ),
                    _deployment_target_controls(),
                    rx.flex(
                        rx.button(
                            ContractDetailState.deployment_submit_label,
                            type="submit",
                            size="3",
                            color_scheme="bronze",
                            disabled=ContractDetailState.deployment_pending,
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                        rx.button(
                            "Close",
                            type="button",
                            size="3",
                            variant="soft",
                            on_click=ContractDetailState.close_deployment_drawer,
                            disabled=ContractDetailState.deployment_pending,
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                        direction=rx.breakpoints(initial="column", sm="row"),
                        gap="var(--hub-space-3)",
                        width="100%",
                    ),
                    align="start",
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                on_submit=ContractDetailState.submit_deployment,
                width="100%",
                custom_attrs={"data-testid": "contract-deployment-form"},
            ),
            _deployment_result_card(),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        width=rx.breakpoints(initial="100%", md="30rem"),
        max_width="100%",
        height="100%",
        padding=rx.breakpoints(initial="var(--hub-space-5)", md="var(--hub-space-6)"),
        background="rgba(255, 252, 246, 0.98)",
        border_left=rx.breakpoints(initial="none", md="1px solid var(--hub-color-line)"),
        box_shadow="var(--hub-shadow-panel)",
        overflow_y="auto",
    )
    return rx.cond(
        ContractDetailState.deployment_drawer_open,
        rx.box(
            rx.box(
                position="fixed",
                inset="0",
                background="rgba(38, 30, 17, 0.42)",
                backdrop_filter="blur(3px)",
                on_click=ContractDetailState.close_deployment_drawer,
            ),
            rx.flex(
                drawer_panel,
                justify="end",
                align="start",
                width="100%",
                height="100%",
                position="relative",
            ),
            position="fixed",
            inset="0",
            z_index="60",
            custom_attrs={"data-testid": "contract-deployment-drawer"},
        ),
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
                    _related_contracts_section(),
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
            _deployment_drawer(),
            width="100%",
            custom_attrs={"data-testid": "contract-detail-page"},
        )
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
