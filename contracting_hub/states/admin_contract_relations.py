"""Admin contract-relation manager state."""

from __future__ import annotations

from typing import Any, TypedDict

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import User
from contracting_hub.services.admin_contract_relations import (
    AdminContractRelationEntry,
    AdminContractRelationManagerServiceError,
    AdminContractRelationManagerSnapshot,
    AdminContractRelationTargetOption,
    build_empty_admin_contract_relation_manager_snapshot,
    create_admin_contract_relation,
    delete_admin_contract_relation,
    load_admin_contract_relation_manager_snapshot_safe,
    update_admin_contract_relation,
)
from contracting_hub.services.auth import AuthServiceError, logout_user, resolve_current_user
from contracting_hub.states.auth import AUTH_SESSION_COOKIE_NAME
from contracting_hub.utils.meta import HOME_ROUTE

_SETTINGS = get_settings()


class AdminContractRelationTargetOptionPayload(TypedDict):
    """Serialized target-contract option stored in state."""

    contract_id: str
    slug: str
    display_name: str
    contract_name: str
    status_label: str
    status_color_scheme: str


class AdminContractRelationRowPayload(TypedDict):
    """Serialized relation row stored in state."""

    relation_id: str
    relation_type_value: str
    relation_label: str
    note: str
    counterpart_contract_id: str
    counterpart_slug: str
    counterpart_display_name: str
    counterpart_contract_name: str
    counterpart_status_label: str
    counterpart_status_color_scheme: str
    public_detail_href: str
    has_public_detail: bool
    relation_manager_href: str


class AdminContractRelationManagerState(rx.State):
    """Admin-only state for directional relation management."""

    auth_session_token: str = rx.Cookie(
        "",
        name=AUTH_SESSION_COOKIE_NAME,
        path="/",
        same_site="lax",
        secure=_SETTINGS.environment == "production",
    )
    current_user_id: int | None = None
    current_user_email: str | None = None
    current_username: str | None = None
    current_display_name: str | None = None
    contract_slug: str = ""
    contract_display_name: str = ""
    contract_name: str = ""
    contract_status_label: str = "Draft"
    contract_status_color_scheme: str = "gray"
    latest_public_version_label: str = "No public version yet"
    public_detail_href: str = ""
    metadata_edit_href: str = ""
    versions_href: str = ""
    editing_relation_id: str = ""
    target_contract_id_value: str = ""
    relation_type_value: str = ""
    note_value: str = ""
    target_options: list[AdminContractRelationTargetOptionPayload] = []
    outgoing_relations: list[AdminContractRelationRowPayload] = []
    incoming_relations: list[AdminContractRelationRowPayload] = []
    save_success_message: str = ""
    form_error_message: str = ""
    load_error_message: str = ""
    target_contract_error: str = ""
    relation_type_error: str = ""
    note_error: str = ""

    @rx.var
    def is_authenticated(self) -> bool:
        """Return whether the current browser has an active user session."""
        return self.current_user_id is not None

    @rx.var
    def current_identity_label(self) -> str:
        """Return the primary account label for session-aware shell navigation."""
        if self.current_display_name:
            return self.current_display_name
        if self.current_username:
            return f"@{self.current_username}"
        if self.current_user_email:
            return self.current_user_email
        return "Account"

    @rx.var
    def current_identity_secondary(self) -> str:
        """Return a secondary account line for the authenticated shell header."""
        if self.current_username and self.current_display_name:
            return f"@{self.current_username}"
        if self.current_user_email and self.current_user_email != self.current_identity_label:
            return self.current_user_email
        return ""

    @rx.var
    def has_current_identity_secondary(self) -> bool:
        """Return whether the authenticated shell header has a secondary line."""
        return bool(self.current_identity_secondary)

    @rx.var
    def page_heading(self) -> str:
        """Return the primary page heading for the relation manager."""
        if self.contract_display_name:
            return f"Manage relations for {self.contract_display_name}"
        return "Manage contract relations"

    @rx.var
    def page_intro(self) -> str:
        """Return the primary page intro copy."""
        return (
            "Create and maintain typed links from this contract to related entries, then review "
            "incoming context without leaving the admin workspace."
        )

    @rx.var
    def has_public_detail(self) -> bool:
        """Return whether the contract currently has a public detail page."""
        return bool(self.public_detail_href)

    @rx.var
    def has_target_options(self) -> bool:
        """Return whether other contracts are available as relation targets."""
        return bool(self.target_options)

    @rx.var
    def has_outgoing_relations(self) -> bool:
        """Return whether the current contract has outgoing relations."""
        return bool(self.outgoing_relations)

    @rx.var
    def has_incoming_relations(self) -> bool:
        """Return whether the current contract has incoming relations."""
        return bool(self.incoming_relations)

    @rx.var
    def is_editing_relation(self) -> bool:
        """Return whether the relation form is editing an existing row."""
        return bool(self.editing_relation_id)

    @rx.var
    def relation_form_heading(self) -> str:
        """Return the relation-form section heading."""
        return "Edit outgoing relation" if self.is_editing_relation else "Add outgoing relation"

    @rx.var
    def relation_submit_label(self) -> str:
        """Return the relation-form submit label."""
        return "Save relation changes" if self.is_editing_relation else "Add relation"

    @rx.var
    def show_missing_contract_state(self) -> bool:
        """Return whether the requested route slug could not be resolved."""
        return (
            bool(self.contract_slug)
            and not self.contract_display_name
            and bool(self.load_error_message)
        )

    def sync_auth_state(self) -> None:
        """Refresh the current-user shell snapshot from the auth cookie."""
        self._apply_user_snapshot(self._resolve_user_from_cookie())

    def load_page(self) -> None:
        """Load the admin relation manager from the current route params."""
        requested_slug = str(self.router.page.params.get("slug", "")).strip().lower()
        self._clear_feedback()
        self._reset_form()
        self.sync_auth_state()
        try:
            snapshot = load_admin_contract_relation_manager_snapshot_safe(
                contract_slug=requested_slug or None
            )
        except AdminContractRelationManagerServiceError as error:
            self.load_error_message = str(error)
            snapshot = build_empty_admin_contract_relation_manager_snapshot(
                contract_slug=requested_slug or None
            )
        self._apply_snapshot(snapshot)

    def logout_current_user(self) -> rx.event.EventSpec:
        """Invalidate the current cookie-backed session from the admin shell."""
        if self.auth_session_token:
            with session_scope() as session:
                logout_user(
                    session=session,
                    session_token=self.auth_session_token,
                )

        self.auth_session_token = ""
        self._apply_user_snapshot(None)
        self._clear_feedback()
        self._reset_form()
        return rx.redirect(HOME_ROUTE, replace=True)

    def set_target_contract_id_value(self, value: str) -> None:
        """Update the selected relation-target contract."""
        self.target_contract_id_value = value
        self.target_contract_error = ""

    def set_relation_type_value(self, value: str) -> None:
        """Update the selected relation type."""
        self.relation_type_value = value
        self.relation_type_error = ""

    def set_note_value(self, value: str) -> None:
        """Update the optional relation note."""
        self.note_value = value
        self.note_error = ""

    def start_edit_relation(self, relation_id: str) -> None:
        """Populate the relation form from one outgoing relation row."""
        row = next(
            (
                relation
                for relation in self.outgoing_relations
                if relation["relation_id"] == relation_id
            ),
            None,
        )
        if row is None:
            self.form_error_message = "The selected relation is no longer available."
            return
        self._clear_feedback()
        self.editing_relation_id = row["relation_id"]
        self.target_contract_id_value = row["counterpart_contract_id"]
        self.relation_type_value = row["relation_type_value"]
        self.note_value = row["note"]

    def cancel_edit_relation(self) -> None:
        """Return the relation form to create mode."""
        self._reset_form()
        self._clear_feedback()

    def submit_form(self, form_data: dict[str, Any]) -> None:
        """Persist the relation form for the current contract."""
        del form_data
        self._clear_feedback()
        try:
            with session_scope() as session:
                if self.is_editing_relation:
                    update_admin_contract_relation(
                        session=session,
                        session_token=self.auth_session_token,
                        contract_slug=self.contract_slug,
                        relation_id=self.editing_relation_id,
                        target_contract_id=self.target_contract_id_value,
                        relation_type=self.relation_type_value,
                        note=self.note_value,
                    )
                else:
                    create_admin_contract_relation(
                        session=session,
                        session_token=self.auth_session_token,
                        contract_slug=self.contract_slug,
                        target_contract_id=self.target_contract_id_value,
                        relation_type=self.relation_type_value,
                        note=self.note_value,
                    )
        except (AdminContractRelationManagerServiceError, AuthServiceError) as error:
            self._apply_submit_error(error)
            return

        success_message = "Relation updated." if self.is_editing_relation else "Relation added."
        self._reset_form()
        self._reload_snapshot()
        self.save_success_message = success_message

    def delete_relation(self, relation_id: str) -> None:
        """Delete one outgoing relation row."""
        self._clear_feedback()
        try:
            with session_scope() as session:
                delete_admin_contract_relation(
                    session=session,
                    session_token=self.auth_session_token,
                    contract_slug=self.contract_slug,
                    relation_id=relation_id,
                )
        except (AdminContractRelationManagerServiceError, AuthServiceError) as error:
            self._apply_submit_error(error)
            return

        if relation_id == self.editing_relation_id:
            self._reset_form()
        self._reload_snapshot()
        self.save_success_message = "Relation removed."

    def _reload_snapshot(self) -> None:
        snapshot = load_admin_contract_relation_manager_snapshot_safe(
            contract_slug=self.contract_slug or None
        )
        self._apply_snapshot(snapshot)

    def _resolve_user_from_cookie(self) -> User | None:
        with session_scope() as session:
            return resolve_current_user(
                session=session,
                session_token=self.auth_session_token,
            )

    def _apply_user_snapshot(self, user: User | None) -> None:
        if user is None:
            if self.auth_session_token:
                self.auth_session_token = ""
            self.current_user_id = None
            self.current_user_email = None
            self.current_username = None
            self.current_display_name = None
            return

        self.current_user_id = user.id
        self.current_user_email = user.email
        self.current_username = user.profile.username if user.profile is not None else None
        self.current_display_name = user.profile.display_name if user.profile is not None else None

    def _apply_snapshot(self, snapshot: AdminContractRelationManagerSnapshot) -> None:
        self.contract_slug = snapshot.slug
        self.contract_display_name = snapshot.display_name
        self.contract_name = snapshot.contract_name
        self.contract_status_label = snapshot.contract_status.value.title()
        self.contract_status_color_scheme = _status_color_scheme(snapshot.contract_status.value)
        self.latest_public_version_label = snapshot.latest_public_version or "No public version yet"
        self.public_detail_href = snapshot.public_detail_href or ""
        self.metadata_edit_href = snapshot.edit_href
        self.versions_href = snapshot.versions_href
        self.target_options = [
            _serialize_target_option(option) for option in snapshot.target_options
        ]
        self.outgoing_relations = [
            _serialize_relation_row(entry) for entry in snapshot.outgoing_relations
        ]
        self.incoming_relations = [
            _serialize_relation_row(entry) for entry in snapshot.incoming_relations
        ]

    def _apply_submit_error(self, error: Exception) -> None:
        if isinstance(error, AuthServiceError):
            self.form_error_message = str(error)
            return
        if not isinstance(error, AdminContractRelationManagerServiceError):
            self.form_error_message = str(error)
            return

        if error.field == "target_contract_id":
            self.target_contract_error = str(error)
            return
        if error.field == "relation_type":
            self.relation_type_error = str(error)
            return
        if error.field == "note":
            self.note_error = str(error)
            return
        self.form_error_message = str(error)

    def _clear_feedback(self) -> None:
        self.save_success_message = ""
        self.form_error_message = ""
        self.load_error_message = ""
        self.target_contract_error = ""
        self.relation_type_error = ""
        self.note_error = ""

    def _reset_form(self) -> None:
        self.editing_relation_id = ""
        self.target_contract_id_value = ""
        self.relation_type_value = ""
        self.note_value = ""


def _serialize_target_option(
    option: AdminContractRelationTargetOption,
) -> AdminContractRelationTargetOptionPayload:
    return {
        "contract_id": str(option.contract_id),
        "slug": option.slug,
        "display_name": option.display_name,
        "contract_name": option.contract_name,
        "status_label": option.status.value.title(),
        "status_color_scheme": _status_color_scheme(option.status.value),
    }


def _serialize_relation_row(entry: AdminContractRelationEntry) -> AdminContractRelationRowPayload:
    return {
        "relation_id": str(entry.relation_id),
        "relation_type_value": entry.relation_type.value,
        "relation_label": entry.relation_label,
        "note": entry.note or "",
        "counterpart_contract_id": str(entry.counterpart_contract_id),
        "counterpart_slug": entry.counterpart_slug,
        "counterpart_display_name": entry.counterpart_display_name,
        "counterpart_contract_name": entry.counterpart_contract_name,
        "counterpart_status_label": entry.counterpart_status.value.title(),
        "counterpart_status_color_scheme": _status_color_scheme(entry.counterpart_status.value),
        "public_detail_href": entry.public_detail_href or "",
        "has_public_detail": entry.public_detail_href is not None,
        "relation_manager_href": entry.relation_manager_href,
    }


def _status_color_scheme(status_value: str) -> str:
    if status_value == "published":
        return "green"
    if status_value == "deprecated":
        return "amber"
    if status_value == "archived":
        return "gray"
    return "bronze"


__all__ = ["AdminContractRelationManagerState"]
