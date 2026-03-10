"""Admin contract index page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import (
    app_shell,
    contract_metadata_badge,
    page_error_state,
    page_loading_state,
    page_section,
)
from contracting_hub.states.admin_contracts import AdminContractsState
from contracting_hub.states.auth import AuthState
from contracting_hub.utils.meta import (
    ADMIN_CONTRACT_CREATE_ROUTE,
    ADMIN_CONTRACTS_ROUTE,
    ADMIN_OPERATIONS_ROUTE,
)

ROUTE = ADMIN_CONTRACTS_ROUTE
ON_LOAD = [AuthState.guard_admin_route, AdminContractsState.load_page]


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


def _field_label(label: str) -> rx.Component:
    return rx.text(
        label,
        font_size="0.78rem",
        font_weight="600",
        text_transform="uppercase",
        letter_spacing="0.08em",
        color="var(--hub-color-text-muted)",
    )


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


def _status_tab(tab) -> rx.Component:
    return rx.link(
        rx.box(
            rx.vstack(
                rx.text(
                    tab["label"],
                    font_size="0.95rem",
                    font_weight="700",
                    color=tab["text_color"],
                ),
                rx.text(
                    tab["count"],
                    font_family="var(--hub-font-mono)",
                    font_size="0.9rem",
                    color=tab["text_color"],
                ),
                align="start",
                gap="var(--hub-space-1)",
                width="100%",
            ),
            width="100%",
            padding="1rem 1.05rem",
            border=tab["border_color"],
            border_radius="var(--hub-radius-md)",
            background=tab["background"],
            box_shadow="var(--hub-shadow-panel)",
        ),
        href=tab["href"],
        text_decoration="none",
        width="100%",
    )


def _filters_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.badge(
                        "Contract operations",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.heading(
                        "Control catalog visibility from one admin surface.",
                        size="5",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.05em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Use lifecycle tabs for triage, filter for featured state, "
                            "and run quick publish, archive, or delete actions without "
                            "leaving the index."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="42rem",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                rx.flex(
                    rx.link(
                        rx.button("Catalog operations", size="3", variant="soft"),
                        href=ADMIN_OPERATIONS_ROUTE,
                        text_decoration="none",
                        width=rx.breakpoints(initial="100%", sm="auto"),
                    ),
                    rx.link(
                        rx.button("Create contract", size="3"),
                        href=ADMIN_CONTRACT_CREATE_ROUTE,
                        text_decoration="none",
                        width=rx.breakpoints(initial="100%", sm="auto"),
                        custom_attrs={"data-testid": "admin-contract-create-trigger"},
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
            rx.grid(
                rx.foreach(AdminContractsState.status_tabs, _status_tab),
                columns=rx.breakpoints(initial="2", md="5"),
                gap="var(--hub-space-3)",
                width="100%",
            ),
            _message_banner(AdminContractsState.action_success_message, tone="success"),
            _message_banner(AdminContractsState.action_error_message, tone="error"),
            rx.form(
                rx.grid(
                    rx.vstack(
                        _field_label("Search"),
                        _surface_input(
                            name="query",
                            value=AdminContractsState.query,
                            on_change=AdminContractsState.set_query,
                            placeholder="Search by name, author, tag, or category",
                        ),
                        align="start",
                        gap="var(--hub-space-2)",
                        width="100%",
                    ),
                    rx.vstack(
                        _field_label("Featured"),
                        rx.el.select(
                            rx.el.option("All contracts", value="all"),
                            rx.el.option("Featured only", value="featured"),
                            rx.el.option("Not featured", value="not_featured"),
                            name="featured",
                            value=AdminContractsState.selected_featured_filter,
                            on_change=AdminContractsState.set_selected_featured_filter,
                            style=_select_style(),
                        ),
                        align="start",
                        gap="var(--hub-space-2)",
                        width="100%",
                    ),
                    rx.flex(
                        rx.button(
                            "Apply",
                            type="submit",
                            size="3",
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                        rx.link(
                            rx.button(
                                "Clear",
                                type="button",
                                size="3",
                                variant="soft",
                                width=rx.breakpoints(initial="100%", sm="auto"),
                            ),
                            href=AdminContractsState.clear_filters_href,
                            text_decoration="none",
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                        direction=rx.breakpoints(initial="column", sm="row"),
                        align="end",
                        gap="var(--hub-space-3)",
                        width="100%",
                    ),
                    columns=rx.breakpoints(initial="1", lg="1.8fr 1fr auto"),
                    gap="var(--hub-space-4)",
                    width="100%",
                    align_items="end",
                ),
                on_submit=AdminContractsState.apply_filters,
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-lg)",
        background="rgba(255, 252, 246, 0.97)",
        box_shadow="var(--hub-shadow-panel)",
        custom_attrs={"data-testid": "admin-contract-filters"},
    )


def _row_metadata(label: str, value) -> rx.Component:
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
            color="var(--hub-color-text)",
        ),
        min_width="10rem",
    )


def _contract_row(row) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.flex(
                        rx.box(
                            rx.text(
                                row["status_label"],
                                font_size="0.74rem",
                                font_weight="700",
                                color=row["status_text"],
                                text_transform="uppercase",
                                letter_spacing="0.08em",
                            ),
                            padding="0.35rem 0.65rem",
                            border=row["status_border"],
                            border_radius="var(--hub-radius-pill)",
                            background=row["status_background"],
                        ),
                        rx.cond(
                            row["featured_visible"],
                            contract_metadata_badge(row["featured_label"], tone="featured"),
                        ),
                        wrap="wrap",
                        gap="var(--hub-space-2)",
                        width="100%",
                    ),
                    rx.heading(
                        row["display_name"],
                        size="4",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        row["contract_name"],
                        font_family="var(--hub-font-mono)",
                        font_size="0.95rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.text(
                        row["short_summary"],
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    rx.link(
                        rx.button("Edit", size="2", variant="soft"),
                        href=row["edit_href"],
                        text_decoration="none",
                    ),
                    rx.link(
                        rx.button("Versions", size="2", variant="soft"),
                        href=row["versions_href"],
                        text_decoration="none",
                    ),
                    rx.cond(
                        row["has_public_detail"],
                        rx.link(
                            rx.button("Public view", size="2", variant="soft"),
                            href=row["public_detail_href"],
                            text_decoration="none",
                        ),
                    ),
                    rx.button(
                        "Publish",
                        size="2",
                        variant="soft",
                        disabled=~row["can_publish"],
                        on_click=AdminContractsState.publish_contract(row["slug"]),
                    ),
                    rx.button(
                        "Archive",
                        size="2",
                        variant="soft",
                        disabled=~row["can_archive"],
                        on_click=AdminContractsState.archive_contract(row["slug"]),
                    ),
                    rx.button(
                        "Delete",
                        size="2",
                        variant="outline",
                        color_scheme="tomato",
                        disabled=~row["can_delete"],
                        on_click=AdminContractsState.delete_contract(row["slug"]),
                    ),
                    wrap="wrap",
                    justify=rx.breakpoints(initial="start", lg="end"),
                    gap="var(--hub-space-2)",
                    width=rx.breakpoints(initial="100%", lg="auto"),
                ),
                direction=rx.breakpoints(initial="column", lg="row"),
                align=rx.breakpoints(initial="start", lg="start"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.grid(
                _row_metadata("Author", row["author_name"]),
                _row_metadata("Categories", row["categories_label"]),
                _row_metadata("Latest public version", row["latest_version_label"]),
                _row_metadata("Updated", row["updated_at_label"]),
                columns=rx.breakpoints(initial="1", md="2", xl="4"),
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.text(
                row["action_hint"],
                color="var(--hub-color-text-muted)",
                font_size="0.92rem",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.78)",
        custom_attrs={"data-testid": "admin-contract-row"},
    )


def _empty_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "No admin contracts found",
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                AdminContractsState.empty_state_body,
                color="var(--hub-color-text-muted)",
                max_width="34rem",
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


def index() -> rx.Component:
    """Render the admin contract index."""
    return app_shell(
        rx.box(
            rx.cond(
                AdminContractsState.is_loading,
                page_loading_state(
                    title="Loading admin contract index",
                    body=(
                        "Preparing lifecycle tabs, filters, and catalog rows "
                        "for the admin workspace."
                    ),
                    test_id="admin-contract-loading",
                ),
                rx.cond(
                    AdminContractsState.has_load_error,
                    page_error_state(
                        title="Admin contract index could not be loaded",
                        body=AdminContractsState.load_error_message,
                        test_id="admin-contract-error",
                        action=rx.link(
                            rx.button("Retry admin workspace", size="3", variant="soft"),
                            href=ADMIN_CONTRACTS_ROUTE,
                            text_decoration="none",
                        ),
                    ),
                    page_section(
                        rx.vstack(
                            _filters_panel(),
                            rx.box(
                                rx.vstack(
                                    rx.flex(
                                        rx.heading(
                                            "Catalog contracts",
                                            size="5",
                                            font_family="var(--hub-font-display)",
                                            color="var(--hub-color-text)",
                                        ),
                                        rx.text(
                                            AdminContractsState.result_count_label,
                                            font_family="var(--hub-font-mono)",
                                            color="var(--hub-color-text-muted)",
                                        ),
                                        direction=rx.breakpoints(initial="column", sm="row"),
                                        align=rx.breakpoints(initial="start", sm="center"),
                                        justify="between",
                                        gap="var(--hub-space-3)",
                                        width="100%",
                                    ),
                                    rx.cond(
                                        AdminContractsState.has_results,
                                        rx.vstack(
                                            rx.foreach(
                                                AdminContractsState.contract_rows,
                                                _contract_row,
                                            ),
                                            align="start",
                                            gap="var(--hub-space-4)",
                                            width="100%",
                                        ),
                                        _empty_state(),
                                    ),
                                    align="start",
                                    gap="var(--hub-space-4)",
                                    width="100%",
                                ),
                                width="100%",
                                custom_attrs={"data-testid": "admin-contract-results"},
                            ),
                            align="start",
                            gap="var(--hub-space-6)",
                            width="100%",
                        ),
                    ),
                ),
            ),
            width="100%",
            custom_attrs={"data-testid": "admin-contract-page"},
        ),
        page_title="Admin contract index",
        page_intro=(
            "Review every contract in the catalog, slice by lifecycle state, "
            "and apply quick publish, archive, or delete actions from one admin view."
        ),
        page_kicker="Admin workspace",
        auth_state=AdminContractsState,
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
