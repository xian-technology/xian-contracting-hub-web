"""Lint-summary primitives for public contract pages."""

from __future__ import annotations

from typing import Literal

import reflex as rx

from contracting_hub.components.contract_catalog import contract_metadata_badge
from contracting_hub.components.page_section import page_section


def contract_lint_results_panel(
    *,
    selected_version: object,
    has_lint_report: object,
    lint_status_label: object,
    lint_status_color_scheme: object,
    lint_summary_copy: object,
    issue_count_label: object,
    error_count_label: object,
    warning_count_label: object,
    info_count_label: object,
    findings: object,
    has_findings: object,
    **props: object,
) -> rx.Component:
    """Render lint status, counts, and issue details for one public release."""
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.text(
                        "Lint results",
                        font_size="0.75rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.heading(
                        "Quality checks",
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Review the stored xian-linter summary for the selected public "
                            "release before reusing or deploying the contract."
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
                        selected_version,
                        contract_metadata_badge(selected_version, tone="category"),
                    ),
                    _status_badge(lint_status_label, lint_status_color_scheme),
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
            rx.cond(
                has_lint_report,
                _lint_report_state(
                    lint_summary_copy=lint_summary_copy,
                    issue_count_label=issue_count_label,
                    error_count_label=error_count_label,
                    warning_count_label=warning_count_label,
                    info_count_label=info_count_label,
                    findings=findings,
                    has_findings=has_findings,
                ),
                _lint_unavailable_state(),
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        **props,
    )


def _lint_report_state(
    *,
    lint_summary_copy: object,
    issue_count_label: object,
    error_count_label: object,
    warning_count_label: object,
    info_count_label: object,
    findings: object,
    has_findings: object,
) -> rx.Component:
    typed_findings = _typed_lint_findings(findings)
    return rx.box(
        rx.vstack(
            rx.text(
                lint_summary_copy,
                color="var(--hub-color-text-muted)",
                max_width="44rem",
            ),
            rx.flex(
                _summary_badge(issue_count_label, "gray"),
                _summary_badge(error_count_label, "tomato"),
                _summary_badge(warning_count_label, "orange"),
                _summary_badge(info_count_label, "gray"),
                wrap="wrap",
                gap="var(--hub-space-2)",
                width="100%",
            ),
            rx.cond(
                has_findings,
                rx.vstack(
                    rx.text(
                        "Detailed findings",
                        font_size="0.75rem",
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.vstack(
                        rx.foreach(typed_findings, _finding_card),
                        align="start",
                        gap="var(--hub-space-3)",
                        width="100%",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                _clean_lint_state(),
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
    )


def _finding_card(finding: object) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                _finding_severity_badge(
                    finding["severity_label"],
                    finding["severity_color_scheme"],
                ),
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


def _status_badge(label: object, color_scheme: object) -> rx.Component:
    return rx.cond(
        color_scheme == "grass",
        _summary_badge(label, "grass"),
        rx.cond(
            color_scheme == "orange",
            _summary_badge(label, "orange"),
            rx.cond(
                color_scheme == "tomato",
                _summary_badge(label, "tomato"),
                _summary_badge(label, "gray"),
            ),
        ),
    )


def _finding_severity_badge(label: object, color_scheme: object) -> rx.Component:
    return rx.cond(
        color_scheme == "tomato",
        _summary_badge(label, "tomato"),
        rx.cond(
            color_scheme == "orange",
            _summary_badge(label, "orange"),
            _summary_badge(label, "gray"),
        ),
    )


def _summary_badge(
    label: object,
    color_scheme: Literal["grass", "orange", "tomato", "gray"],
) -> rx.Component:
    return rx.badge(
        label,
        radius="full",
        variant="soft",
        color_scheme=color_scheme,
        padding_x="0.85rem",
        padding_y="0.35rem",
    )


def _typed_lint_findings(findings: object):
    return rx.Var.create(findings).to(list[dict[str, str]])


def _clean_lint_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "No detailed findings",
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                "This public release currently carries no stored lint findings.",
                color="var(--hub-color-text-muted)",
                max_width="36rem",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px dashed rgba(124, 93, 37, 0.24)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 251, 244, 0.78)",
    )


def _lint_unavailable_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "Lint report unavailable",
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                (
                    "The selected public version does not currently expose stored lint "
                    "metadata. Review the source snapshot directly before reuse."
                ),
                color="var(--hub-color-text-muted)",
                max_width="36rem",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px dashed rgba(124, 93, 37, 0.24)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 251, 244, 0.78)",
    )


__all__ = ["contract_lint_results_panel"]
