"""Authenticated state for the deployment history page."""

from __future__ import annotations

from typing import TypedDict

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import DeploymentStatus, DeploymentTransport, User
from contracting_hub.services.auth import logout_user, resolve_current_user
from contracting_hub.services.deployment_history import (
    DeploymentHistoryEntrySnapshot,
    DeploymentHistoryServiceError,
    PrivateDeploymentHistorySnapshot,
    SavedTargetShortcutSnapshot,
    load_private_deployment_history_snapshot,
)
from contracting_hub.states.auth import AUTH_SESSION_COOKIE_NAME
from contracting_hub.utils import build_contract_detail_path, format_contract_calendar_date
from contracting_hub.utils.meta import HOME_ROUTE

ALL_DEPLOYMENT_FILTER_VALUE = "all"
_SETTINGS = get_settings()


class SavedTargetShortcutPayload(TypedDict):
    """Serialized saved-target shortcut content stored in state."""

    id: int
    label: str
    playground_id: str
    is_default: bool
    default_badge_label: str
    last_used_label: str
    filter_value: str
    button_label: str


class DeploymentHistoryEntryPayload(TypedDict):
    """Serialized deployment-history content rendered by the page."""

    deployment_id: int
    contract_title: str
    contract_name: str
    contract_href: str
    semantic_version: str
    version_label: str
    status_label: str
    status_color_scheme: str
    transport_label: str
    target_label: str
    target_detail: str
    playground_id: str
    redirect_url: str
    external_request_id: str
    error_message: str
    initiated_label: str
    completed_label: str
    target_filter_value: str


class DeploymentHistoryState(rx.State):
    """Authenticated UI state for deployment-history review and target shortcuts."""

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
    deployment_entries: list[DeploymentHistoryEntryPayload] = []
    visible_deployment_entries: list[DeploymentHistoryEntryPayload] = []
    saved_target_shortcuts: list[SavedTargetShortcutPayload] = []
    saved_target_shortcut_count_label: str = "0 saved targets"
    selected_target_filter: str = ALL_DEPLOYMENT_FILTER_VALUE
    deployment_history_count_label: str = "0 deployments"
    active_filter_description: str = "Viewing all recorded deployments."
    history_empty_title: str = "No deployments recorded yet."
    history_empty_body: str = (
        "Deploy a published contract version from its detail page to build your history."
    )
    page_error_message: str = ""

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
    def has_saved_target_shortcuts(self) -> bool:
        """Return whether the user has any saved playground targets."""
        return bool(self.saved_target_shortcuts)

    @rx.var
    def has_visible_deployments(self) -> bool:
        """Return whether the active filter currently exposes any history rows."""
        return bool(self.visible_deployment_entries)

    def load_page(self) -> rx.event.EventSpec | None:
        """Load the authenticated deployment-history snapshot."""
        self._clear_feedback()
        self._apply_user_snapshot(self._resolve_user_from_cookie())
        self._reset_history_state()

        user_id = self.current_user_id
        if user_id is None:
            return None

        try:
            with session_scope() as session:
                snapshot = load_private_deployment_history_snapshot(
                    session=session,
                    user_id=user_id,
                )
        except DeploymentHistoryServiceError as error:
            self.page_error_message = str(error)
            return None

        self._apply_snapshot(snapshot)
        return None

    def logout_current_user(self) -> rx.event.EventSpec:
        """Invalidate the current cookie-backed session from the history page shell."""
        if self.auth_session_token:
            with session_scope() as session:
                logout_user(
                    session=session,
                    session_token=self.auth_session_token,
                )

        self.auth_session_token = ""
        self._apply_user_snapshot(None)
        self._clear_feedback()
        self._reset_history_state()
        return rx.redirect(HOME_ROUTE, replace=True)

    def set_target_filter(self, value: str) -> None:
        """Apply a saved-target filter shortcut to the visible deployment history."""
        self.selected_target_filter = value.strip() or ALL_DEPLOYMENT_FILTER_VALUE
        self._apply_target_filter()

    def show_all_deployments(self) -> None:
        """Reset the history filter back to the full deployment list."""
        self.selected_target_filter = ALL_DEPLOYMENT_FILTER_VALUE
        self._apply_target_filter()

    def _reset_history_state(self) -> None:
        self.deployment_entries = []
        self.visible_deployment_entries = []
        self.saved_target_shortcuts = []
        self.saved_target_shortcut_count_label = "0 saved targets"
        self.selected_target_filter = ALL_DEPLOYMENT_FILTER_VALUE
        self.deployment_history_count_label = "0 deployments"
        self.active_filter_description = "Viewing all recorded deployments."
        self.history_empty_title = "No deployments recorded yet."
        self.history_empty_body = (
            "Deploy a published contract version from its detail page to build your history."
        )

    def _apply_snapshot(self, snapshot: PrivateDeploymentHistorySnapshot) -> None:
        self.saved_target_shortcuts = [
            _serialize_saved_target_shortcut(target) for target in snapshot.saved_targets
        ]
        self.saved_target_shortcut_count_label = _format_saved_target_count_label(
            len(self.saved_target_shortcuts)
        )
        self.deployment_entries = [
            _serialize_deployment_history_entry(entry) for entry in snapshot.deployments
        ]
        self.selected_target_filter = ALL_DEPLOYMENT_FILTER_VALUE
        self._apply_target_filter()

    def _apply_target_filter(self) -> None:
        valid_filter_values = {shortcut["filter_value"] for shortcut in self.saved_target_shortcuts}
        if (
            self.selected_target_filter != ALL_DEPLOYMENT_FILTER_VALUE
            and self.selected_target_filter not in valid_filter_values
        ):
            self.selected_target_filter = ALL_DEPLOYMENT_FILTER_VALUE

        if self.selected_target_filter == ALL_DEPLOYMENT_FILTER_VALUE:
            visible_entries = list(self.deployment_entries)
        else:
            visible_entries = [
                entry
                for entry in self.deployment_entries
                if entry["target_filter_value"] == self.selected_target_filter
            ]

        self.visible_deployment_entries = visible_entries
        self.deployment_history_count_label = _format_deployment_count_label(
            visible_count=len(visible_entries),
            total_count=len(self.deployment_entries),
        )
        self.active_filter_description = _build_active_filter_description(
            filter_value=self.selected_target_filter,
            shortcuts=self.saved_target_shortcuts,
        )
        self.history_empty_title, self.history_empty_body = _build_empty_history_copy(
            filter_value=self.selected_target_filter,
            shortcuts=self.saved_target_shortcuts,
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
        self.page_error_message = ""


def _serialize_saved_target_shortcut(
    target: SavedTargetShortcutSnapshot,
) -> SavedTargetShortcutPayload:
    return {
        "id": target.id,
        "label": target.label,
        "playground_id": target.playground_id,
        "is_default": target.is_default,
        "default_badge_label": "Default" if target.is_default else "",
        "last_used_label": _format_saved_target_last_used_label(target.last_used_at),
        "filter_value": str(target.id),
        "button_label": f"Show {target.label} deployments",
    }


def _serialize_deployment_history_entry(
    entry: DeploymentHistoryEntrySnapshot,
) -> DeploymentHistoryEntryPayload:
    target_label = entry.playground_target_label or "Ad hoc target"
    target_detail = entry.playground_id
    if entry.playground_target_label is None:
        target_detail = f"{entry.playground_id} / Direct entry"

    return {
        "deployment_id": entry.deployment_id,
        "contract_title": entry.contract_display_name,
        "contract_name": entry.contract_name,
        "contract_href": build_contract_detail_path(
            entry.contract_slug,
            semantic_version=entry.semantic_version,
        ),
        "semantic_version": entry.semantic_version,
        "version_label": f"Version {entry.semantic_version}",
        "status_label": _deployment_status_label(entry.status),
        "status_color_scheme": _deployment_status_color_scheme(entry.status),
        "transport_label": _deployment_transport_label(entry.transport),
        "target_label": target_label,
        "target_detail": target_detail,
        "playground_id": entry.playground_id,
        "redirect_url": entry.redirect_url or "",
        "external_request_id": entry.external_request_id or "",
        "error_message": entry.error_message or "",
        "initiated_label": f"Started {format_contract_calendar_date(entry.initiated_at)}",
        "completed_label": _format_completion_label(entry.completed_at),
        "target_filter_value": (
            "" if entry.playground_target_id is None else str(entry.playground_target_id)
        ),
    }


def _deployment_status_label(status: DeploymentStatus) -> str:
    if status is DeploymentStatus.ACCEPTED:
        return "Accepted"
    if status is DeploymentStatus.REDIRECT_REQUIRED:
        return "Redirect ready"
    if status is DeploymentStatus.FAILED:
        return "Failed"
    return "Pending"


def _deployment_status_color_scheme(status: DeploymentStatus) -> str:
    if status is DeploymentStatus.ACCEPTED:
        return "grass"
    if status is DeploymentStatus.REDIRECT_REQUIRED:
        return "bronze"
    if status is DeploymentStatus.FAILED:
        return "tomato"
    return "gray"


def _deployment_transport_label(transport: DeploymentTransport | None) -> str:
    if transport is DeploymentTransport.DEEP_LINK:
        return "Deep link"
    if transport is DeploymentTransport.HTTP:
        return "HTTP"
    if transport is DeploymentTransport.HYBRID:
        return "Hybrid"
    return ""


def _format_completion_label(value) -> str:
    if value is None:
        return "Awaiting completion details"
    return f"Completed {format_contract_calendar_date(value)}"


def _format_saved_target_last_used_label(value) -> str:
    if value is None:
        return "Never used"
    return f"Last used {format_contract_calendar_date(value)}"


def _format_saved_target_count_label(count: int) -> str:
    return "1 saved target" if count == 1 else f"{count} saved targets"


def _format_deployment_count_label(*, visible_count: int, total_count: int) -> str:
    if total_count <= 0:
        return "0 deployments"
    if visible_count == total_count:
        return "1 deployment" if total_count == 1 else f"{total_count} deployments"
    return (
        f"1 of {total_count} deployments"
        if visible_count == 1
        else f"{visible_count} of {total_count} deployments"
    )


def _build_active_filter_description(
    *,
    filter_value: str,
    shortcuts: list[SavedTargetShortcutPayload],
) -> str:
    if filter_value == ALL_DEPLOYMENT_FILTER_VALUE:
        return "Viewing all recorded deployments."

    shortcut = next(
        (candidate for candidate in shortcuts if candidate["filter_value"] == filter_value),
        None,
    )
    if shortcut is None:
        return "Viewing all recorded deployments."
    return f"Viewing deployments for {shortcut['label']}."


def _build_empty_history_copy(
    *,
    filter_value: str,
    shortcuts: list[SavedTargetShortcutPayload],
) -> tuple[str, str]:
    if filter_value == ALL_DEPLOYMENT_FILTER_VALUE:
        return (
            "No deployments recorded yet.",
            "Deploy a published contract version from its detail page to build your history.",
        )

    shortcut = next(
        (candidate for candidate in shortcuts if candidate["filter_value"] == filter_value),
        None,
    )
    if shortcut is None:
        return (
            "No deployments recorded yet.",
            "Deploy a published contract version from its detail page to build your history.",
        )
    return (
        f"No deployments recorded for {shortcut['label']} yet.",
        "Switch back to all deployments or retry this target from a contract detail page.",
    )


__all__ = [
    "ALL_DEPLOYMENT_FILTER_VALUE",
    "DeploymentHistoryEntryPayload",
    "DeploymentHistoryState",
    "SavedTargetShortcutPayload",
]
