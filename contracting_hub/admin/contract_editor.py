"""Admin contract-editor route scaffolding."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import app_shell, page_section
from contracting_hub.states.admin_contracts import AdminContractsState
from contracting_hub.states.auth import AuthState
from contracting_hub.utils.meta import ADMIN_CONTRACT_CREATE_ROUTE, ADMIN_CONTRACT_EDIT_ROUTE

NEW_ROUTE = ADMIN_CONTRACT_CREATE_ROUTE
EDIT_ROUTE = ADMIN_CONTRACT_EDIT_ROUTE
ON_LOAD = [AuthState.guard_admin_route, AdminContractsState.sync_auth_state]


def _placeholder_body(title: str, body: str) -> rx.Component:
    return page_section(
        rx.box(
            rx.vstack(
                rx.badge(
                    "Editor scaffold",
                    radius="full",
                    variant="soft",
                    color_scheme="bronze",
                    width="fit-content",
                ),
                rx.heading(
                    title,
                    size="5",
                    font_family="var(--hub-font-display)",
                    letter_spacing="-0.05em",
                    color="var(--hub-color-text)",
                ),
                rx.text(
                    body,
                    color="var(--hub-color-text-muted)",
                    max_width="38rem",
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
        ),
        custom_attrs={"data-testid": "admin-contract-editor-placeholder"},
    )


def new_contract() -> rx.Component:
    """Render the placeholder route for creating a contract."""
    return app_shell(
        _placeholder_body(
            "Create contract",
            (
                "The dedicated metadata editor lands in the next task. "
                "The index route already points here so create actions stay "
                "on a real admin path."
            ),
        ),
        page_title="Create contract",
        page_intro=(
            "Contract creation is scaffolded so the admin index has a stable "
            "destination for create actions."
        ),
        page_kicker="Admin workspace",
        auth_state=AdminContractsState,
    )


def edit_contract() -> rx.Component:
    """Render the placeholder route for editing a contract."""
    return app_shell(
        _placeholder_body(
            "Edit contract",
            (
                "The full metadata editor is the next task. "
                "This route exists now so index-level edit actions do not "
                "dead-end."
            ),
        ),
        page_title="Edit contract",
        page_intro=(
            "Metadata editing is scaffolded behind a stable admin route and will be filled in next."
        ),
        page_kicker="Admin workspace",
        auth_state=AdminContractsState,
    )


__all__ = ["EDIT_ROUTE", "NEW_ROUTE", "ON_LOAD", "edit_contract", "new_contract"]
