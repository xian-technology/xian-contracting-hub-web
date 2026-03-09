"""Admin contract-relation manager page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import app_shell, page_section
from contracting_hub.models import ContractRelationType
from contracting_hub.services.admin_contract_relations import (
    format_admin_contract_relation_type_label,
)
from contracting_hub.states.admin_contract_relations import AdminContractRelationManagerState
from contracting_hub.states.auth import AuthState
from contracting_hub.utils.meta import ADMIN_CONTRACT_RELATIONS_ROUTE, ADMIN_CONTRACTS_ROUTE

ROUTE = ADMIN_CONTRACT_RELATIONS_ROUTE
ON_LOAD = [AuthState.guard_admin_route, AdminContractRelationManagerState.load_page]
_RELATION_TYPE_OPTIONS = tuple(
    (
        relation_type.value,
        format_admin_contract_relation_type_label(relation_type),
    )
    for relation_type in (
        ContractRelationType.DEPENDS_ON,
        ContractRelationType.COMPANION,
        ContractRelationType.EXAMPLE_FOR,
        ContractRelationType.EXTENDS,
        ContractRelationType.SUPERSEDES,
    )
)


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


def _text_area_style() -> dict[str, str]:
    return {
        **_select_style(),
        "minHeight": "7rem",
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
    helper_text: object | None = None,
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
                        "Relation manager",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.heading(
                        AdminContractRelationManagerState.page_heading,
                        size="6",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.05em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        AdminContractRelationManagerState.page_intro,
                        color="var(--hub-color-text-muted)",
                        max_width="46rem",
                    ),
                    rx.text(
                        AdminContractRelationManagerState.contract_name,
                        font_family="var(--hub-font-mono)",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.flex(
                        _status_badge(
                            AdminContractRelationManagerState.contract_status_label,
                            AdminContractRelationManagerState.contract_status_color_scheme,
                        ),
                        rx.badge(
                            AdminContractRelationManagerState.latest_public_version_label,
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
                    rx.link(
                        rx.button("Edit metadata", size="3", variant="soft"),
                        href=AdminContractRelationManagerState.metadata_edit_href,
                        text_decoration="none",
                    ),
                    rx.link(
                        rx.button("Manage versions", size="3", variant="soft"),
                        href=AdminContractRelationManagerState.versions_href,
                        text_decoration="none",
                    ),
                    rx.cond(
                        AdminContractRelationManagerState.has_public_detail,
                        rx.link(
                            rx.button("View public detail", size="3"),
                            href=AdminContractRelationManagerState.public_detail_href,
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


def _target_option(option) -> rx.Component:
    return rx.el.option(
        option["display_name"],
        " (",
        option["contract_name"],
        ") - ",
        option["status_label"],
        value=option["contract_id"],
    )


def _relation_type_option(option: tuple[str, str]) -> rx.Component:
    return rx.el.option(option[1], value=option[0])


def _relation_form() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading(
                        AdminContractRelationManagerState.relation_form_heading,
                        size="5",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        (
                            "Outgoing links are managed from the current contract. Incoming links "
                            "remain visible below and link back to their source workspace."
                        ),
                        color="var(--hub-color-text-muted)",
                        max_width="42rem",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.cond(
                    AdminContractRelationManagerState.is_editing_relation,
                    rx.button(
                        "Cancel edit",
                        size="2",
                        variant="soft",
                        on_click=AdminContractRelationManagerState.cancel_edit_relation,
                    ),
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
                width="100%",
            ),
            _message_banner(AdminContractRelationManagerState.save_success_message, tone="success"),
            _message_banner(AdminContractRelationManagerState.form_error_message, tone="error"),
            rx.form(
                rx.grid(
                    _editor_field(
                        label="Related contract",
                        control=rx.el.select(
                            rx.el.option("Select related contract", value=""),
                            rx.foreach(
                                AdminContractRelationManagerState.target_options,
                                _target_option,
                            ),
                            name="target_contract_id",
                            value=AdminContractRelationManagerState.target_contract_id_value,
                            on_change=AdminContractRelationManagerState.set_target_contract_id_value,
                            style=_select_style(),
                        ),
                        error_message=AdminContractRelationManagerState.target_contract_error,
                        helper_text=(
                            "Choose the contract that this entry points to. "
                            "Create another contract first if the catalog only contains this entry."
                        ),
                    ),
                    _editor_field(
                        label="Relation type",
                        control=rx.el.select(
                            rx.el.option("Select relation type", value=""),
                            *[_relation_type_option(option) for option in _RELATION_TYPE_OPTIONS],
                            name="relation_type",
                            value=AdminContractRelationManagerState.relation_type_value,
                            on_change=AdminContractRelationManagerState.set_relation_type_value,
                            style=_select_style(),
                        ),
                        error_message=AdminContractRelationManagerState.relation_type_error,
                        helper_text="Use the directional type that best describes the dependency.",
                    ),
                    columns=rx.breakpoints(initial="1", lg="2"),
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                _editor_field(
                    label="Internal note",
                    control=rx.el.textarea(
                        name="note",
                        value=AdminContractRelationManagerState.note_value,
                        on_change=AdminContractRelationManagerState.set_note_value,
                        placeholder="Optional internal note for admin context",
                        style=_text_area_style(),
                    ),
                    error_message=AdminContractRelationManagerState.note_error,
                    helper_text="Notes stay in admin context and help future curation decisions.",
                ),
                rx.flex(
                    rx.button(
                        AdminContractRelationManagerState.relation_submit_label,
                        type="submit",
                        size="3",
                        disabled=~AdminContractRelationManagerState.has_target_options,
                    ),
                    direction=rx.breakpoints(initial="column", sm="row"),
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                on_submit=AdminContractRelationManagerState.submit_form,
                width="100%",
                custom_attrs={"data-testid": "admin-contract-relation-form"},
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
        custom_attrs={"data-testid": "admin-contract-relation-editor"},
    )


def _relation_row(row, *, direction: str) -> rx.Component:
    management_label = "Target workspace" if direction == "outgoing" else "Source workspace"
    note_empty_copy = (
        "No admin note was saved for this outgoing relation."
        if direction == "outgoing"
        else "No admin note was saved for this incoming relation."
    )
    action_buttons: list[rx.Component] = []
    if direction == "outgoing":
        action_buttons.append(
            rx.button(
                "Edit",
                size="2",
                variant="soft",
                on_click=AdminContractRelationManagerState.start_edit_relation(row["relation_id"]),
            )
        )
    action_buttons.append(
        rx.link(
            rx.button(management_label, size="2", variant="soft"),
            href=row["relation_manager_href"],
            text_decoration="none",
        )
    )
    if direction == "outgoing":
        action_buttons.append(
            rx.button(
                "Remove",
                size="2",
                variant="outline",
                color_scheme="tomato",
                on_click=AdminContractRelationManagerState.delete_relation(row["relation_id"]),
            )
        )
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.flex(
                        _status_badge(
                            row["relation_label"],
                            "bronze",
                        ),
                        _status_badge(
                            row["counterpart_status_label"],
                            row["counterpart_status_color_scheme"],
                        ),
                        gap="var(--hub-space-2)",
                        wrap="wrap",
                    ),
                    rx.heading(
                        row["counterpart_display_name"],
                        size="4",
                        font_family="var(--hub-font-display)",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        row["counterpart_contract_name"],
                        font_family="var(--hub-font-mono)",
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-2)",
                    width="100%",
                ),
                rx.flex(
                    *action_buttons,
                    rx.cond(
                        row["has_public_detail"],
                        rx.link(
                            rx.button("Public view", size="2", variant="soft"),
                            href=row["public_detail_href"],
                            text_decoration="none",
                        ),
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
            rx.box(
                rx.text(
                    "Admin note",
                    font_size="0.72rem",
                    text_transform="uppercase",
                    letter_spacing="0.08em",
                    color="var(--hub-color-text-muted)",
                ),
                rx.text(
                    rx.cond(row["note"] != "", row["note"], note_empty_copy),
                    color="var(--hub-color-text-muted)",
                ),
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
        background="rgba(255, 250, 242, 0.78)",
        custom_attrs={"data-testid": f"admin-contract-relation-row-{direction}"},
    )


def _outgoing_relation_row(row) -> rx.Component:
    return _relation_row(row, direction="outgoing")


def _incoming_relation_row(row) -> rx.Component:
    return _relation_row(row, direction="incoming")


def _relation_empty_state(title: str, body: str) -> rx.Component:
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
                max_width="40rem",
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


def _outgoing_relations_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "Outgoing relations",
                size="5",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                (
                    "These links define how the current contract depends on, extends, or "
                    "otherwise maps to other curated entries."
                ),
                color="var(--hub-color-text-muted)",
                max_width="44rem",
            ),
            rx.cond(
                AdminContractRelationManagerState.has_outgoing_relations,
                rx.vstack(
                    rx.foreach(
                        AdminContractRelationManagerState.outgoing_relations,
                        _outgoing_relation_row,
                    ),
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                _relation_empty_state(
                    "No outgoing relations yet",
                    "Add a typed link above to connect this contract to a related entry.",
                ),
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
        custom_attrs={"data-testid": "admin-contract-relation-outgoing"},
    )


def _incoming_relations_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "Incoming relations",
                size="5",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                (
                    "Incoming links are shown for context. Open the source workspace when you need "
                    "to change how another contract points to this one."
                ),
                color="var(--hub-color-text-muted)",
                max_width="44rem",
            ),
            rx.cond(
                AdminContractRelationManagerState.has_incoming_relations,
                rx.vstack(
                    rx.foreach(
                        AdminContractRelationManagerState.incoming_relations,
                        _incoming_relation_row,
                    ),
                    gap="var(--hub-space-4)",
                    width="100%",
                ),
                _relation_empty_state(
                    "No incoming relations yet",
                    "No other curated contracts currently point to this entry.",
                ),
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
        custom_attrs={"data-testid": "admin-contract-relation-incoming"},
    )


def _missing_contract_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "Contract not found",
                size="5",
                font_family="var(--hub-font-display)",
                color="var(--hub-color-text)",
            ),
            rx.text(
                AdminContractRelationManagerState.load_error_message,
                color="var(--hub-color-text-muted)",
                max_width="40rem",
            ),
            rx.link(
                rx.button("Return to admin contracts", size="3", variant="soft"),
                href=ADMIN_CONTRACTS_ROUTE,
                text_decoration="none",
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-7)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-lg)",
        background="rgba(255, 252, 246, 0.97)",
        box_shadow="var(--hub-shadow-panel)",
    )


def index() -> rx.Component:
    """Render the admin contract-relation manager."""
    return app_shell(
        page_section(
            rx.cond(
                AdminContractRelationManagerState.show_missing_contract_state,
                _missing_contract_state(),
                rx.vstack(
                    _overview_card(),
                    _message_banner(
                        AdminContractRelationManagerState.load_error_message,
                        tone="error",
                    ),
                    _relation_form(),
                    _outgoing_relations_panel(),
                    _incoming_relations_panel(),
                    gap="var(--hub-space-6)",
                    width="100%",
                ),
            ),
            gap="var(--hub-space-6)",
            width="100%",
            custom_attrs={"data-testid": "admin-contract-relation-page"},
        ),
        auth_state=AdminContractRelationManagerState,
    )
