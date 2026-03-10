"""Admin contract-index state."""

from __future__ import annotations

from typing import Any, TypedDict

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import User
from contracting_hub.services.admin_contracts import (
    AdminContractActionError,
    AdminContractFeaturedFilter,
    AdminContractIndexEntry,
    AdminContractIndexSnapshot,
    AdminContractStatusFilter,
    AdminContractStatusTab,
    archive_admin_contract,
    build_admin_contracts_path,
    build_empty_admin_contract_index_snapshot,
    delete_admin_contract,
    load_admin_contract_index_snapshot_safe,
    publish_admin_contract,
)
from contracting_hub.services.auth import AuthServiceError, logout_user, resolve_current_user
from contracting_hub.states.auth import AUTH_SESSION_COOKIE_NAME
from contracting_hub.utils.meta import HOME_ROUTE

_SETTINGS = get_settings()


class AdminContractRowPayload(TypedDict):
    """Serialized admin contract-row content stored in state."""

    slug: str
    display_name: str
    contract_name: str
    short_summary: str
    status_label: str
    status_background: str
    status_border: str
    status_text: str
    featured_label: str
    featured_visible: bool
    author_name: str
    categories_label: str
    latest_version_label: str
    updated_at_label: str
    public_detail_href: str
    has_public_detail: bool
    edit_href: str
    versions_href: str
    can_publish: bool
    can_archive: bool
    can_delete: bool
    action_hint: str


class AdminContractStatusTabPayload(TypedDict):
    """Serialized status-tab content stored in state."""

    value: str
    label: str
    count: str
    href: str
    background: str
    border_color: str
    text_color: str


class AdminContractsState(rx.State):
    """Admin-only state for contract index filtering and quick actions."""

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
    query: str = ""
    selected_status_filter: str = AdminContractStatusFilter.ALL.value
    selected_featured_filter: str = AdminContractFeaturedFilter.ALL.value
    result_count_label: str = "0 contracts"
    empty_state_body: str = "No contracts match the current admin filters."
    action_success_message: str = ""
    action_error_message: str = ""
    status_tabs: list[AdminContractStatusTabPayload] = []
    contract_rows: list[AdminContractRowPayload] = []
    clear_filters_href: str = build_admin_contracts_path()

    @rx.var
    def is_authenticated(self) -> bool:
        """Return whether the current browser has an active user session."""
        return self.current_user_id is not None

    @rx.var
    def is_loading(self) -> bool:
        """Return whether the admin contract index is loading."""
        return self.load_state == "loading"

    @rx.var
    def has_load_error(self) -> bool:
        """Return whether the admin contract index failed to load."""
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
    def has_results(self) -> bool:
        """Return whether the admin index currently has rows to render."""
        return bool(self.contract_rows)

    def sync_auth_state(self) -> None:
        """Refresh the current-user shell snapshot from the auth cookie."""
        self._apply_user_snapshot(self._resolve_user_from_cookie())

    def load_page(self) -> None:
        """Load the admin contract index from the current router query params."""
        self.load_state = "loading"
        self._clear_feedback()
        self.sync_auth_state()
        params = self.router.page.params
        if self.current_user_id is None:
            self.load_error_message = "Administrator access is required to view this workspace."
            self.load_state = "error"
            return

        try:
            snapshot = load_admin_contract_index_snapshot_safe(
                query=params.get("query"),
                status_filter=params.get("status"),
                featured_filter=params.get("featured"),
            )
        except Exception as error:
            snapshot = build_empty_admin_contract_index_snapshot(
                query=params.get("query"),
                status_filter=params.get("status"),
                featured_filter=params.get("featured"),
            )
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
        return rx.redirect(HOME_ROUTE, replace=True)

    def set_query(self, value: str) -> None:
        """Update the current admin search input."""
        self.query = value

    def set_selected_featured_filter(self, value: str) -> None:
        """Update the featured-state filter control."""
        self.selected_featured_filter = value

    def apply_filters(self, form_data: dict[str, Any]) -> rx.event.EventSpec:
        """Redirect to the canonical admin index URL for the submitted filters."""
        return rx.redirect(
            build_admin_contracts_path(
                query=form_data.get("query"),
                status_filter=self.selected_status_filter,
                featured_filter=form_data.get("featured"),
            )
        )

    def publish_contract(self, slug: str) -> None:
        """Publish one contract directly from the admin index."""
        self._perform_action(
            slug=slug,
            action=publish_admin_contract,
            success_message="Contract published and restored to the public catalog.",
        )

    def archive_contract(self, slug: str) -> None:
        """Archive one contract directly from the admin index."""
        self._perform_action(
            slug=slug,
            action=archive_admin_contract,
            success_message="Contract archived while preserving its version history.",
        )

    def delete_contract(self, slug: str) -> None:
        """Delete one draft-only or archive-only contract directly from the index."""
        self._perform_action(
            slug=slug,
            action=delete_admin_contract,
            success_message="Contract deleted.",
        )

    def _perform_action(
        self,
        *,
        slug: str,
        action,
        success_message: str,
    ) -> None:
        self._clear_feedback()
        try:
            with session_scope() as session:
                action(
                    session=session,
                    session_token=self.auth_session_token,
                    contract_slug=slug,
                )
        except (AdminContractActionError, AuthServiceError) as error:
            self.action_error_message = str(error)
            return

        self.action_success_message = success_message
        self._reload_snapshot()

    def _reload_snapshot(self) -> None:
        snapshot = load_admin_contract_index_snapshot_safe(
            query=self.query,
            status_filter=self.selected_status_filter,
            featured_filter=self.selected_featured_filter,
        )
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: AdminContractIndexSnapshot) -> None:
        self.query = snapshot.query
        self.selected_status_filter = snapshot.status_filter.value
        self.selected_featured_filter = snapshot.featured_filter.value
        self.result_count_label = _result_count_label(snapshot.total_results)
        self.empty_state_body = _empty_state_body(snapshot)
        self.status_tabs = [_serialize_status_tab(tab) for tab in snapshot.status_tabs]
        self.contract_rows = [_serialize_contract_row(entry) for entry in snapshot.results]
        self.clear_filters_href = build_admin_contracts_path(
            status_filter=snapshot.status_filter,
        )

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

    def _clear_feedback(self) -> None:
        self.action_success_message = ""
        self.action_error_message = ""
        self.load_error_message = ""


def _serialize_status_tab(tab: AdminContractStatusTab) -> AdminContractStatusTabPayload:
    return {
        "value": tab.value.value,
        "label": tab.label,
        "count": str(tab.count),
        "href": tab.href,
        "background": (
            "rgba(226, 205, 165, 0.22)" if tab.is_active else "rgba(255, 252, 246, 0.9)"
        ),
        "border_color": (
            "rgba(141, 95, 37, 0.45)" if tab.is_active else "rgba(148, 128, 97, 0.18)"
        ),
        "text_color": "var(--hub-color-text)" if tab.is_active else "var(--hub-color-text-muted)",
    }


def _serialize_contract_row(entry: AdminContractIndexEntry) -> AdminContractRowPayload:
    status_background, status_border, status_text = _status_badge_style(entry.status.value)
    return {
        "slug": entry.slug,
        "display_name": entry.display_name,
        "contract_name": entry.contract_name,
        "short_summary": entry.short_summary,
        "status_label": entry.status.value.title(),
        "status_background": status_background,
        "status_border": status_border,
        "status_text": status_text,
        "featured_label": "Featured",
        "featured_visible": entry.featured,
        "author_name": entry.author_name,
        "categories_label": ", ".join(entry.category_names) or "Uncategorized",
        "latest_version_label": entry.latest_public_version or "No public version yet",
        "updated_at_label": entry.updated_at_label,
        "public_detail_href": entry.public_detail_href or "",
        "has_public_detail": entry.public_detail_href is not None,
        "edit_href": entry.edit_href,
        "versions_href": entry.versions_href,
        "can_publish": entry.can_publish,
        "can_archive": entry.can_archive,
        "can_delete": entry.can_delete,
        "action_hint": entry.action_hint,
    }


def _status_badge_style(status_value: str) -> tuple[str, str, str]:
    if status_value == AdminContractStatusFilter.PUBLISHED.value:
        return (
            "rgba(220, 248, 231, 0.95)",
            "1px solid rgba(46, 125, 50, 0.22)",
            "#1b5e20",
        )
    if status_value == AdminContractStatusFilter.DRAFT.value:
        return (
            "rgba(255, 247, 224, 0.95)",
            "1px solid rgba(166, 115, 0, 0.22)",
            "#7a4f01",
        )
    if status_value == AdminContractStatusFilter.ARCHIVED.value:
        return (
            "rgba(237, 240, 244, 0.95)",
            "1px solid rgba(92, 102, 114, 0.22)",
            "#41505f",
        )
    return (
        "rgba(240, 235, 255, 0.95)",
        "1px solid rgba(91, 76, 149, 0.18)",
        "#4b3f8c",
    )


def _result_count_label(total_results: int) -> str:
    return "1 contract" if total_results == 1 else f"{total_results} contracts"


def _empty_state_body(snapshot: AdminContractIndexSnapshot) -> str:
    if snapshot.query or snapshot.featured_filter is not AdminContractFeaturedFilter.ALL:
        return "Broaden the search or featured filter to bring more contracts back into view."
    if snapshot.status_filter is not AdminContractStatusFilter.ALL:
        return "No contracts currently match this lifecycle tab."
    return "Seed or create contracts to start populating the admin catalog."


__all__ = ["AdminContractsState"]
