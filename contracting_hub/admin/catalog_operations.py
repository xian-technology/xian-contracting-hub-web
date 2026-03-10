"""Admin catalog-operations workspace page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import app_shell, contract_metadata_badge, page_section
from contracting_hub.states.admin_catalog_operations import AdminCatalogOperationsState
from contracting_hub.states.auth import AuthState
from contracting_hub.utils.meta import ADMIN_CONTRACTS_ROUTE, ADMIN_OPERATIONS_ROUTE

ROUTE = ADMIN_OPERATIONS_ROUTE
ON_LOAD = [AuthState.guard_admin_route, AdminCatalogOperationsState.load_page]


def _field_label(label: str) -> rx.Component:
    return rx.text(
        label,
        font_size="0.78rem",
        font_weight="600",
        text_transform="uppercase",
        letter_spacing="0.08em",
        color="var(--hub-color-text-muted)",
    )


def _surface_input(**props: object) -> rx.Component:
    return rx.input(
        size="3",
        variant="surface",
        width="100%",
        **props,
    )


def _text_area_style() -> dict[str, str]:
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
        "minHeight": "7rem",
        "resize": "vertical",
        "lineHeight": "1.55",
    }


def _surface_text_area(**props: object) -> rx.Component:
    return rx.el.textarea(style=_text_area_style(), **props)


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


def _empty_state(*, title: str, body: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                title,
                size="4",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                body,
                color="var(--hub-color-text-muted)",
                max_width="32rem",
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px dashed var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.68)",
    )


def _overview_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.badge(
                        "Catalog operations",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.heading(
                        "Manage taxonomy, featured picks, and audit visibility.",
                        size="6",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.05em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Keep browse taxonomy tidy, curate homepage-worthy contracts, "
                            "and review the latest immutable admin actions from one place."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="46rem",
                    ),
                    rx.flex(
                        contract_metadata_badge(
                            AdminCatalogOperationsState.category_count_label,
                            tone="category",
                        ),
                        contract_metadata_badge(
                            AdminCatalogOperationsState.featured_count_label,
                            tone="featured",
                        ),
                        contract_metadata_badge(
                            AdminCatalogOperationsState.audit_log_count_label,
                            tone="neutral",
                        ),
                        gap="var(--hub-space-3)",
                        wrap="wrap",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                rx.link(
                    rx.button("Back to contracts", size="3", variant="soft"),
                    href=ADMIN_CONTRACTS_ROUTE,
                    text_decoration="none",
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
        custom_attrs={"data-testid": "admin-catalog-overview"},
    )


def _category_row(row) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.flex(
                        rx.heading(
                            row["name"],
                            size="4",
                            font_family="var(--hub-font-display)",
                            color="var(--hub-color-text)",
                        ),
                        contract_metadata_badge(row["contract_count_label"], tone="neutral"),
                        gap="var(--hub-space-2)",
                        wrap="wrap",
                        align="center",
                    ),
                    rx.text(
                        "/",
                        row["slug"],
                        font_family="var(--hub-font-mono)",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.cond(
                        row["description"] != "",
                        rx.text(
                            row["description"],
                            color="var(--hub-color-text-muted)",
                        ),
                    ),
                    rx.flex(
                        contract_metadata_badge(
                            rx.text("Sort ", row["sort_order_label"]),
                            tone="category",
                        ),
                        contract_metadata_badge(
                            rx.text("Updated ", row["updated_at_label"]),
                            tone="neutral",
                        ),
                        gap="var(--hub-space-2)",
                        wrap="wrap",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    rx.button(
                        "Edit",
                        size="2",
                        variant="soft",
                        on_click=AdminCatalogOperationsState.start_edit_category(
                            row["category_id"]
                        ),
                    ),
                    rx.cond(
                        row["can_delete"],
                        rx.button(
                            "Delete",
                            size="2",
                            variant="soft",
                            color_scheme="tomato",
                            on_click=AdminCatalogOperationsState.delete_category(
                                row["category_id"]
                            ),
                        ),
                        contract_metadata_badge("In use", tone="warning"),
                    ),
                    direction=rx.breakpoints(initial="column", sm="row"),
                    align=rx.breakpoints(initial="start", sm="center"),
                    gap="var(--hub-space-2)",
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid rgba(148, 128, 97, 0.18)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 252, 246, 0.94)",
        custom_attrs={"data-testid": "admin-category-row"},
    )


def _category_manager() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading(
                        "Category management",
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Create taxonomy buckets, tune ordering, and rename categories "
                            "without leaving the admin workspace."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="42rem",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                contract_metadata_badge(
                    AdminCatalogOperationsState.category_count_label,
                    tone="category",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            _message_banner(AdminCatalogOperationsState.category_success_message, tone="success"),
            _message_banner(AdminCatalogOperationsState.category_form_error, tone="error"),
            rx.grid(
                rx.form(
                    rx.vstack(
                        rx.flex(
                            rx.heading(
                                AdminCatalogOperationsState.category_form_heading,
                                size="4",
                                font_family="var(--hub-font-display)",
                                color="var(--hub-color-text)",
                            ),
                            rx.cond(
                                AdminCatalogOperationsState.is_editing_category,
                                rx.button(
                                    "Cancel",
                                    type="button",
                                    size="2",
                                    variant="soft",
                                    on_click=AdminCatalogOperationsState.cancel_category_edit,
                                ),
                            ),
                            align="center",
                            justify="between",
                            gap="var(--hub-space-3)",
                            width="100%",
                        ),
                        _editor_field(
                            label="Slug",
                            control=_surface_input(
                                name="slug",
                                value=AdminCatalogOperationsState.category_slug_value,
                                on_change=AdminCatalogOperationsState.set_category_slug_value,
                                placeholder="defi",
                            ),
                            error_message=AdminCatalogOperationsState.category_slug_error,
                            helper_text="Use lowercase letters, numbers, hyphens, or underscores.",
                        ),
                        _editor_field(
                            label="Name",
                            control=_surface_input(
                                name="name",
                                value=AdminCatalogOperationsState.category_name_value,
                                on_change=AdminCatalogOperationsState.set_category_name_value,
                                placeholder="DeFi",
                            ),
                            error_message=AdminCatalogOperationsState.category_name_error,
                        ),
                        _editor_field(
                            label="Description",
                            control=_surface_text_area(
                                name="description",
                                value=AdminCatalogOperationsState.category_description_value,
                                on_change=AdminCatalogOperationsState.set_category_description_value,
                                placeholder="Describe what belongs in this bucket.",
                            ),
                            error_message=AdminCatalogOperationsState.category_description_error,
                        ),
                        _editor_field(
                            label="Sort order",
                            control=_surface_input(
                                name="sort_order",
                                value=AdminCatalogOperationsState.category_sort_order_value,
                                on_change=AdminCatalogOperationsState.set_category_sort_order_value,
                                placeholder="0",
                            ),
                            error_message=AdminCatalogOperationsState.category_sort_order_error,
                            helper_text="Lower numbers appear first in browse filters.",
                        ),
                        rx.button(
                            AdminCatalogOperationsState.category_submit_label,
                            type="submit",
                            size="3",
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                        align="start",
                        gap="var(--hub-space-4)",
                        width="100%",
                    ),
                    on_submit=AdminCatalogOperationsState.submit_category_form,
                    width="100%",
                    custom_attrs={"data-testid": "admin-category-form"},
                ),
                rx.cond(
                    AdminCatalogOperationsState.has_categories,
                    rx.vstack(
                        rx.foreach(AdminCatalogOperationsState.category_rows, _category_row),
                        align="start",
                        gap="var(--hub-space-4)",
                        width="100%",
                    ),
                    _empty_state(
                        title="No categories created yet",
                        body=(
                            "Create the first category to power browse filters "
                            "and homepage context."
                        ),
                    ),
                ),
                columns=rx.breakpoints(initial="1", xl="0.95fr 1.25fr"),
                gap="var(--hub-space-5)",
                width="100%",
                align_items="start",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        custom_attrs={"data-testid": "admin-category-manager"},
    )


def _featured_contract_row(row) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.flex(
                        rx.heading(
                            row["display_name"],
                            size="4",
                            font_family="var(--hub-font-display)",
                            color="var(--hub-color-text)",
                        ),
                        rx.cond(
                            row["is_featured"],
                            contract_metadata_badge("Featured", tone="featured"),
                            contract_metadata_badge("Not featured", tone="neutral"),
                        ),
                        _status_badge(row["status_label"], row["status_color_scheme"]),
                        gap="var(--hub-space-2)",
                        wrap="wrap",
                        align="center",
                    ),
                    rx.text(
                        row["contract_name"],
                        font_family="var(--hub-font-mono)",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.text(
                        "Author: ",
                        row["author_name"],
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.flex(
                        contract_metadata_badge(
                            row["categories_label"],
                            tone="category",
                        ),
                        contract_metadata_badge(
                            row["latest_public_version"],
                            tone="neutral",
                        ),
                        contract_metadata_badge(
                            rx.text("Updated ", row["updated_at_label"]),
                            tone="neutral",
                        ),
                        gap="var(--hub-space-2)",
                        wrap="wrap",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    rx.cond(
                        row["is_featured"],
                        rx.button(
                            "Remove spotlight",
                            size="2",
                            variant="soft",
                            on_click=AdminCatalogOperationsState.toggle_contract_featured(
                                row["slug"]
                            ),
                        ),
                        rx.button(
                            "Feature contract",
                            size="2",
                            on_click=AdminCatalogOperationsState.toggle_contract_featured(
                                row["slug"]
                            ),
                        ),
                    ),
                    rx.link(
                        rx.button("Edit metadata", size="2", variant="soft"),
                        href=row["edit_href"],
                        text_decoration="none",
                    ),
                    rx.cond(
                        row["has_public_detail"],
                        rx.link(
                            rx.button("View public detail", size="2", variant="soft"),
                            href=row["public_detail_href"],
                            text_decoration="none",
                        ),
                    ),
                    direction=rx.breakpoints(initial="column", sm="row"),
                    align=rx.breakpoints(initial="start", sm="center"),
                    gap="var(--hub-space-2)",
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid rgba(148, 128, 97, 0.18)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 252, 246, 0.94)",
        custom_attrs={"data-testid": "admin-featured-contract-row"},
    )


def _featured_curation_panel() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading(
                        "Featured-content curation",
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Promote published contracts into homepage spotlight sections "
                            "without editing each record individually."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="42rem",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                contract_metadata_badge(
                    AdminCatalogOperationsState.featured_count_label,
                    tone="featured",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            _message_banner(AdminCatalogOperationsState.featured_success_message, tone="success"),
            _message_banner(AdminCatalogOperationsState.featured_error_message, tone="error"),
            rx.cond(
                AdminCatalogOperationsState.has_featured_contracts,
                rx.vstack(
                    rx.foreach(
                        AdminCatalogOperationsState.featured_contract_rows,
                        _featured_contract_row,
                    ),
                    align="start",
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                _empty_state(
                    title="No public contracts ready for curation",
                    body=(
                        "Publish a contract version first, then it becomes eligible "
                        "for featured placement."
                    ),
                ),
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        custom_attrs={"data-testid": "admin-featured-curation"},
    )


def _audit_log_row(row) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.flex(
                        contract_metadata_badge(row["action_label"], tone="warning"),
                        contract_metadata_badge(row["entity_type_label"], tone="neutral"),
                        gap="var(--hub-space-2)",
                        wrap="wrap",
                    ),
                    rx.heading(
                        row["summary"],
                        size="4",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        row["admin_label"],
                        " · ",
                        row["created_at_label"],
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.cond(
                row["has_details"],
                rx.box(
                    rx.code_block(
                        row["details_pretty_json"],
                        language="json",
                        theme=rx.code_block.themes.one_light,
                        show_line_numbers=False,
                        wrap_long_lines=True,
                        custom_style={
                            "margin": "0",
                            "padding": "1rem",
                            "fontFamily": "var(--hub-font-mono)",
                            "fontSize": "0.84rem",
                            "lineHeight": "1.6",
                            "minWidth": "100%",
                        },
                    ),
                    width="100%",
                    overflow_x="auto",
                    border="1px solid rgba(124, 93, 37, 0.16)",
                    border_radius="var(--hub-radius-md)",
                    background="rgba(255, 251, 244, 0.96)",
                ),
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid rgba(148, 128, 97, 0.18)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 252, 246, 0.94)",
        custom_attrs={"data-testid": "admin-audit-log-row"},
    )


def _audit_log_panel() -> rx.Component:
    return page_section(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading(
                        "Audit-log inspection",
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Review the latest immutable admin actions, including taxonomy "
                            "changes, publish events, and featured-content updates."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="42rem",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                contract_metadata_badge(
                    AdminCatalogOperationsState.audit_log_count_label,
                    tone="neutral",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            rx.cond(
                AdminCatalogOperationsState.has_audit_logs,
                rx.vstack(
                    rx.foreach(AdminCatalogOperationsState.audit_log_rows, _audit_log_row),
                    align="start",
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                _empty_state(
                    title="No audit records yet",
                    body=(
                        "Admin actions will appear here once contracts, categories, "
                        "or curation settings change."
                    ),
                ),
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        custom_attrs={"data-testid": "admin-audit-log"},
    )


def index() -> rx.Component:
    """Render the admin catalog-operations workspace."""
    return app_shell(
        page_section(
            rx.vstack(
                _overview_card(),
                _category_manager(),
                _featured_curation_panel(),
                _audit_log_panel(),
                align="start",
                gap="var(--hub-space-6)",
                width="100%",
            ),
            custom_attrs={"data-testid": "admin-catalog-page"},
        ),
        page_title="Admin catalog operations",
        page_intro=(
            "Manage shared catalog surfaces that cut across individual contracts, "
            "from browse taxonomy to featured placements and immutable audit history."
        ),
        page_kicker="Admin workspace",
        auth_state=AdminCatalogOperationsState,
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
