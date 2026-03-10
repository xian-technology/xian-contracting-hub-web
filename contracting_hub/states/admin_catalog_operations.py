"""State for the admin catalog-operations workspace."""

from __future__ import annotations

from typing import Any, TypedDict

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import PublicationStatus, User
from contracting_hub.services.admin_catalog_operations import (
    AdminAuditLogInspectionEntry,
    AdminCatalogOperationsError,
    AdminCatalogOperationsSnapshot,
    AdminCategoryManagementEntry,
    AdminFeaturedContractEntry,
    build_empty_admin_catalog_operations_snapshot,
    create_admin_category,
    delete_admin_category,
    load_admin_catalog_operations_snapshot_safe,
    set_admin_contract_featured_state,
    update_admin_category,
)
from contracting_hub.services.auth import AuthServiceError, logout_user, resolve_current_user
from contracting_hub.states.auth import AUTH_SESSION_COOKIE_NAME
from contracting_hub.utils.meta import HOME_ROUTE

_SETTINGS = get_settings()


class AdminCategoryRowPayload(TypedDict):
    """Serialized category row stored in state."""

    category_id: str
    slug: str
    name: str
    description: str
    sort_order_label: str
    contract_count_label: str
    updated_at_label: str
    can_delete: bool


class AdminFeaturedContractRowPayload(TypedDict):
    """Serialized featured-curation row stored in state."""

    contract_id: str
    slug: str
    display_name: str
    contract_name: str
    author_name: str
    categories_label: str
    latest_public_version: str
    status_label: str
    status_color_scheme: str
    is_featured: bool
    featured_label: str
    toggle_label: str
    toggle_variant: str
    updated_at_label: str
    public_detail_href: str
    has_public_detail: bool
    edit_href: str


class AdminAuditLogRowPayload(TypedDict):
    """Serialized audit-log row stored in state."""

    audit_log_id: str
    created_at_label: str
    admin_label: str
    action_label: str
    entity_type_label: str
    summary: str
    details_pretty_json: str
    has_details: bool


class AdminCatalogOperationsState(rx.State):
    """Admin-only state for category, curation, and audit-log operations."""

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
    load_state: str = "loading"
    load_error_message: str = ""
    category_slug_value: str = ""
    category_name_value: str = ""
    category_description_value: str = ""
    category_sort_order_value: str = "0"
    editing_category_id: str = ""
    category_success_message: str = ""
    category_form_error: str = ""
    category_slug_error: str = ""
    category_name_error: str = ""
    category_description_error: str = ""
    category_sort_order_error: str = ""
    featured_success_message: str = ""
    featured_error_message: str = ""
    category_count_label: str = "0 categories"
    featured_count_label: str = "0 featured contracts"
    audit_log_count_label: str = "0 recent audit entries"
    category_rows: list[AdminCategoryRowPayload] = []
    featured_contract_rows: list[AdminFeaturedContractRowPayload] = []
    audit_log_rows: list[AdminAuditLogRowPayload] = []

    @rx.var
    def is_authenticated(self) -> bool:
        """Return whether the current browser has an active user session."""
        return self.current_user_id is not None

    @rx.var
    def is_loading(self) -> bool:
        """Return whether the admin operations workspace is loading."""
        return self.load_state == "loading"

    @rx.var
    def has_load_error(self) -> bool:
        """Return whether the admin operations workspace failed to load."""
        return self.load_state == "error" and bool(self.load_error_message)

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
    def is_editing_category(self) -> bool:
        """Return whether the category form is editing an existing row."""
        return bool(self.editing_category_id)

    @rx.var
    def category_form_heading(self) -> str:
        """Return the category-form section heading."""
        return "Edit category" if self.is_editing_category else "Add category"

    @rx.var
    def category_submit_label(self) -> str:
        """Return the category-form submit label."""
        return "Save category changes" if self.is_editing_category else "Create category"

    @rx.var
    def has_categories(self) -> bool:
        """Return whether any categories are available to render."""
        return bool(self.category_rows)

    @rx.var
    def has_featured_contracts(self) -> bool:
        """Return whether any public contracts are available for curation."""
        return bool(self.featured_contract_rows)

    @rx.var
    def has_audit_logs(self) -> bool:
        """Return whether any audit-log rows are available to inspect."""
        return bool(self.audit_log_rows)

    def sync_auth_state(self) -> None:
        """Refresh the current-user shell snapshot from the auth cookie."""
        self._apply_user_snapshot(self._resolve_user_from_cookie())

    def load_page(self) -> None:
        """Load the admin operations workspace."""
        self.load_state = "loading"
        self._clear_feedback()
        self._reset_category_form()
        self.sync_auth_state()
        if self.current_user_id is None:
            self.load_error_message = "Administrator access is required to view this workspace."
            self.load_state = "error"
            return

        try:
            snapshot = load_admin_catalog_operations_snapshot_safe()
        except Exception as error:
            snapshot = build_empty_admin_catalog_operations_snapshot()
            self._apply_snapshot(snapshot)
            self.load_error_message = str(error)
            self.load_state = "error"
            return

        self._apply_snapshot(snapshot)
        self.load_state = "ready"

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
        self._reset_category_form()
        return rx.redirect(HOME_ROUTE, replace=True)

    def set_category_slug_value(self, value: str) -> None:
        """Update the editable category slug field."""
        self.category_slug_value = value
        self.category_slug_error = ""

    def set_category_name_value(self, value: str) -> None:
        """Update the editable category name field."""
        self.category_name_value = value
        self.category_name_error = ""

    def set_category_description_value(self, value: str) -> None:
        """Update the editable category description field."""
        self.category_description_value = value
        self.category_description_error = ""

    def set_category_sort_order_value(self, value: str) -> None:
        """Update the editable category sort-order field."""
        self.category_sort_order_value = value
        self.category_sort_order_error = ""

    def start_edit_category(self, category_id: str) -> None:
        """Populate the category form from one existing row."""
        row = next(
            (category for category in self.category_rows if category["category_id"] == category_id),
            None,
        )
        if row is None:
            self.category_form_error = "The selected category is no longer available."
            return

        self._clear_category_feedback()
        self.editing_category_id = row["category_id"]
        self.category_slug_value = row["slug"]
        self.category_name_value = row["name"]
        self.category_description_value = row["description"]
        self.category_sort_order_value = row["sort_order_label"]

    def cancel_category_edit(self) -> None:
        """Return the category form to create mode."""
        self._reset_category_form()
        self._clear_category_feedback()

    def submit_category_form(self, form_data: dict[str, Any]) -> None:
        """Create or update one category from the admin form."""
        del form_data
        self._clear_category_feedback()
        try:
            with session_scope() as session:
                if self.editing_category_id:
                    update_admin_category(
                        session=session,
                        session_token=self.auth_session_token,
                        category_id=int(self.editing_category_id),
                        slug=self.category_slug_value,
                        name=self.category_name_value,
                        description=self.category_description_value,
                        sort_order=self.category_sort_order_value,
                    )
                else:
                    create_admin_category(
                        session=session,
                        session_token=self.auth_session_token,
                        slug=self.category_slug_value,
                        name=self.category_name_value,
                        description=self.category_description_value,
                        sort_order=self.category_sort_order_value,
                    )
        except (AdminCatalogOperationsError, AuthServiceError) as error:
            self._apply_category_error(error)
            return

        self.category_success_message = (
            "Category updated." if self.editing_category_id else "Category created."
        )
        self._reset_category_form()
        self._reload_snapshot()

    def delete_category(self, category_id: str) -> None:
        """Delete one category when it is safe to do so."""
        self._clear_category_feedback()
        try:
            with session_scope() as session:
                delete_admin_category(
                    session=session,
                    session_token=self.auth_session_token,
                    category_id=int(category_id),
                )
        except (AdminCatalogOperationsError, AuthServiceError) as error:
            self._apply_category_error(error)
            return

        self.category_success_message = "Category deleted."
        self._reset_category_form()
        self._reload_snapshot()

    def toggle_contract_featured(self, contract_slug: str) -> None:
        """Toggle one contract in or out of featured curation."""
        row = next(
            (
                contract
                for contract in self.featured_contract_rows
                if contract["slug"] == contract_slug
            ),
            None,
        )
        if row is None:
            self.featured_error_message = "The selected contract is no longer available."
            return

        self._clear_featured_feedback()
        try:
            with session_scope() as session:
                set_admin_contract_featured_state(
                    session=session,
                    session_token=self.auth_session_token,
                    contract_slug=contract_slug,
                    featured=not row["is_featured"],
                )
        except (AdminCatalogOperationsError, AuthServiceError) as error:
            self.featured_error_message = str(error)
            return

        self.featured_success_message = (
            "Contract added to featured content."
            if not row["is_featured"]
            else "Contract removed from featured content."
        )
        self._reload_snapshot()

    def _reload_snapshot(self) -> None:
        self._apply_snapshot(load_admin_catalog_operations_snapshot_safe())

    def _apply_snapshot(self, snapshot: AdminCatalogOperationsSnapshot) -> None:
        self.category_count_label = _category_count_label(len(snapshot.categories))
        self.featured_count_label = _featured_count_label(snapshot.featured_contracts)
        self.audit_log_count_label = _audit_log_count_label(len(snapshot.audit_logs))
        self.category_rows = [_serialize_category_row(entry) for entry in snapshot.categories]
        self.featured_contract_rows = [
            _serialize_featured_contract_row(entry) for entry in snapshot.featured_contracts
        ]
        self.audit_log_rows = [_serialize_audit_log_row(entry) for entry in snapshot.audit_logs]

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
        profile = user.profile
        if profile is None:
            self.current_username = None
            self.current_display_name = None
            return
        self.current_username = profile.username
        self.current_display_name = profile.display_name

    def _apply_category_error(self, error: Exception) -> None:
        if isinstance(error, AdminCatalogOperationsError):
            if error.field == "slug":
                self.category_slug_error = str(error)
                return
            if error.field == "name":
                self.category_name_error = str(error)
                return
            if error.field == "description":
                self.category_description_error = str(error)
                return
            if error.field == "sort_order":
                self.category_sort_order_error = str(error)
                return
        self.category_form_error = str(error)

    def _clear_feedback(self) -> None:
        self._clear_category_feedback()
        self._clear_featured_feedback()
        self.load_error_message = ""

    def _clear_category_feedback(self) -> None:
        self.category_success_message = ""
        self.category_form_error = ""
        self.category_slug_error = ""
        self.category_name_error = ""
        self.category_description_error = ""
        self.category_sort_order_error = ""

    def _clear_featured_feedback(self) -> None:
        self.featured_success_message = ""
        self.featured_error_message = ""

    def _reset_category_form(self) -> None:
        self.editing_category_id = ""
        self.category_slug_value = ""
        self.category_name_value = ""
        self.category_description_value = ""
        self.category_sort_order_value = "0"


def _serialize_category_row(entry: AdminCategoryManagementEntry) -> AdminCategoryRowPayload:
    return {
        "category_id": str(entry.category_id),
        "slug": entry.slug,
        "name": entry.name,
        "description": entry.description or "",
        "sort_order_label": str(entry.sort_order),
        "contract_count_label": _linked_contract_count_label(entry.contract_count),
        "updated_at_label": entry.updated_at_label,
        "can_delete": entry.can_delete,
    }


def _serialize_featured_contract_row(
    entry: AdminFeaturedContractEntry,
) -> AdminFeaturedContractRowPayload:
    is_featured = entry.is_featured
    return {
        "contract_id": str(entry.contract_id),
        "slug": entry.slug,
        "display_name": entry.display_name,
        "contract_name": entry.contract_name,
        "author_name": entry.author_name,
        "categories_label": entry.categories_label,
        "latest_public_version": entry.latest_public_version,
        "status_label": entry.status_label,
        "status_color_scheme": _publication_status_color_scheme(entry.status),
        "is_featured": is_featured,
        "featured_label": "Featured" if is_featured else "Not featured",
        "toggle_label": "Remove spotlight" if is_featured else "Feature contract",
        "toggle_variant": "soft" if is_featured else "solid",
        "updated_at_label": entry.updated_at_label,
        "public_detail_href": entry.public_detail_href or "",
        "has_public_detail": entry.public_detail_href is not None,
        "edit_href": entry.edit_href,
    }


def _serialize_audit_log_row(entry: AdminAuditLogInspectionEntry) -> AdminAuditLogRowPayload:
    return {
        "audit_log_id": str(entry.audit_log_id),
        "created_at_label": entry.created_at_label,
        "admin_label": entry.admin_label,
        "action_label": entry.action_label,
        "entity_type_label": entry.entity_type_label,
        "summary": entry.summary,
        "details_pretty_json": entry.details_pretty_json,
        "has_details": entry.has_details,
    }


def _category_count_label(count: int) -> str:
    if count == 1:
        return "1 category"
    return f"{count} categories"


def _featured_count_label(entries: tuple[AdminFeaturedContractEntry, ...]) -> str:
    featured_count = sum(1 for entry in entries if entry.is_featured)
    if featured_count == 1:
        return "1 featured contract"
    return f"{featured_count} featured contracts"


def _audit_log_count_label(count: int) -> str:
    if count == 1:
        return "1 recent audit entry"
    return f"{count} recent audit entries"


def _linked_contract_count_label(count: int) -> str:
    if count == 1:
        return "1 linked contract"
    return f"{count} linked contracts"


def _publication_status_color_scheme(status_value: str) -> str:
    normalized_status = PublicationStatus(status_value)
    if normalized_status is PublicationStatus.PUBLISHED:
        return "grass"
    if normalized_status in {PublicationStatus.DEPRECATED, PublicationStatus.ARCHIVED}:
        return "orange"
    return "gray"


__all__ = ["AdminCatalogOperationsState"]
