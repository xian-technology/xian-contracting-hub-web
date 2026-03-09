"""Admin contract-editor state."""

from __future__ import annotations

from typing import Any, TypedDict

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import User
from contracting_hub.services.admin_contract_editor import (
    AdminContractEditorAuthorOption,
    AdminContractEditorCategoryOption,
    AdminContractEditorMode,
    AdminContractEditorServiceError,
    AdminContractEditorSnapshot,
    build_empty_admin_contract_editor_snapshot,
    create_admin_contract_metadata,
    load_admin_contract_editor_snapshot_safe,
    update_admin_contract_metadata,
)
from contracting_hub.services.auth import AuthServiceError, logout_user, resolve_current_user
from contracting_hub.states.auth import AUTH_SESSION_COOKIE_NAME
from contracting_hub.utils.meta import (
    HOME_ROUTE,
    build_admin_contract_edit_path,
    build_admin_contract_relations_path,
    build_admin_contract_versions_path,
)

_SETTINGS = get_settings()


class AdminContractEditorAuthorOptionPayload(TypedDict):
    """Serialized author option stored in state."""

    user_id: str
    display_label: str
    secondary_label: str


class AdminContractEditorCategoryOptionPayload(TypedDict):
    """Serialized category option stored in state."""

    id: str
    slug: str
    name: str
    description: str
    is_primary_selected: bool
    is_secondary_selected: bool


class AdminContractEditorState(rx.State):
    """Admin-only state for contract metadata editing."""

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
    editor_mode: str = AdminContractEditorMode.CREATE.value
    editor_contract_id: int | None = None
    editing_contract_slug: str = ""
    contract_status_label: str = "Draft"
    latest_public_version_label: str = "No public version yet"
    public_detail_href: str = ""
    versions_href: str = ""
    relations_href: str = ""
    contract_slug_value: str = ""
    contract_name_value: str = ""
    display_name_value: str = ""
    short_summary_value: str = ""
    long_description_value: str = ""
    author_user_id_value: str = ""
    author_label_value: str = ""
    featured_choice: str = "no"
    license_name_value: str = ""
    documentation_url_value: str = ""
    source_repository_url_value: str = ""
    network_value: str = ""
    primary_category_id_value: str = ""
    tags_value: str = ""
    author_options: list[AdminContractEditorAuthorOptionPayload] = []
    category_options: list[AdminContractEditorCategoryOptionPayload] = []
    save_success_message: str = ""
    form_error_message: str = ""
    load_error_message: str = ""
    slug_error: str = ""
    contract_name_error: str = ""
    display_name_error: str = ""
    short_summary_error: str = ""
    long_description_error: str = ""
    author_assignment_error: str = ""
    primary_category_error: str = ""
    secondary_categories_error: str = ""
    license_name_error: str = ""
    documentation_url_error: str = ""
    source_repository_url_error: str = ""
    network_error: str = ""

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
    def is_edit_mode(self) -> bool:
        """Return whether the current route is editing an existing contract."""
        return self.editor_mode == AdminContractEditorMode.EDIT.value

    @rx.var
    def editor_heading(self) -> str:
        """Return the page heading shown above the editor form."""
        if self.is_edit_mode and self.display_name_value:
            return f"Edit {self.display_name_value}"
        if self.is_edit_mode:
            return "Edit contract"
        return "Create contract"

    @rx.var
    def editor_intro(self) -> str:
        """Return the primary page intro copy for the editor."""
        if self.is_edit_mode:
            return (
                "Update catalog metadata, taxonomy, tags, featured state, and author assignment "
                "without touching immutable version history."
            )
        return (
            "Create a draft contract shell, organize it in the taxonomy, and assign the intended "
            "author before adding versions."
        )

    @rx.var
    def editor_submit_label(self) -> str:
        """Return the submit-button copy for the editor form."""
        return "Save metadata changes" if self.is_edit_mode else "Create draft contract"

    @rx.var
    def has_public_detail(self) -> bool:
        """Return whether the contract has a public detail route."""
        return bool(self.public_detail_href)

    @rx.var
    def has_version_manager(self) -> bool:
        """Return whether the current editor should link to version management."""
        return bool(self.versions_href)

    @rx.var
    def has_relation_manager(self) -> bool:
        """Return whether the current editor should link to relation management."""
        return bool(self.relations_href)

    @rx.var
    def has_categories(self) -> bool:
        """Return whether taxonomy options are available."""
        return bool(self.category_options)

    @rx.var
    def secondary_category_count_label(self) -> str:
        """Return a compact summary of selected secondary categories."""
        count = sum(1 for option in self.category_options if option["is_secondary_selected"])
        if count == 1:
            return "1 secondary category"
        return f"{count} secondary categories"

    @rx.var
    def show_missing_contract_state(self) -> bool:
        """Return whether the edit route could not resolve the requested contract."""
        return (
            self.is_edit_mode and self.editor_contract_id is None and bool(self.load_error_message)
        )

    def sync_auth_state(self) -> None:
        """Refresh the current-user shell snapshot from the auth cookie."""
        self._apply_user_snapshot(self._resolve_user_from_cookie())

    def load_page(self) -> None:
        """Load the admin contract editor from the current route params."""
        requested_slug = str(self.router.page.params.get("slug", "")).strip().lower() or None
        self._clear_feedback()
        self.sync_auth_state()
        try:
            snapshot = load_admin_contract_editor_snapshot_safe(contract_slug=requested_slug)
        except AdminContractEditorServiceError as error:
            self.load_error_message = str(error)
            self._apply_snapshot(
                build_empty_admin_contract_editor_snapshot(contract_slug=requested_slug)
            )
            return

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
        return rx.redirect(HOME_ROUTE, replace=True)

    def set_contract_slug_value(self, value: str) -> None:
        """Update the editable contract slug field."""
        self.contract_slug_value = value

    def set_contract_name_value(self, value: str) -> None:
        """Update the editable Xian contract-name field."""
        self.contract_name_value = value

    def set_display_name_value(self, value: str) -> None:
        """Update the editable display-name field."""
        self.display_name_value = value

    def set_short_summary_value(self, value: str) -> None:
        """Update the editable short-summary field."""
        self.short_summary_value = value

    def set_long_description_value(self, value: str) -> None:
        """Update the editable long-description field."""
        self.long_description_value = value

    def set_author_label_value(self, value: str) -> None:
        """Update the fallback author-label field."""
        self.author_label_value = value
        self.author_assignment_error = ""

    def select_author_user(self, value: str) -> None:
        """Update the current author selection."""
        self.author_user_id_value = value
        self.author_assignment_error = ""

    def select_primary_category(self, value: str) -> None:
        """Update the primary category and keep it out of the secondary set."""
        self.primary_category_id_value = value
        updated_options: list[AdminContractEditorCategoryOptionPayload] = []
        for option in self.category_options:
            updated_option = dict(option)
            updated_option["is_primary_selected"] = option["id"] == value
            if option["id"] == value:
                updated_option["is_secondary_selected"] = False
            updated_options.append(updated_option)
        self.category_options = updated_options
        self.primary_category_error = ""
        self.secondary_categories_error = ""

    def set_featured_choice(self, value: str) -> None:
        """Update the featured-state selector."""
        self.featured_choice = value

    def set_license_name_value(self, value: str) -> None:
        """Update the license-name field."""
        self.license_name_value = value

    def set_documentation_url_value(self, value: str) -> None:
        """Update the documentation URL field."""
        self.documentation_url_value = value
        self.documentation_url_error = ""

    def set_source_repository_url_value(self, value: str) -> None:
        """Update the source repository URL field."""
        self.source_repository_url_value = value
        self.source_repository_url_error = ""

    def set_network_value(self, value: str) -> None:
        """Update the optional network label."""
        self.network_value = value
        self.network_error = ""

    def set_tags_value(self, value: str) -> None:
        """Update the comma-separated tags field."""
        self.tags_value = value

    def toggle_secondary_category(self, category_id: str) -> None:
        """Toggle one secondary category badge in the taxonomy grid."""
        if not category_id or category_id == self.primary_category_id_value:
            return

        updated_options: list[AdminContractEditorCategoryOptionPayload] = []
        for option in self.category_options:
            updated_option = dict(option)
            if option["id"] == category_id:
                updated_option["is_secondary_selected"] = not option["is_secondary_selected"]
            updated_options.append(updated_option)
        self.category_options = updated_options
        self.secondary_categories_error = ""

    def submit_form(self, form_data: dict[str, Any]) -> rx.event.EventSpec | None:
        """Persist the editor-managed contract metadata."""
        del form_data
        self._clear_feedback()
        try:
            with session_scope() as session:
                if self.is_edit_mode and self.editing_contract_slug:
                    contract = update_admin_contract_metadata(
                        session=session,
                        session_token=self.auth_session_token,
                        contract_slug=self.editing_contract_slug,
                        **self._submission_payload(),
                    )
                else:
                    contract = create_admin_contract_metadata(
                        session=session,
                        session_token=self.auth_session_token,
                        **self._submission_payload(),
                    )
        except (AdminContractEditorServiceError, AuthServiceError) as error:
            self._apply_submit_error(error)
            return None

        if not self.is_edit_mode:
            return rx.redirect(build_admin_contract_edit_path(contract.slug), replace=True)

        if contract.slug != self.editing_contract_slug:
            return rx.redirect(build_admin_contract_edit_path(contract.slug), replace=True)

        self._reload_snapshot(contract.slug)
        self.save_success_message = "Contract metadata updated."
        return None

    def _submission_payload(self) -> dict[str, object]:
        return {
            "slug": self.contract_slug_value,
            "contract_name": self.contract_name_value,
            "display_name": self.display_name_value,
            "short_summary": self.short_summary_value,
            "long_description": self.long_description_value,
            "author_user_id": self.author_user_id_value or None,
            "author_label": self.author_label_value,
            "featured": self.featured_choice,
            "license_name": self.license_name_value,
            "documentation_url": self.documentation_url_value,
            "source_repository_url": self.source_repository_url_value,
            "network": self.network_value,
            "primary_category_id": self.primary_category_id_value or None,
            "secondary_category_ids": self._selected_secondary_category_ids(),
            "tags_text": self.tags_value,
        }

    def _selected_secondary_category_ids(self) -> list[str]:
        return [option["id"] for option in self.category_options if option["is_secondary_selected"]]

    def _reload_snapshot(self, contract_slug: str | None = None) -> None:
        snapshot = load_admin_contract_editor_snapshot_safe(
            contract_slug=contract_slug or self.editing_contract_slug or None
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

    def _apply_snapshot(self, snapshot: AdminContractEditorSnapshot) -> None:
        self.editor_mode = snapshot.mode.value
        self.editor_contract_id = snapshot.contract_id
        self.editing_contract_slug = snapshot.slug
        self.contract_status_label = snapshot.status.value.title()
        self.latest_public_version_label = snapshot.latest_public_version or "No public version yet"
        self.public_detail_href = snapshot.public_detail_href or ""
        self.versions_href = (
            build_admin_contract_versions_path(snapshot.slug) if snapshot.contract_id else ""
        )
        self.relations_href = (
            build_admin_contract_relations_path(snapshot.slug) if snapshot.contract_id else ""
        )
        self.contract_slug_value = snapshot.slug
        self.contract_name_value = snapshot.contract_name
        self.display_name_value = snapshot.display_name
        self.short_summary_value = snapshot.short_summary
        self.long_description_value = snapshot.long_description
        self.author_user_id_value = str(snapshot.author_user_id or "")
        self.author_label_value = snapshot.author_label
        self.featured_choice = "yes" if snapshot.featured else "no"
        self.license_name_value = snapshot.license_name
        self.documentation_url_value = snapshot.documentation_url
        self.source_repository_url_value = snapshot.source_repository_url
        self.network_value = snapshot.network.value if snapshot.network is not None else ""
        self.primary_category_id_value = str(snapshot.primary_category_id or "")
        self.tags_value = snapshot.tags_text
        self.author_options = [
            _serialize_author_option(option) for option in snapshot.author_options
        ]
        self.category_options = [
            _serialize_category_option(
                option,
                primary_category_id=snapshot.primary_category_id,
                secondary_category_ids=snapshot.secondary_category_ids,
            )
            for option in snapshot.category_options
        ]

    def _apply_submit_error(self, error: Exception) -> None:
        if isinstance(error, AuthServiceError):
            self.form_error_message = str(error)
            return
        if not isinstance(error, AdminContractEditorServiceError):
            self.form_error_message = str(error)
            return

        field = error.field
        if field == "slug":
            self.slug_error = str(error)
            return
        if field == "contract_name":
            self.contract_name_error = str(error)
            return
        if field == "display_name":
            self.display_name_error = str(error)
            return
        if field == "short_summary":
            self.short_summary_error = str(error)
            return
        if field == "long_description":
            self.long_description_error = str(error)
            return
        if field in {"author_user_id", "author_label", "author_assignment"}:
            self.author_assignment_error = str(error)
            return
        if field == "primary_category_id":
            self.primary_category_error = str(error)
            return
        if field == "secondary_category_ids":
            self.secondary_categories_error = str(error)
            return
        if field == "license_name":
            self.license_name_error = str(error)
            return
        if field == "documentation_url":
            self.documentation_url_error = str(error)
            return
        if field == "source_repository_url":
            self.source_repository_url_error = str(error)
            return
        if field == "network":
            self.network_error = str(error)
            return
        self.form_error_message = str(error)

    def _clear_feedback(self) -> None:
        self.save_success_message = ""
        self.form_error_message = ""
        self.load_error_message = ""
        self.slug_error = ""
        self.contract_name_error = ""
        self.display_name_error = ""
        self.short_summary_error = ""
        self.long_description_error = ""
        self.author_assignment_error = ""
        self.primary_category_error = ""
        self.secondary_categories_error = ""
        self.license_name_error = ""
        self.documentation_url_error = ""
        self.source_repository_url_error = ""
        self.network_error = ""


def _serialize_author_option(
    option: AdminContractEditorAuthorOption,
) -> AdminContractEditorAuthorOptionPayload:
    return {
        "user_id": str(option.user_id),
        "display_label": option.display_label,
        "secondary_label": option.secondary_label,
    }


def _serialize_category_option(
    option: AdminContractEditorCategoryOption,
    *,
    primary_category_id: int | None,
    secondary_category_ids: tuple[int, ...],
) -> AdminContractEditorCategoryOptionPayload:
    return {
        "id": str(option.category_id),
        "slug": option.slug,
        "name": option.name,
        "description": option.description or "",
        "is_primary_selected": option.category_id == primary_category_id,
        "is_secondary_selected": option.category_id in set(secondary_category_ids),
    }


__all__ = ["AdminContractEditorState"]
