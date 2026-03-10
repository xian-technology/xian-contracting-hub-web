"""Admin contract-version manager page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import app_shell, page_error_state, page_loading_state, page_section
from contracting_hub.states.admin_contract_versions import AdminContractVersionManagerState
from contracting_hub.states.auth import AuthState
from contracting_hub.utils.meta import ADMIN_CONTRACT_VERSIONS_ROUTE, ADMIN_CONTRACTS_ROUTE

ROUTE = ADMIN_CONTRACT_VERSIONS_ROUTE
ON_LOAD = [AuthState.guard_admin_route, AdminContractVersionManagerState.load_page]


def _field_label(label: str) -> rx.Component:
    return rx.text(
        label,
        font_size="0.78rem",
        font_weight="600",
        text_transform="uppercase",
        letter_spacing="0.08em",
        color="var(--hub-color-text-muted)",
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


def _code_area_style() -> dict[str, str]:
    return {
        **_select_style(),
        "minHeight": "20rem",
        "resize": "vertical",
        "lineHeight": "1.7",
        "fontFamily": "var(--hub-font-mono)",
        "fontSize": "0.9rem",
        "whiteSpace": "pre",
    }


def _message_banner(message, *, tone: str) -> rx.Component:
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
        ),
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


def _editor_field(
    *,
    label: str,
    control: rx.Component,
    error_message,
    helper_text: str | None = None,
) -> rx.Component:
    children: list[rx.Component] = [_field_label(label), control]
    if helper_text is not None:
        children.append(
            rx.text(
                helper_text,
                font_size="0.9rem",
                color="var(--hub-color-text-muted)",
            )
        )
    children.append(_field_error(error_message))
    return rx.vstack(
        *children,
        align="start",
        gap="var(--hub-space-2)",
        width="100%",
    )


def _status_badge(label, color_scheme) -> rx.Component:
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme=color_scheme,
    )


def _overview_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.badge(
                        "Version manager",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.heading(
                        AdminContractVersionManagerState.page_heading,
                        size="6",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.05em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        AdminContractVersionManagerState.page_intro,
                        color="var(--hub-color-text-muted)",
                        max_width="46rem",
                    ),
                    rx.text(
                        AdminContractVersionManagerState.contract_name,
                        font_family="var(--hub-font-mono)",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.flex(
                        _status_badge(
                            AdminContractVersionManagerState.contract_status_label,
                            AdminContractVersionManagerState.contract_status_color_scheme,
                        ),
                        rx.badge(
                            AdminContractVersionManagerState.latest_public_version_label,
                            radius="full",
                            variant="soft",
                            color_scheme="gray",
                        ),
                        rx.badge(
                            AdminContractVersionManagerState.latest_saved_version_label,
                            radius="full",
                            variant="soft",
                            color_scheme="bronze",
                        ),
                        rx.badge(
                            AdminContractVersionManagerState.version_count_label,
                            radius="full",
                            variant="soft",
                            color_scheme="bronze",
                        ),
                        gap="var(--hub-space-3)",
                        wrap="wrap",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                rx.flex(
                    rx.link(
                        rx.button("Back to contracts", size="3", variant="soft"),
                        href=ADMIN_CONTRACTS_ROUTE,
                        text_decoration="none",
                    ),
                    rx.link(
                        rx.button("Edit metadata", size="3", variant="soft"),
                        href=AdminContractVersionManagerState.metadata_edit_href,
                        text_decoration="none",
                    ),
                    rx.cond(
                        AdminContractVersionManagerState.has_relation_manager,
                        rx.link(
                            rx.button("Manage relations", size="3", variant="soft"),
                            href=AdminContractVersionManagerState.relations_href,
                            text_decoration="none",
                        ),
                    ),
                    rx.cond(
                        AdminContractVersionManagerState.has_public_detail,
                        rx.link(
                            rx.button("View public detail", size="3"),
                            href=AdminContractVersionManagerState.public_detail_href,
                            text_decoration="none",
                        ),
                    ),
                    direction=rx.breakpoints(initial="column", sm="row"),
                    gap="var(--hub-space-3)",
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                direction=rx.breakpoints(initial="column", lg="row"),
                align=rx.breakpoints(initial="start", lg="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-lg)",
        background="rgba(255, 252, 246, 0.97)",
        box_shadow="var(--hub-shadow-panel)",
    )


def _version_row(row) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.flex(
                    rx.heading(
                        row["semantic_version"],
                        size="4",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.cond(
                        row["is_latest_published"],
                        rx.badge(
                            "Latest public",
                            radius="full",
                            variant="soft",
                            color_scheme="bronze",
                        ),
                    ),
                    align="center",
                    gap="var(--hub-space-2)",
                    wrap="wrap",
                ),
                rx.flex(
                    _status_badge(row["status_label"], row["status_color_scheme"]),
                    _status_badge(row["lint_status_label"], row["lint_status_color_scheme"]),
                    gap="var(--hub-space-2)",
                    wrap="wrap",
                    justify=rx.breakpoints(initial="start", sm="end"),
                ),
                direction=rx.breakpoints(initial="column", sm="row"),
                align=rx.breakpoints(initial="start", sm="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.grid(
                rx.box(
                    _field_label("Baseline"),
                    rx.text(row["previous_version_label"], color="var(--hub-color-text)"),
                ),
                rx.box(
                    _field_label("Saved"),
                    rx.text(row["created_at_label"], color="var(--hub-color-text)"),
                ),
                rx.box(
                    _field_label("Published"),
                    rx.text(row["published_at_label"], color="var(--hub-color-text)"),
                ),
                columns=rx.breakpoints(initial="1", md="3"),
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.cond(
                row["has_public_detail"],
                rx.link(
                    rx.button("Open public version", size="2", variant="soft"),
                    href=row["public_detail_href"],
                    text_decoration="none",
                ),
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border="1px solid rgba(148, 128, 97, 0.18)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 252, 246, 0.9)",
    )


def _history_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading(
                        "Persisted versions",
                        size="4",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.04em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Immutable history stays visible here, including drafts "
                            "that are still under review."
                        ),
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                ),
                rx.badge(
                    AdminContractVersionManagerState.version_count_label,
                    radius="full",
                    variant="soft",
                    color_scheme="bronze",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.cond(
                AdminContractVersionManagerState.has_version_history,
                rx.vstack(
                    rx.foreach(AdminContractVersionManagerState.version_rows, _version_row),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                rx.box(
                    rx.text(
                        (
                            "No versions have been saved yet. Start with a source draft "
                            "and run a preview before committing the first release."
                        ),
                        color="var(--hub-color-text-muted)",
                    ),
                    width="100%",
                    padding="1rem 1.05rem",
                    border="1px dashed var(--hub-color-line)",
                    border_radius="var(--hub-radius-md)",
                    background="rgba(255, 250, 242, 0.72)",
                ),
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
            custom_attrs={"data-testid": "admin-contract-version-history"},
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.82)",
    )


def _editor_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading(
                        "New immutable snapshot",
                        size="4",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.04em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Each save creates a new append-only version row. Existing "
                            "source snapshots are never overwritten."
                        ),
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                ),
                rx.badge(
                    AdminContractVersionManagerState.source_line_count_label,
                    radius="full",
                    variant="soft",
                    color_scheme="gray",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            _message_banner(AdminContractVersionManagerState.save_success_message, tone="success"),
            _message_banner(AdminContractVersionManagerState.form_error_message, tone="error"),
            rx.grid(
                _editor_field(
                    label="Semantic version",
                    control=rx.input(
                        size="3",
                        variant="surface",
                        width="100%",
                        value=AdminContractVersionManagerState.semantic_version_value,
                        on_change=AdminContractVersionManagerState.set_semantic_version_value,
                        placeholder="1.2.0",
                    ),
                    error_message=AdminContractVersionManagerState.semantic_version_error,
                    helper_text="Use a new immutable semantic version for each release candidate.",
                ),
                _editor_field(
                    label="Changelog",
                    control=rx.el.textarea(
                        value=AdminContractVersionManagerState.changelog_value,
                        on_change=AdminContractVersionManagerState.set_changelog_value,
                        placeholder="Summarize the contract changes introduced in this snapshot.",
                        rows="4",
                        style={
                            **_select_style(),
                            "minHeight": "8rem",
                            "resize": "vertical",
                            "lineHeight": "1.55",
                        },
                    ),
                    error_message=AdminContractVersionManagerState.changelog_error,
                    helper_text=(
                        "Optional release notes shown alongside the stored version history."
                    ),
                ),
                columns=rx.breakpoints(initial="1", xl="1fr 1.2fr"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            _editor_field(
                label="Source code",
                control=rx.el.textarea(
                    value=AdminContractVersionManagerState.source_code_value,
                    on_change=AdminContractVersionManagerState.set_source_code_value,
                    placeholder="@export\ndef contract_entrypoint():\n    return 'ready'\n",
                    rows="20",
                    style=_code_area_style(),
                ),
                error_message=AdminContractVersionManagerState.source_code_error,
                helper_text=(
                    "The preview uses this exact source snapshot and compares it "
                    "against the latest saved version."
                ),
            ),
            rx.flex(
                rx.button(
                    "Preview lint and diff",
                    type="button",
                    size="3",
                    variant="soft",
                    on_click=AdminContractVersionManagerState.run_preview,
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                rx.button(
                    "Save draft version",
                    type="button",
                    size="3",
                    variant="soft",
                    on_click=AdminContractVersionManagerState.save_draft_version,
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                rx.button(
                    "Publish version",
                    type="button",
                    size="3",
                    disabled=(
                        AdminContractVersionManagerState.preview_ready
                        & ~AdminContractVersionManagerState.preview_can_publish
                    ),
                    on_click=AdminContractVersionManagerState.publish_version,
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                direction=rx.breakpoints(initial="column", sm="row"),
                gap="var(--hub-space-3)",
                width="100%",
                justify="end",
            ),
            rx.text(
                AdminContractVersionManagerState.preview_publish_hint,
                color="var(--hub-color-text-muted)",
                font_size="0.92rem",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
            custom_attrs={"data-testid": "admin-contract-version-editor"},
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.82)",
    )


def _finding_card(finding) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                _status_badge(finding["severity_label"], finding["severity_color_scheme"]),
                rx.text(
                    finding["location_label"],
                    font_family="var(--hub-font-mono)",
                    font_size="0.82rem",
                    color="var(--hub-color-text-muted)",
                ),
                direction=rx.breakpoints(initial="column", sm="row"),
                align=rx.breakpoints(initial="start", sm="center"),
                gap="var(--hub-space-2)",
                width="100%",
            ),
            rx.text(
                finding["message"],
                color="var(--hub-color-text)",
                line_height="1.7",
                white_space="pre-wrap",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border="1px solid rgba(124, 93, 37, 0.14)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 252, 246, 0.9)",
    )


def _lint_preview_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.text(
                        "Lint preview",
                        font_size="0.75rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        "Quality checks before save",
                        size="4",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Run a preview to inspect the current source snapshot "
                            "with the same linter used during persistence."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="42rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    rx.cond(
                        AdminContractVersionManagerState.preview_target_version_label != "",
                        rx.badge(
                            AdminContractVersionManagerState.preview_target_version_label,
                            radius="full",
                            variant="soft",
                            color_scheme="bronze",
                        ),
                    ),
                    _status_badge(
                        AdminContractVersionManagerState.preview_lint_status_label,
                        AdminContractVersionManagerState.preview_lint_status_color_scheme,
                    ),
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
            rx.box(
                rx.vstack(
                    rx.text(
                        AdminContractVersionManagerState.preview_lint_summary_copy,
                        color="var(--hub-color-text-muted)",
                        max_width="44rem",
                    ),
                    rx.cond(
                        AdminContractVersionManagerState.preview_ready,
                        rx.flex(
                            rx.badge(
                                AdminContractVersionManagerState.preview_lint_issue_count_label,
                                radius="full",
                                variant="soft",
                                color_scheme="gray",
                            ),
                            rx.badge(
                                AdminContractVersionManagerState.preview_lint_error_count_label,
                                radius="full",
                                variant="soft",
                                color_scheme="tomato",
                            ),
                            rx.badge(
                                AdminContractVersionManagerState.preview_lint_warning_count_label,
                                radius="full",
                                variant="soft",
                                color_scheme="orange",
                            ),
                            rx.badge(
                                AdminContractVersionManagerState.preview_lint_info_count_label,
                                radius="full",
                                variant="soft",
                                color_scheme="gray",
                            ),
                            wrap="wrap",
                            gap="var(--hub-space-2)",
                            width="100%",
                        ),
                    ),
                    rx.cond(
                        AdminContractVersionManagerState.has_preview_lint_findings,
                        rx.vstack(
                            rx.foreach(
                                AdminContractVersionManagerState.preview_lint_findings,
                                _finding_card,
                            ),
                            align="start",
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
                background="rgba(255, 248, 236, 0.72)",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
            custom_attrs={"data-testid": "admin-contract-version-lint-preview"},
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.82)",
    )


def _diff_preview_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.text(
                        "Diff preview",
                        font_size="0.75rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        "Comparison against the latest saved snapshot",
                        size="4",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "The preview baseline follows the same latest-version "
                            "linkage used when the new row is persisted."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="42rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    rx.cond(
                        AdminContractVersionManagerState.preview_target_version_label != "",
                        rx.badge(
                            AdminContractVersionManagerState.preview_target_version_label,
                            radius="full",
                            variant="soft",
                            color_scheme="bronze",
                        ),
                    ),
                    rx.cond(
                        AdminContractVersionManagerState.preview_diff_has_previous_version,
                        rx.badge(
                            AdminContractVersionManagerState.preview_diff_previous_version,
                            radius="full",
                            variant="soft",
                            color_scheme="gray",
                        ),
                        rx.badge(
                            "Initial release",
                            radius="full",
                            variant="soft",
                            color_scheme="gray",
                        ),
                    ),
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
            rx.box(
                rx.vstack(
                    rx.cond(
                        AdminContractVersionManagerState.preview_ready,
                        rx.flex(
                            rx.badge(
                                AdminContractVersionManagerState.preview_diff_added_lines_label,
                                radius="full",
                                variant="soft",
                                color_scheme="grass",
                            ),
                            rx.badge(
                                AdminContractVersionManagerState.preview_diff_removed_lines_label,
                                radius="full",
                                variant="soft",
                                color_scheme="tomato",
                            ),
                            rx.badge(
                                AdminContractVersionManagerState.preview_diff_line_delta_label,
                                radius="full",
                                variant="soft",
                                color_scheme="gray",
                            ),
                            rx.badge(
                                AdminContractVersionManagerState.preview_diff_hunk_count_label,
                                radius="full",
                                variant="soft",
                                color_scheme="gray",
                            ),
                            rx.badge(
                                AdminContractVersionManagerState.preview_diff_context_lines_label,
                                radius="full",
                                variant="soft",
                                color_scheme="gray",
                            ),
                            wrap="wrap",
                            gap="var(--hub-space-2)",
                            width="100%",
                        ),
                    ),
                    rx.cond(
                        AdminContractVersionManagerState.has_preview_diff_content,
                        rx.box(
                            rx.code_block(
                                AdminContractVersionManagerState.preview_diff_unified_text,
                                language="diff",
                                theme=rx.code_block.themes.one_light,
                                show_line_numbers=True,
                                wrap_long_lines=False,
                                custom_style={
                                    "margin": "0",
                                    "padding": "1.25rem",
                                    "fontFamily": "var(--hub-font-mono)",
                                    "fontSize": "0.88rem",
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
                        rx.box(
                            rx.text(
                                (
                                    "Run a preview to see diff output. Initial releases "
                                    "do not render a unified diff until a baseline exists."
                                ),
                                color="var(--hub-color-text-muted)",
                            ),
                            width="100%",
                            padding="1rem 1.05rem",
                            border="1px dashed rgba(148, 128, 97, 0.22)",
                            border_radius="var(--hub-radius-md)",
                            background="rgba(255, 252, 246, 0.9)",
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
                background="rgba(255, 248, 236, 0.72)",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
            custom_attrs={"data-testid": "admin-contract-version-diff-preview"},
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.82)",
    )


def _missing_contract_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.badge(
                "Missing contract",
                radius="full",
                variant="soft",
                color_scheme="bronze",
                width="fit-content",
            ),
            rx.heading(
                "The requested contract could not be loaded.",
                size="5",
                font_family="var(--hub-font-display)",
                letter_spacing="-0.05em",
                color="var(--hub-color-text)",
            ),
            rx.text(
                AdminContractVersionManagerState.load_error_message,
                color="var(--hub-color-text-muted)",
                max_width="36rem",
            ),
            rx.link(
                rx.button("Back to admin contracts", size="3"),
                href=ADMIN_CONTRACTS_ROUTE,
                text_decoration="none",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-lg)",
        background="rgba(255, 252, 246, 0.97)",
        box_shadow="var(--hub-shadow-panel)",
    )


def index() -> rx.Component:
    """Render the admin route for managing contract versions."""
    return app_shell(
        rx.box(
            rx.cond(
                AdminContractVersionManagerState.is_loading,
                page_loading_state(
                    title="Loading version manager",
                    body="Preparing immutable version history, lint previews, and diff context.",
                    test_id="admin-contract-version-loading",
                ),
                rx.cond(
                    AdminContractVersionManagerState.has_load_error,
                    page_error_state(
                        title="Version manager could not be loaded",
                        body=AdminContractVersionManagerState.load_error_message,
                        test_id="admin-contract-version-error",
                        action=rx.link(
                            rx.button("Back to admin contracts", size="3", variant="soft"),
                            href=ADMIN_CONTRACTS_ROUTE,
                            text_decoration="none",
                        ),
                    ),
                    rx.vstack(
                        page_section(_overview_card()),
                        page_section(
                            _message_banner(
                                AdminContractVersionManagerState.load_error_message,
                                tone="error",
                            ),
                            rx.cond(
                                AdminContractVersionManagerState.show_missing_contract_state,
                                _missing_contract_state(),
                                rx.grid(
                                    rx.vstack(
                                        _editor_panel(),
                                        _lint_preview_panel(),
                                        _diff_preview_panel(),
                                        align="start",
                                        gap="var(--hub-space-5)",
                                        width="100%",
                                    ),
                                    _history_panel(),
                                    columns=rx.breakpoints(initial="1", xl="1.5fr 1fr"),
                                    gap="var(--hub-space-5)",
                                    width="100%",
                                    align_items="start",
                                ),
                            ),
                        ),
                        gap="var(--hub-space-6)",
                        width="100%",
                    ),
                ),
            ),
            width="100%",
            custom_attrs={"data-testid": "admin-contract-version-page"},
        ),
        page_title=AdminContractVersionManagerState.page_heading,
        page_intro=AdminContractVersionManagerState.page_intro,
        page_kicker="Admin workspace",
        auth_state=AdminContractVersionManagerState,
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
