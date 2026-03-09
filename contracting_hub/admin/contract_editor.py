"""Admin contract editor page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import app_shell, page_section
from contracting_hub.models import ContractNetwork
from contracting_hub.states.admin_contract_editor import AdminContractEditorState
from contracting_hub.states.auth import AuthState
from contracting_hub.utils.meta import (
    ADMIN_CONTRACT_CREATE_ROUTE,
    ADMIN_CONTRACT_EDIT_ROUTE,
    ADMIN_CONTRACTS_ROUTE,
)

NEW_ROUTE = ADMIN_CONTRACT_CREATE_ROUTE
EDIT_ROUTE = ADMIN_CONTRACT_EDIT_ROUTE
ON_LOAD = [AuthState.guard_admin_route, AdminContractEditorState.load_page]


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


def _surface_text_area(**props: object) -> rx.Component:
    return rx.el.textarea(style=_text_area_style(), **props)


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


def _text_area_style() -> dict[str, str]:
    return {
        **_select_style(),
        "minHeight": "7.5rem",
        "resize": "vertical",
        "lineHeight": "1.55",
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


def _overview_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.badge(
                        "Metadata editor",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.heading(
                        AdminContractEditorState.editor_heading,
                        size="6",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.05em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        AdminContractEditorState.editor_intro,
                        color="var(--hub-color-text-muted)",
                        max_width="44rem",
                    ),
                    rx.flex(
                        rx.badge(
                            AdminContractEditorState.contract_status_label,
                            radius="full",
                            variant="soft",
                            color_scheme="bronze",
                        ),
                        rx.badge(
                            AdminContractEditorState.latest_public_version_label,
                            radius="full",
                            variant="soft",
                            color_scheme="gray",
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
                    rx.cond(
                        AdminContractEditorState.has_public_detail,
                        rx.link(
                            rx.button("View public detail", size="3"),
                            href=AdminContractEditorState.public_detail_href,
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


def _author_option(option) -> rx.Component:
    return rx.el.option(
        option["display_label"],
        " - ",
        option["secondary_label"],
        value=option["user_id"],
    )


def _category_option(option) -> rx.Component:
    return rx.el.option(option["name"], value=option["id"])


def _secondary_category_chip(option) -> rx.Component:
    selected_button = rx.button(
        rx.vstack(
            rx.hstack(
                rx.text(
                    option["name"],
                    font_weight="700",
                    color="var(--hub-color-text)",
                ),
                rx.badge(
                    "Selected",
                    radius="full",
                    variant="soft",
                    color_scheme="bronze",
                ),
                align="center",
                gap="var(--hub-space-2)",
                width="100%",
            ),
            rx.text(
                option["description"],
                color="var(--hub-color-text-muted)",
                font_size="0.92rem",
                text_align="left",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        type="button",
        variant="soft",
        on_click=AdminContractEditorState.toggle_secondary_category(option["id"]),
        width="100%",
        justify="start",
        padding="1rem 1.05rem",
        border="1px solid rgba(141, 95, 37, 0.32)",
        background="rgba(247, 232, 207, 0.7)",
        white_space="normal",
        height="100%",
    )
    unselected_button = rx.button(
        rx.vstack(
            rx.text(
                option["name"],
                font_weight="700",
                color="var(--hub-color-text)",
            ),
            rx.text(
                option["description"],
                color="var(--hub-color-text-muted)",
                font_size="0.92rem",
                text_align="left",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        type="button",
        variant="ghost",
        on_click=AdminContractEditorState.toggle_secondary_category(option["id"]),
        width="100%",
        justify="start",
        padding="1rem 1.05rem",
        border="1px solid rgba(148, 128, 97, 0.18)",
        background="rgba(255, 250, 242, 0.8)",
        white_space="normal",
        height="100%",
    )
    primary_card = rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(
                    option["name"],
                    font_weight="700",
                    color="var(--hub-color-text)",
                ),
                rx.badge(
                    "Primary",
                    radius="full",
                    variant="soft",
                    color_scheme="bronze",
                ),
                align="center",
                gap="var(--hub-space-2)",
                width="100%",
            ),
            rx.text(
                "Selected above as the primary taxonomy bucket.",
                color="var(--hub-color-text-muted)",
                font_size="0.92rem",
            ),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
        ),
        width="100%",
        padding="1rem 1.05rem",
        border="1px dashed rgba(148, 128, 97, 0.28)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.7)",
    )
    return rx.cond(
        option["is_primary_selected"],
        primary_card,
        rx.cond(option["is_secondary_selected"], selected_button, unselected_button),
    )


def _taxonomy_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading(
                        "Taxonomy and discovery",
                        size="4",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.04em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        "Pick one primary category, add optional supporting categories, and keep "
                        "catalog tags tidy for search and browse ranking.",
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                ),
                rx.badge(
                    AdminContractEditorState.secondary_category_count_label,
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
            rx.grid(
                _editor_field(
                    label="Primary category",
                    control=rx.el.select(
                        rx.el.option("Select a category", value=""),
                        rx.foreach(AdminContractEditorState.category_options, _category_option),
                        name="primary_category_id",
                        value=AdminContractEditorState.primary_category_id_value,
                        on_change=AdminContractEditorState.select_primary_category,
                        style=_select_style(),
                    ),
                    error_message=AdminContractEditorState.primary_category_error,
                    helper_text="The primary category drives the main catalog grouping.",
                ),
                _editor_field(
                    label="Tags",
                    control=_surface_input(
                        name="tags",
                        value=AdminContractEditorState.tags_value,
                        on_change=AdminContractEditorState.set_tags_value,
                        placeholder="escrow, treasury, settlement",
                    ),
                    error_message="",
                    helper_text="Use comma-separated tags for search and browse facets.",
                ),
                _editor_field(
                    label="Featured state",
                    control=rx.el.select(
                        rx.el.option("Standard listing", value="no"),
                        rx.el.option("Featured highlight", value="yes"),
                        name="featured",
                        value=AdminContractEditorState.featured_choice,
                        on_change=AdminContractEditorState.set_featured_choice,
                        style=_select_style(),
                    ),
                    error_message="",
                    helper_text=(
                        "Featured contracts receive stronger placement across discovery surfaces."
                    ),
                ),
                _editor_field(
                    label="Network",
                    control=rx.el.select(
                        rx.el.option("No network label", value=""),
                        *[
                            rx.el.option(member.value.title(), value=member.value)
                            for member in ContractNetwork
                        ],
                        name="network",
                        value=AdminContractEditorState.network_value,
                        on_change=AdminContractEditorState.set_network_value,
                        style=_select_style(),
                    ),
                    error_message=AdminContractEditorState.network_error,
                    helper_text=(
                        "Optional deployment context for public badges and playground metadata."
                    ),
                ),
                columns=rx.breakpoints(initial="1", lg="2"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.vstack(
                _field_label("Secondary categories"),
                rx.text(
                    "Add supporting taxonomy links without duplicating the primary bucket.",
                    font_size="0.9rem",
                    color="var(--hub-color-text-muted)",
                ),
                _field_error(AdminContractEditorState.secondary_categories_error),
                rx.cond(
                    AdminContractEditorState.has_categories,
                    rx.grid(
                        rx.foreach(
                            AdminContractEditorState.category_options,
                            _secondary_category_chip,
                        ),
                        columns=rx.breakpoints(initial="1", md="2"),
                        gap="var(--hub-space-3)",
                        width="100%",
                    ),
                    rx.box(
                        rx.text(
                            "No categories are available yet. Seed the catalog taxonomy before "
                            "saving metadata.",
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
                gap="var(--hub-space-3)",
                width="100%",
                custom_attrs={"data-testid": "admin-contract-editor-taxonomy"},
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.82)",
    )


def _editor_form() -> rx.Component:
    return rx.form(
        rx.vstack(
            _message_banner(AdminContractEditorState.save_success_message, tone="success"),
            _message_banner(AdminContractEditorState.form_error_message, tone="error"),
            rx.grid(
                _editor_field(
                    label="Stable slug",
                    control=_surface_input(
                        name="slug",
                        value=AdminContractEditorState.contract_slug_value,
                        on_change=AdminContractEditorState.set_contract_slug_value,
                        placeholder="escrow-v2",
                        disabled=AdminContractEditorState.is_edit_mode,
                        required=True,
                    ),
                    error_message=AdminContractEditorState.slug_error,
                    helper_text=(
                        "Stable after creation so public and admin routes remain predictable."
                    ),
                ),
                _editor_field(
                    label="Xian contract name",
                    control=_surface_input(
                        name="contract_name",
                        value=AdminContractEditorState.contract_name_value,
                        on_change=AdminContractEditorState.set_contract_name_value,
                        placeholder="con_escrow_v2",
                        required=True,
                    ),
                    error_message=AdminContractEditorState.contract_name_error,
                    helper_text=(
                        "Must match the Xian contract naming rules, for example con_escrow_v2."
                    ),
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            rx.grid(
                _editor_field(
                    label="Display name",
                    control=_surface_input(
                        name="display_name",
                        value=AdminContractEditorState.display_name_value,
                        on_change=AdminContractEditorState.set_display_name_value,
                        placeholder="Escrow V2",
                        required=True,
                    ),
                    error_message=AdminContractEditorState.display_name_error,
                ),
                _editor_field(
                    label="Short summary",
                    control=_surface_input(
                        name="short_summary",
                        value=AdminContractEditorState.short_summary_value,
                        on_change=AdminContractEditorState.set_short_summary_value,
                        placeholder="Streamlined settlement flow for escrow agreements.",
                        required=True,
                    ),
                    error_message=AdminContractEditorState.short_summary_error,
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            _editor_field(
                label="Long description",
                control=_surface_text_area(
                    name="long_description",
                    value=AdminContractEditorState.long_description_value,
                    on_change=AdminContractEditorState.set_long_description_value,
                    placeholder=(
                        "Describe the contract intent, notable behaviors, integration context, "
                        "and any migration notes for curators."
                    ),
                    rows="6",
                ),
                error_message=AdminContractEditorState.long_description_error,
            ),
            rx.box(
                rx.vstack(
                    rx.heading(
                        "Author assignment",
                        size="4",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.04em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        "Link the contract to an internal developer profile when possible. Use a "
                        "fallback label only when the author does not have a local account.",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.grid(
                        _editor_field(
                            label="Internal author",
                            control=rx.el.select(
                                rx.el.option("No internal author selected", value=""),
                                rx.foreach(
                                    AdminContractEditorState.author_options,
                                    _author_option,
                                ),
                                name="author_user_id",
                                value=AdminContractEditorState.author_user_id_value,
                                on_change=AdminContractEditorState.select_author_user,
                                style=_select_style(),
                            ),
                            error_message="",
                            helper_text="Preferred when the author has a profile in the hub.",
                        ),
                        _editor_field(
                            label="Fallback author label",
                            control=_surface_input(
                                name="author_label",
                                value=AdminContractEditorState.author_label_value,
                                on_change=AdminContractEditorState.set_author_label_value,
                                placeholder="Core Team",
                            ),
                            error_message=AdminContractEditorState.author_assignment_error,
                            helper_text="Used only when no internal author is selected.",
                        ),
                        columns=rx.breakpoints(initial="1", md="2"),
                        gap="var(--hub-space-4)",
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
                background="rgba(255, 250, 242, 0.82)",
            ),
            _taxonomy_section(),
            rx.box(
                rx.vstack(
                    rx.heading(
                        "Reference metadata",
                        size="4",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.04em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        "Add optional links and license details that help users evaluate and "
                        "verify the contract before opening source or deployment flows.",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.grid(
                        _editor_field(
                            label="License",
                            control=_surface_input(
                                name="license_name",
                                value=AdminContractEditorState.license_name_value,
                                on_change=AdminContractEditorState.set_license_name_value,
                                placeholder="MIT",
                            ),
                            error_message=AdminContractEditorState.license_name_error,
                        ),
                        _editor_field(
                            label="Documentation URL",
                            control=_surface_input(
                                name="documentation_url",
                                value=AdminContractEditorState.documentation_url_value,
                                on_change=AdminContractEditorState.set_documentation_url_value,
                                placeholder="https://docs.example.com/contracts/escrow-v2",
                            ),
                            error_message=AdminContractEditorState.documentation_url_error,
                        ),
                        _editor_field(
                            label="Source repository URL",
                            control=_surface_input(
                                name="source_repository_url",
                                value=AdminContractEditorState.source_repository_url_value,
                                on_change=AdminContractEditorState.set_source_repository_url_value,
                                placeholder="https://github.com/example/escrow-contracts",
                            ),
                            error_message=AdminContractEditorState.source_repository_url_error,
                        ),
                        columns=rx.breakpoints(initial="1", md="2"),
                        gap="var(--hub-space-4)",
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
                background="rgba(255, 250, 242, 0.82)",
            ),
            rx.flex(
                rx.button(
                    AdminContractEditorState.editor_submit_label,
                    type="submit",
                    size="3",
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                rx.link(
                    rx.button(
                        "Cancel",
                        type="button",
                        size="3",
                        variant="soft",
                        width=rx.breakpoints(initial="100%", sm="auto"),
                    ),
                    href=ADMIN_CONTRACTS_ROUTE,
                    text_decoration="none",
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                direction=rx.breakpoints(initial="column", sm="row"),
                gap="var(--hub-space-3)",
                width="100%",
                justify="end",
            ),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
            custom_attrs={"data-testid": "admin-contract-editor-form"},
        ),
        on_submit=AdminContractEditorState.submit_form,
        width="100%",
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
                AdminContractEditorState.load_error_message,
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


def _editor_page() -> rx.Component:
    return app_shell(
        rx.vstack(
            page_section(_overview_card()),
            page_section(
                _message_banner(AdminContractEditorState.load_error_message, tone="error"),
                rx.cond(
                    AdminContractEditorState.show_missing_contract_state,
                    _missing_contract_state(),
                    _editor_form(),
                ),
                custom_attrs={"data-testid": "admin-contract-editor-page"},
            ),
            gap="var(--hub-space-6)",
            width="100%",
        ),
        page_title=AdminContractEditorState.editor_heading,
        page_intro=AdminContractEditorState.editor_intro,
        page_kicker="Admin workspace",
        auth_state=AdminContractEditorState,
    )


def new_contract() -> rx.Component:
    """Render the admin route for creating a contract."""
    return _editor_page()


def edit_contract() -> rx.Component:
    """Render the admin route for editing a contract."""
    return _editor_page()


__all__ = ["EDIT_ROUTE", "NEW_ROUTE", "ON_LOAD", "edit_contract", "new_contract"]
