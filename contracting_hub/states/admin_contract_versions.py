"""Admin contract-version manager state."""

from __future__ import annotations

from typing import TypedDict

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import LintStatus, PublicationStatus, User
from contracting_hub.services.admin_contract_versions import (
    AdminContractVersionHistoryEntry,
    AdminContractVersionManagerServiceError,
    AdminContractVersionManagerSnapshot,
    AdminContractVersionPreview,
    build_empty_admin_contract_version_manager_snapshot,
    create_admin_contract_version,
    format_admin_version_timestamp,
    load_admin_contract_version_manager_snapshot_safe,
    preview_admin_contract_version,
)
from contracting_hub.services.auth import AuthServiceError, logout_user, resolve_current_user
from contracting_hub.services.contract_versions import ContractVersionServiceError
from contracting_hub.states.auth import AUTH_SESSION_COOKIE_NAME
from contracting_hub.utils.meta import (
    HOME_ROUTE,
    build_admin_contract_relations_path,
)

_SETTINGS = get_settings()


class AdminContractVersionRowPayload(TypedDict):
    """Serialized version-history content stored in state."""

    semantic_version: str
    status_label: str
    status_color_scheme: str
    lint_status_label: str
    lint_status_color_scheme: str
    previous_version_label: str
    created_at_label: str
    published_at_label: str
    is_latest_published: bool
    public_detail_href: str
    has_public_detail: bool


class AdminContractVersionLintFindingPayload(TypedDict):
    """Serialized lint finding displayed in preview mode."""

    severity_label: str
    severity_color_scheme: str
    location_label: str
    message: str


class AdminContractVersionManagerState(rx.State):
    """Admin-only state for contract version creation and preview."""

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
    contract_slug: str = ""
    contract_display_name: str = ""
    contract_name: str = ""
    contract_status_label: str = "Draft"
    contract_status_color_scheme: str = "gray"
    latest_public_version_label: str = "No public version yet"
    latest_saved_version_label: str = "No versions yet"
    public_detail_href: str = ""
    metadata_edit_href: str = ""
    relations_href: str = ""
    version_rows: list[AdminContractVersionRowPayload] = []
    semantic_version_value: str = ""
    source_code_value: str = ""
    changelog_value: str = ""
    save_success_message: str = ""
    form_error_message: str = ""
    load_error_message: str = ""
    semantic_version_error: str = ""
    source_code_error: str = ""
    changelog_error: str = ""
    preview_ready: bool = False
    preview_target_version_label: str = ""
    preview_can_publish: bool = False
    preview_lint_has_report: bool = False
    preview_lint_unavailable_message: str = ""
    preview_lint_status_label: str = "Unavailable"
    preview_lint_status_color_scheme: str = "gray"
    preview_lint_issue_count: int = 0
    preview_lint_error_count: int = 0
    preview_lint_warning_count: int = 0
    preview_lint_info_count: int = 0
    preview_lint_findings: list[AdminContractVersionLintFindingPayload] = []
    preview_diff_previous_version: str = ""
    preview_diff_unified_text: str = ""
    preview_diff_has_previous_version: bool = False
    preview_diff_has_changes: bool = False
    preview_diff_added_lines: int = 0
    preview_diff_removed_lines: int = 0
    preview_diff_line_delta: int = 0
    preview_diff_hunk_count: int = 0
    preview_diff_context_lines: int = 3

    @rx.var
    def is_authenticated(self) -> bool:
        """Return whether the current browser has an active user session."""
        return self.current_user_id is not None

    @rx.var
    def is_loading(self) -> bool:
        """Return whether the version-manager snapshot is loading."""
        return self.load_state == "loading"

    @rx.var
    def has_load_error(self) -> bool:
        """Return whether the version-manager route failed to load."""
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
    def page_heading(self) -> str:
        """Return the primary page heading for the version manager."""
        if self.contract_display_name:
            return f"Manage versions for {self.contract_display_name}"
        return "Manage contract versions"

    @rx.var
    def page_intro(self) -> str:
        """Return the primary page intro copy."""
        return (
            "Add immutable source snapshots, inspect lint and diff previews, and choose when a "
            "new release should enter the public catalog."
        )

    @rx.var
    def has_public_detail(self) -> bool:
        """Return whether the contract currently has a public detail page."""
        return bool(self.public_detail_href)

    @rx.var
    def has_relation_manager(self) -> bool:
        """Return whether the current contract has relation-management routing."""
        return bool(self.relations_href)

    @rx.var
    def has_version_history(self) -> bool:
        """Return whether the contract already has persisted versions."""
        return bool(self.version_rows)

    @rx.var
    def version_count_label(self) -> str:
        """Return a compact summary of persisted versions."""
        count = len(self.version_rows)
        if count == 1:
            return "1 saved version"
        return f"{count} saved versions"

    @rx.var
    def show_missing_contract_state(self) -> bool:
        """Return whether the route slug could not be resolved."""
        return (
            bool(self.contract_slug)
            and not self.contract_display_name
            and bool(self.load_error_message)
        )

    @rx.var
    def has_preview_lint_findings(self) -> bool:
        """Return whether the active preview contains lint findings."""
        return bool(self.preview_lint_findings)

    @rx.var
    def has_preview_diff_content(self) -> bool:
        """Return whether the active preview exposes a diff body."""
        return (
            self.preview_ready
            and self.preview_diff_has_previous_version
            and self.preview_diff_has_changes
            and bool(self.preview_diff_unified_text.strip())
        )

    @rx.var
    def preview_lint_issue_count_label(self) -> str:
        """Return the formatted lint-issue count label."""
        if self.preview_lint_issue_count == 1:
            return "1 issue"
        return f"{self.preview_lint_issue_count} issues"

    @rx.var
    def preview_lint_error_count_label(self) -> str:
        """Return the formatted lint-error count label."""
        if self.preview_lint_error_count == 1:
            return "1 error"
        return f"{self.preview_lint_error_count} errors"

    @rx.var
    def preview_lint_warning_count_label(self) -> str:
        """Return the formatted lint-warning count label."""
        if self.preview_lint_warning_count == 1:
            return "1 warning"
        return f"{self.preview_lint_warning_count} warnings"

    @rx.var
    def preview_lint_info_count_label(self) -> str:
        """Return the formatted lint-info count label."""
        if self.preview_lint_info_count == 1:
            return "1 info note"
        return f"{self.preview_lint_info_count} info notes"

    @rx.var
    def preview_lint_summary_copy(self) -> str:
        """Return helper copy for the current lint preview."""
        if self.preview_lint_unavailable_message:
            return self.preview_lint_unavailable_message
        if not self.preview_lint_has_report:
            return "Run a preview to inspect lint results before saving the version."
        if self.preview_lint_status_label == "Fail":
            return (
                "Blocking lint issues were detected. Save a draft to iterate, "
                "or fix them before publishing."
            )
        if self.preview_lint_status_label == "Warn":
            return "Non-blocking lint warnings were detected for the current source draft."
        return "No lint issues were reported for the current source draft."

    @rx.var
    def preview_publish_hint(self) -> str:
        """Return helper copy for the publish action."""
        if not self.preview_ready:
            return (
                "Run a preview before publishing so lint and diff feedback match "
                "the current source."
            )
        if self.preview_can_publish:
            return "This preview can be published immediately."
        return "Publishing is blocked until the preview no longer contains lint errors."

    @rx.var
    def preview_diff_added_lines_label(self) -> str:
        """Return the formatted added-line count label."""
        if self.preview_diff_added_lines == 1:
            return "+1 line added"
        return f"+{self.preview_diff_added_lines} lines added"

    @rx.var
    def preview_diff_removed_lines_label(self) -> str:
        """Return the formatted removed-line count label."""
        if self.preview_diff_removed_lines == 1:
            return "-1 line removed"
        return f"-{self.preview_diff_removed_lines} lines removed"

    @rx.var
    def preview_diff_line_delta_label(self) -> str:
        """Return the formatted net line delta label."""
        delta = self.preview_diff_line_delta
        if delta > 0:
            return f"+{delta} net lines"
        if delta < 0:
            return f"{delta} net lines"
        return "0 net lines"

    @rx.var
    def preview_diff_hunk_count_label(self) -> str:
        """Return the formatted hunk count label."""
        if self.preview_diff_hunk_count == 1:
            return "1 diff hunk"
        return f"{self.preview_diff_hunk_count} diff hunks"

    @rx.var
    def preview_diff_context_lines_label(self) -> str:
        """Return the formatted diff-context label."""
        if self.preview_diff_context_lines == 1:
            return "1 context line"
        return f"{self.preview_diff_context_lines} context lines"

    @rx.var
    def source_line_count_label(self) -> str:
        """Return the current source-editor line count."""
        line_count = len(self.source_code_value.splitlines()) if self.source_code_value else 0
        if line_count == 1:
            return "1 line"
        return f"{line_count} lines"

    def sync_auth_state(self) -> None:
        """Refresh the current-user shell snapshot from the auth cookie."""
        self._apply_user_snapshot(self._resolve_user_from_cookie())

    def load_page(self) -> None:
        """Load the admin version manager from the current route params."""
        requested_slug = str(self.router.page.params.get("slug", "")).strip().lower()
        self.load_state = "loading"
        self._clear_feedback()
        self._clear_preview()
        self.sync_auth_state()
        if self.current_user_id is None:
            self.load_error_message = "Administrator access is required to manage versions."
            self.load_state = "error"
            return

        try:
            snapshot = load_admin_contract_version_manager_snapshot_safe(
                contract_slug=requested_slug or None
            )
        except AdminContractVersionManagerServiceError as error:
            self.load_error_message = str(error)
            snapshot = build_empty_admin_contract_version_manager_snapshot(
                contract_slug=requested_slug or None
            )
            self._apply_snapshot(snapshot)
            self.load_state = "ready"
            return
        except Exception as error:
            self.load_error_message = str(error)
            snapshot = build_empty_admin_contract_version_manager_snapshot(
                contract_slug=requested_slug or None
            )
            self._apply_snapshot(snapshot)
            self.load_state = "error"
            return
        else:
            if requested_slug and snapshot.contract_id is None:
                self.load_error_message = "The requested contract could not be found."

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
        self._clear_preview()
        return rx.redirect(HOME_ROUTE, replace=True)

    def set_semantic_version_value(self, value: str) -> None:
        """Update the semantic-version field."""
        self.semantic_version_value = value
        self.semantic_version_error = ""
        self._clear_preview()

    def set_source_code_value(self, value: str) -> None:
        """Update the source editor."""
        self.source_code_value = value
        self.source_code_error = ""
        self._clear_preview()

    def set_changelog_value(self, value: str) -> None:
        """Update the optional changelog field."""
        self.changelog_value = value
        self.changelog_error = ""
        self._clear_preview()

    def run_preview(self) -> None:
        """Generate lint and diff previews for the current input draft."""
        self._clear_feedback()
        self._clear_preview()
        try:
            with session_scope() as session:
                preview = preview_admin_contract_version(
                    session=session,
                    session_token=self.auth_session_token,
                    contract_slug=self.contract_slug,
                    semantic_version=self.semantic_version_value,
                    source_code=self.source_code_value,
                    changelog=self.changelog_value,
                )
        except (
            AdminContractVersionManagerServiceError,
            AuthServiceError,
            ContractVersionServiceError,
        ) as error:
            self._apply_service_error(error)
            return

        self._apply_preview(preview)

    def save_draft_version(self) -> None:
        """Persist the current editor values as a draft version."""
        self._submit_version(publish_now=False)

    def publish_version(self) -> None:
        """Persist the current editor values as a published version."""
        self._submit_version(publish_now=True)

    def _submit_version(self, *, publish_now: bool) -> None:
        self._clear_feedback()
        try:
            with session_scope() as session:
                version = create_admin_contract_version(
                    session=session,
                    session_token=self.auth_session_token,
                    contract_slug=self.contract_slug,
                    semantic_version=self.semantic_version_value,
                    source_code=self.source_code_value,
                    changelog=self.changelog_value,
                    publish_now=publish_now,
                )
        except (
            AdminContractVersionManagerServiceError,
            AuthServiceError,
            ContractVersionServiceError,
        ) as error:
            self._apply_service_error(error)
            return

        self._reload_snapshot()
        self._reset_form()
        self.save_success_message = (
            f"Published version {version.semantic_version}."
            if publish_now
            else f"Saved draft version {version.semantic_version}."
        )

    def _reload_snapshot(self) -> None:
        snapshot = load_admin_contract_version_manager_snapshot_safe(
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

    def _apply_snapshot(self, snapshot: AdminContractVersionManagerSnapshot) -> None:
        self.contract_slug = snapshot.slug
        self.contract_display_name = snapshot.display_name
        self.contract_name = snapshot.contract_name
        self.contract_status_label = _publication_status_label(snapshot.contract_status)
        self.contract_status_color_scheme = _publication_status_color_scheme(
            snapshot.contract_status
        )
        self.latest_public_version_label = snapshot.latest_public_version or "No public version yet"
        self.latest_saved_version_label = snapshot.latest_saved_version or "No versions yet"
        self.public_detail_href = snapshot.public_detail_href or ""
        self.metadata_edit_href = snapshot.edit_href
        self.relations_href = (
            build_admin_contract_relations_path(snapshot.slug) if snapshot.contract_id else ""
        )
        self.version_rows = [_serialize_version_row(row) for row in snapshot.version_history]

    def _apply_preview(self, preview: AdminContractVersionPreview) -> None:
        self.preview_ready = True
        self.preview_target_version_label = preview.semantic_version
        self.preview_can_publish = preview.can_publish
        self.preview_lint_has_report = preview.has_lint_report
        self.preview_lint_unavailable_message = preview.lint_unavailable_message or ""
        self.preview_lint_status_label = _lint_status_label(preview.lint_status)
        self.preview_lint_status_color_scheme = _lint_status_color_scheme(preview.lint_status)
        self.preview_lint_issue_count = int((preview.lint_summary or {}).get("issue_count", 0))
        self.preview_lint_error_count = int((preview.lint_summary or {}).get("error_count", 0))
        self.preview_lint_warning_count = int((preview.lint_summary or {}).get("warning_count", 0))
        self.preview_lint_info_count = int((preview.lint_summary or {}).get("info_count", 0))
        self.preview_lint_findings = [
            _serialize_lint_finding(finding) for finding in preview.lint_findings
        ]
        self.preview_diff_previous_version = preview.previous_version or ""
        self.preview_diff_unified_text = preview.unified_diff or ""
        self.preview_diff_has_previous_version = bool(
            preview.diff_summary.get("has_previous_version", False)
        )
        self.preview_diff_has_changes = bool(preview.diff_summary.get("has_changes", False))
        self.preview_diff_added_lines = int(preview.diff_summary.get("added_lines", 0))
        self.preview_diff_removed_lines = int(preview.diff_summary.get("removed_lines", 0))
        self.preview_diff_line_delta = int(preview.diff_summary.get("line_delta", 0))
        self.preview_diff_hunk_count = int(preview.diff_summary.get("hunk_count", 0))
        self.preview_diff_context_lines = int(preview.diff_summary.get("context_lines", 3))

    def _apply_service_error(self, error: Exception) -> None:
        if isinstance(error, AuthServiceError):
            self.form_error_message = str(error)
            return
        if isinstance(
            error,
            (AdminContractVersionManagerServiceError, ContractVersionServiceError),
        ):
            field = getattr(error, "field", "")
            if field == "semantic_version":
                self.semantic_version_error = str(error)
                return
            if field == "source_code":
                self.source_code_error = str(error)
                return
            if field == "changelog":
                self.changelog_error = str(error)
                return
            if field == "contract_slug":
                self.load_error_message = str(error)
                return
        self.form_error_message = str(error)

    def _clear_feedback(self) -> None:
        self.save_success_message = ""
        self.form_error_message = ""
        self.load_error_message = ""
        self.semantic_version_error = ""
        self.source_code_error = ""
        self.changelog_error = ""

    def _clear_preview(self) -> None:
        self.preview_ready = False
        self.preview_target_version_label = ""
        self.preview_can_publish = False
        self.preview_lint_has_report = False
        self.preview_lint_unavailable_message = ""
        self.preview_lint_status_label = "Unavailable"
        self.preview_lint_status_color_scheme = "gray"
        self.preview_lint_issue_count = 0
        self.preview_lint_error_count = 0
        self.preview_lint_warning_count = 0
        self.preview_lint_info_count = 0
        self.preview_lint_findings = []
        self.preview_diff_previous_version = ""
        self.preview_diff_unified_text = ""
        self.preview_diff_has_previous_version = False
        self.preview_diff_has_changes = False
        self.preview_diff_added_lines = 0
        self.preview_diff_removed_lines = 0
        self.preview_diff_line_delta = 0
        self.preview_diff_hunk_count = 0
        self.preview_diff_context_lines = 3

    def _reset_form(self) -> None:
        self.semantic_version_value = ""
        self.source_code_value = ""
        self.changelog_value = ""
        self.semantic_version_error = ""
        self.source_code_error = ""
        self.changelog_error = ""
        self._clear_preview()


def _serialize_version_row(
    entry: AdminContractVersionHistoryEntry,
) -> AdminContractVersionRowPayload:
    return {
        "semantic_version": entry.semantic_version,
        "status_label": _publication_status_label(entry.status),
        "status_color_scheme": _publication_status_color_scheme(entry.status),
        "lint_status_label": _lint_status_label(entry.lint_status),
        "lint_status_color_scheme": _lint_status_color_scheme(entry.lint_status),
        "previous_version_label": entry.previous_version or "Initial release",
        "created_at_label": format_admin_version_timestamp(entry.created_at),
        "published_at_label": format_admin_version_timestamp(entry.published_at),
        "is_latest_published": entry.is_latest_published,
        "public_detail_href": entry.public_detail_href or "",
        "has_public_detail": entry.public_detail_href is not None,
    }


def _serialize_lint_finding(
    finding,
) -> AdminContractVersionLintFindingPayload:
    return {
        "severity_label": _format_lint_severity_label(finding.severity),
        "severity_color_scheme": _lint_finding_color_scheme(finding.severity),
        "location_label": _format_lint_finding_location(finding.line, finding.column),
        "message": finding.message,
    }


def _publication_status_label(status: PublicationStatus | None) -> str:
    if status is None:
        return "Pending"
    return status.value.replace("_", " ").title()


def _publication_status_color_scheme(status: PublicationStatus | None) -> str:
    if status is PublicationStatus.PUBLISHED:
        return "grass"
    if status in {PublicationStatus.DEPRECATED, PublicationStatus.ARCHIVED}:
        return "orange"
    return "gray"


def _lint_status_label(status: LintStatus | None) -> str:
    if status is LintStatus.PASS:
        return "Pass"
    if status is LintStatus.WARN:
        return "Warn"
    if status is LintStatus.FAIL:
        return "Fail"
    return "Unavailable"


def _lint_status_color_scheme(status: LintStatus | None) -> str:
    if status is LintStatus.PASS:
        return "grass"
    if status is LintStatus.WARN:
        return "orange"
    if status is LintStatus.FAIL:
        return "tomato"
    return "gray"


def _format_lint_severity_label(severity: str) -> str:
    normalized = severity.strip().lower()
    if normalized == "warn":
        return "Warning"
    return normalized.title() or "Issue"


def _lint_finding_color_scheme(severity: str) -> str:
    normalized = severity.strip().lower()
    if normalized in {"error", "fatal"}:
        return "tomato"
    if normalized in {"warn", "warning"}:
        return "orange"
    return "gray"


def _format_lint_finding_location(line: int | None, column: int | None) -> str:
    if line is None and column is None:
        return "Location unavailable"
    if column is None:
        return f"Line {line}"
    return f"Line {line}, Column {column}"


__all__ = ["AdminContractVersionManagerState"]
