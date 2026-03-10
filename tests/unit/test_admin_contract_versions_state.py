from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import reflex as rx
from reflex import constants
from reflex.istate.data import RouterData

import contracting_hub.states.admin_contract_versions as admin_contract_versions_state_module
from contracting_hub.models import (
    LintStatus,
    Profile,
    PublicationStatus,
    User,
    UserRole,
    UserStatus,
)
from contracting_hub.services.admin_contract_versions import (
    AdminContractVersionHistoryEntry,
    AdminContractVersionLintFinding,
    AdminContractVersionManagerServiceError,
    AdminContractVersionManagerServiceErrorCode,
    AdminContractVersionManagerSnapshot,
    AdminContractVersionPreview,
    build_empty_admin_contract_version_manager_snapshot,
)
from contracting_hub.services.auth import AuthServiceError, AuthServiceErrorCode
from contracting_hub.services.contract_versions import (
    ContractVersionServiceError,
    ContractVersionServiceErrorCode,
)
from contracting_hub.states.admin_contract_versions import (
    AdminContractVersionManagerState,
    _format_lint_finding_location,
    _format_lint_severity_label,
    _lint_finding_color_scheme,
    _lint_status_color_scheme,
    _lint_status_label,
    _publication_status_color_scheme,
    _publication_status_label,
    _serialize_lint_finding,
    _serialize_version_row,
)


def _build_admin_user(*, with_profile: bool = True) -> User:
    user = User(
        id=7,
        email="admin@example.com",
        password_hash="hashed",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    if with_profile:
        user.profile = Profile(username="admin", display_name="Catalog Admin")
    return user


def _set_route_context(
    state: AdminContractVersionManagerState,
    path: str,
    *,
    params: dict[str, str] | None = None,
) -> None:
    router_data = {
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.HEADERS: {"origin": "http://localhost:3000"},
    }
    object.__setattr__(state, "router_data", router_data)
    object.__setattr__(state, "router", RouterData.from_router_data(router_data))
    object.__setattr__(state.router.page, "params", params or {})


def _redirect_path(event: rx.event.EventSpec | None) -> str | None:
    if event is None:
        return None
    for key, value in event.args:
        if key._js_expr == "path":
            return value._var_value
    return None


@contextmanager
def _fake_session_scope():
    yield object()


def _build_snapshot() -> AdminContractVersionManagerSnapshot:
    return AdminContractVersionManagerSnapshot(
        contract_id=12,
        slug="escrow",
        display_name="Escrow",
        contract_name="con_escrow",
        contract_status=PublicationStatus.PUBLISHED,
        latest_public_version="1.0.0",
        latest_saved_version="1.1.0",
        public_detail_href="/contracts/escrow",
        edit_href="/admin/contracts/escrow/edit",
        version_history=(
            AdminContractVersionHistoryEntry(
                semantic_version="1.1.0",
                status=PublicationStatus.DRAFT,
                previous_version="1.0.0",
                lint_status=LintStatus.WARN,
                created_at=datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc),
                published_at=None,
                is_latest_published=False,
                public_detail_href=None,
            ),
            AdminContractVersionHistoryEntry(
                semantic_version="1.0.0",
                status=PublicationStatus.PUBLISHED,
                previous_version=None,
                lint_status=LintStatus.PASS,
                created_at=datetime(2026, 3, 8, 9, 0, tzinfo=timezone.utc),
                published_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
                is_latest_published=True,
                public_detail_href="/contracts/escrow",
            ),
        ),
    )


def _build_preview(
    *,
    lint_status: LintStatus | None = LintStatus.WARN,
    has_lint_report: bool = True,
    can_publish: bool = False,
    lint_unavailable_message: str | None = None,
) -> AdminContractVersionPreview:
    return AdminContractVersionPreview(
        semantic_version="1.2.0",
        changelog="Adds a safer settle path.",
        previous_version="1.1.0",
        has_lint_report=has_lint_report,
        lint_status=lint_status,
        lint_summary={
            "issue_count": 3,
            "error_count": 1,
            "warning_count": 1,
            "info_count": 1,
        }
        if has_lint_report
        else None,
        lint_findings=(
            AdminContractVersionLintFinding(
                severity="warn",
                line=7,
                column=4,
                message="Prefer a narrower exported surface.",
            ),
            AdminContractVersionLintFinding(
                severity="error",
                line=None,
                column=None,
                message="Blocking issue.",
            ),
        )
        if has_lint_report
        else (),
        lint_unavailable_message=lint_unavailable_message,
        diff_summary={
            "has_previous_version": True,
            "has_changes": True,
            "added_lines": 4,
            "removed_lines": 2,
            "line_delta": 2,
            "hunk_count": 2,
            "context_lines": 1,
        },
        unified_diff="@@ -1 +1 @@\n-return 'old'\n+return 'new'\n",
        can_publish=can_publish,
    )


def test_admin_contract_versions_state_load_page_applies_snapshot_and_auth_shell(
    monkeypatch,
) -> None:
    state = AdminContractVersionManagerState(_reflex_internal_init=True)
    _set_route_context(
        state,
        "/admin/contracts/escrow/versions",
        params={"slug": "Escrow"},
    )

    requested_slugs: list[str | None] = []

    monkeypatch.setattr(
        AdminContractVersionManagerState,
        "_resolve_user_from_cookie",
        lambda self: _build_admin_user(),
    )

    def fake_load_snapshot(*, contract_slug: str | None) -> AdminContractVersionManagerSnapshot:
        requested_slugs.append(contract_slug)
        return _build_snapshot()

    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "load_admin_contract_version_manager_snapshot_safe",
        fake_load_snapshot,
    )

    state.load_page()

    assert requested_slugs == ["escrow"]
    assert state.load_state == "ready"
    assert state.current_user_id == 7
    assert state.current_identity_label == "Catalog Admin"
    assert state.current_identity_secondary == "@admin"
    assert state.has_current_identity_secondary is True
    assert state.is_authenticated is True
    assert state.page_heading == "Manage versions for Escrow"
    assert state.page_intro.startswith("Add immutable source snapshots")
    assert state.has_public_detail is True
    assert state.has_relation_manager is True
    assert state.has_version_history is True
    assert state.version_count_label == "2 saved versions"
    assert state.contract_status_label == "Published"
    assert state.contract_status_color_scheme == "grass"
    assert state.latest_public_version_label == "1.0.0"
    assert state.latest_saved_version_label == "1.1.0"
    assert state.metadata_edit_href == "/admin/contracts/escrow/edit"
    assert state.relations_href == "/admin/contracts/escrow/relations"
    assert state.version_rows[0]["status_label"] == "Draft"
    assert state.version_rows[0]["previous_version_label"] == "1.0.0"
    assert state.version_rows[0]["published_at_label"] == "Pending"
    assert state.version_rows[1]["has_public_detail"] is True
    assert state.version_rows[1]["public_detail_href"] == "/contracts/escrow"


def test_admin_contract_versions_state_computed_properties_cover_fallbacks_and_labels() -> None:
    state = AdminContractVersionManagerState(_reflex_internal_init=True)

    assert state.current_identity_label == "Account"
    assert state.current_identity_secondary == ""
    assert state.page_heading == "Manage contract versions"
    assert state.version_count_label == "0 saved versions"
    assert state.preview_lint_summary_copy == (
        "Run a preview to inspect lint results before saving the version."
    )
    assert state.preview_publish_hint == (
        "Run a preview before publishing so lint and diff feedback match the current source."
    )
    assert state.source_line_count_label == "0 lines"

    state.current_user_email = "admin@example.com"
    assert state.current_identity_label == "admin@example.com"
    assert state.current_identity_secondary == ""

    state.current_username = "admin"
    assert state.current_identity_label == "@admin"
    assert state.current_identity_secondary == "admin@example.com"

    state.current_display_name = "Catalog Admin"
    assert state.current_identity_label == "Catalog Admin"
    assert state.current_identity_secondary == "@admin"

    state.version_rows = [{"semantic_version": "1.0.0"}]  # type: ignore[list-item]
    assert state.version_count_label == "1 saved version"

    state.contract_slug = "missing"
    state.load_error_message = "The requested contract could not be found."
    assert state.show_missing_contract_state is True

    state.preview_ready = True
    state.preview_lint_has_report = True
    state.preview_lint_status_label = "Fail"
    state.preview_lint_issue_count = 1
    state.preview_lint_error_count = 1
    state.preview_lint_warning_count = 2
    state.preview_lint_info_count = 1
    state.preview_lint_findings = [{"message": "Issue"}]  # type: ignore[list-item]
    state.preview_can_publish = False
    state.preview_diff_has_previous_version = True
    state.preview_diff_has_changes = True
    state.preview_diff_unified_text = "  diff body  "
    state.preview_diff_added_lines = 1
    state.preview_diff_removed_lines = 2
    state.preview_diff_line_delta = -1
    state.preview_diff_hunk_count = 1
    state.preview_diff_context_lines = 2
    state.source_code_value = "line one\nline two"

    assert state.has_preview_lint_findings is True
    assert state.has_preview_diff_content is True
    assert state.preview_lint_issue_count_label == "1 issue"
    assert state.preview_lint_error_count_label == "1 error"
    assert state.preview_lint_warning_count_label == "2 warnings"
    assert state.preview_lint_info_count_label == "1 info note"
    assert state.preview_lint_summary_copy.startswith("Blocking lint issues were detected")
    assert state.preview_publish_hint == (
        "Publishing is blocked until the preview no longer contains lint errors."
    )
    assert state.preview_diff_added_lines_label == "+1 line added"
    assert state.preview_diff_removed_lines_label == "-2 lines removed"
    assert state.preview_diff_line_delta_label == "-1 net lines"
    assert state.preview_diff_hunk_count_label == "1 diff hunk"
    assert state.preview_diff_context_lines_label == "2 context lines"
    assert state.source_line_count_label == "2 lines"

    state.preview_lint_unavailable_message = "Linting unavailable."
    assert state.preview_lint_summary_copy == "Linting unavailable."

    state.preview_lint_unavailable_message = ""
    state.preview_lint_status_label = "Warn"
    assert state.preview_lint_summary_copy == (
        "Non-blocking lint warnings were detected for the current source draft."
    )

    state.preview_lint_status_label = "Pass"
    state.preview_can_publish = True
    state.preview_diff_added_lines = 3
    state.preview_diff_removed_lines = 1
    state.preview_diff_line_delta = 4
    state.preview_diff_hunk_count = 2
    state.preview_diff_context_lines = 1
    state.source_code_value = "single line"

    assert state.preview_lint_summary_copy == (
        "No lint issues were reported for the current source draft."
    )
    assert state.preview_publish_hint == "This preview can be published immediately."
    assert state.preview_diff_added_lines_label == "+3 lines added"
    assert state.preview_diff_removed_lines_label == "-1 line removed"
    assert state.preview_diff_line_delta_label == "+4 net lines"
    assert state.preview_diff_hunk_count_label == "2 diff hunks"
    assert state.preview_diff_context_lines_label == "1 context line"
    assert state.source_line_count_label == "1 line"

    state.preview_diff_line_delta = 0
    assert state.preview_diff_line_delta_label == "0 net lines"


def test_admin_contract_versions_state_sync_setters_logout_and_cookie_resolution(
    monkeypatch,
) -> None:
    state = AdminContractVersionManagerState(_reflex_internal_init=True)
    state.auth_session_token = "session-token"
    state.preview_ready = True
    state.preview_lint_status_label = "Fail"
    state.preview_lint_findings = [{"message": "Issue"}]  # type: ignore[list-item]
    state.preview_diff_unified_text = "diff"
    state.semantic_version_error = "old"
    state.source_code_error = "old"
    state.changelog_error = "old"
    state.save_success_message = "saved"
    state.form_error_message = "form"
    state.load_error_message = "load"

    logout_calls: list[str] = []
    resolved_tokens: list[str] = []

    def fake_resolve_current_user(*, session, session_token: str | None) -> User:
        resolved_tokens.append(str(session_token))
        return _build_admin_user(with_profile=False)

    def fake_logout_user(*, session, session_token: str) -> bool:
        logout_calls.append(session_token)
        return True

    monkeypatch.setattr(admin_contract_versions_state_module, "session_scope", _fake_session_scope)
    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "resolve_current_user",
        fake_resolve_current_user,
    )
    monkeypatch.setattr(admin_contract_versions_state_module, "logout_user", fake_logout_user)

    state.sync_auth_state()

    assert resolved_tokens == ["session-token"]
    assert state.current_user_id == 7
    assert state.current_user_email == "admin@example.com"
    assert state.current_username is None
    assert state.current_display_name is None

    state.set_semantic_version_value("1.2.0")
    state.set_source_code_value("print('ok')")
    state.set_changelog_value("Adds preview reset.")

    assert state.semantic_version_value == "1.2.0"
    assert state.source_code_value == "print('ok')"
    assert state.changelog_value == "Adds preview reset."
    assert state.preview_ready is False
    assert state.preview_lint_status_label == "Unavailable"
    assert state.preview_diff_unified_text == ""
    assert state.semantic_version_error == ""
    assert state.source_code_error == ""
    assert state.changelog_error == ""

    event = state.logout_current_user()

    assert logout_calls == ["session-token"]
    assert state.auth_session_token == ""
    assert state.current_user_id is None
    assert state.current_user_email is None
    assert state.current_username is None
    assert state.current_display_name is None
    assert state.save_success_message == ""
    assert state.form_error_message == ""
    assert state.load_error_message == ""
    assert state.preview_ready is False
    assert _redirect_path(event) == "/"


def test_admin_contract_versions_state_load_page_handles_auth_and_snapshot_failures(
    monkeypatch,
) -> None:
    unauthenticated_state = AdminContractVersionManagerState(_reflex_internal_init=True)
    _set_route_context(
        unauthenticated_state,
        "/admin/contracts/missing/versions",
        params={"slug": "missing"},
    )
    monkeypatch.setattr(
        AdminContractVersionManagerState,
        "_resolve_user_from_cookie",
        lambda self: None,
    )

    unauthenticated_state.load_page()

    assert unauthenticated_state.load_state == "error"
    assert unauthenticated_state.has_load_error is True
    assert unauthenticated_state.load_error_message == (
        "Administrator access is required to manage versions."
    )

    missing_state = AdminContractVersionManagerState(_reflex_internal_init=True)
    _set_route_context(
        missing_state,
        "/admin/contracts/missing/versions",
        params={"slug": "missing"},
    )
    monkeypatch.setattr(
        AdminContractVersionManagerState,
        "_resolve_user_from_cookie",
        lambda self: _build_admin_user(),
    )
    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "load_admin_contract_version_manager_snapshot_safe",
        lambda **_: build_empty_admin_contract_version_manager_snapshot(contract_slug="missing"),
    )

    missing_state.load_page()

    assert missing_state.load_state == "ready"
    assert missing_state.load_error_message == "The requested contract could not be found."
    assert missing_state.contract_slug == "missing"
    assert missing_state.metadata_edit_href == "/admin/contracts/missing/edit"
    assert missing_state.relations_href == ""
    assert missing_state.show_missing_contract_state is True

    handled_state = AdminContractVersionManagerState(_reflex_internal_init=True)
    _set_route_context(
        handled_state,
        "/admin/contracts/error/versions",
        params={"slug": "error"},
    )

    def raise_service_error(**_: object) -> AdminContractVersionManagerSnapshot:
        raise AdminContractVersionManagerServiceError(
            AdminContractVersionManagerServiceErrorCode.CONTRACT_NOT_FOUND,
            "Catalog lookup failed.",
            field="contract_slug",
        )

    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "load_admin_contract_version_manager_snapshot_safe",
        raise_service_error,
    )

    handled_state.load_page()

    assert handled_state.load_state == "ready"
    assert handled_state.load_error_message == "Catalog lookup failed."
    assert handled_state.contract_slug == "error"

    failed_state = AdminContractVersionManagerState(_reflex_internal_init=True)
    _set_route_context(
        failed_state,
        "/admin/contracts/boom/versions",
        params={"slug": "boom"},
    )

    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "load_admin_contract_version_manager_snapshot_safe",
        lambda **_: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    failed_state.load_page()

    assert failed_state.load_state == "error"
    assert failed_state.load_error_message == "boom"
    assert failed_state.contract_slug == "boom"


def test_admin_contract_versions_state_run_preview_applies_preview_and_maps_errors(
    monkeypatch,
) -> None:
    state = AdminContractVersionManagerState(_reflex_internal_init=True)
    state.auth_session_token = "session-token"
    state.contract_slug = "escrow"
    state.semantic_version_value = "1.2.0"
    state.source_code_value = "@export\ndef run():\n    return 'ok'\n"
    state.changelog_value = "Preview notes."

    preview_calls: list[dict[str, object]] = []

    def fake_preview_admin_contract_version(**kwargs) -> AdminContractVersionPreview:
        preview_calls.append(kwargs)
        return _build_preview()

    monkeypatch.setattr(admin_contract_versions_state_module, "session_scope", _fake_session_scope)
    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "preview_admin_contract_version",
        fake_preview_admin_contract_version,
    )

    state.run_preview()

    assert preview_calls[0]["session_token"] == "session-token"
    assert preview_calls[0]["contract_slug"] == "escrow"
    assert state.preview_ready is True
    assert state.preview_target_version_label == "1.2.0"
    assert state.preview_can_publish is False
    assert state.preview_lint_has_report is True
    assert state.preview_lint_status_label == "Warn"
    assert state.preview_lint_status_color_scheme == "orange"
    assert state.preview_lint_issue_count == 3
    assert state.preview_lint_error_count == 1
    assert state.preview_lint_warning_count == 1
    assert state.preview_lint_info_count == 1
    assert state.preview_lint_findings[0]["severity_label"] == "Warning"
    assert state.preview_lint_findings[0]["location_label"] == "Line 7, Column 4"
    assert state.preview_lint_findings[1]["severity_color_scheme"] == "tomato"
    assert state.preview_diff_previous_version == "1.1.0"
    assert state.preview_diff_has_previous_version is True
    assert state.preview_diff_has_changes is True
    assert state.preview_diff_added_lines == 4
    assert state.preview_diff_removed_lines == 2
    assert state.preview_diff_line_delta == 2
    assert state.preview_diff_hunk_count == 2
    assert state.preview_diff_context_lines == 1
    assert state.has_preview_diff_content is True

    state._apply_service_error(
        AdminContractVersionManagerServiceError(
            AdminContractVersionManagerServiceErrorCode.INVALID_SEMANTIC_VERSION,
            "Bad version.",
            field="semantic_version",
        )
    )
    state._apply_service_error(
        AdminContractVersionManagerServiceError(
            AdminContractVersionManagerServiceErrorCode.INVALID_CHANGELOG,
            "Bad changelog.",
            field="changelog",
        )
    )
    state._apply_service_error(
        AuthServiceError(
            AuthServiceErrorCode.AUTHENTICATION_REQUIRED,
            "Sign in again.",
            field="session_token",
        )
    )
    state._apply_service_error(
        ContractVersionServiceError(
            ContractVersionServiceErrorCode.CONTRACT_NOT_FOUND,
            "Missing contract.",
            field="contract_slug",
        )
    )
    state._apply_service_error(RuntimeError("Unknown failure."))

    assert state.semantic_version_error == "Bad version."
    assert state.changelog_error == "Bad changelog."
    assert state.load_error_message == "Missing contract."
    assert state.form_error_message == "Unknown failure."

    def raise_source_error(**_: object) -> AdminContractVersionPreview:
        raise AdminContractVersionManagerServiceError(
            AdminContractVersionManagerServiceErrorCode.INVALID_SOURCE_CODE,
            "Source is invalid.",
            field="source_code",
        )

    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "preview_admin_contract_version",
        raise_source_error,
    )
    state.run_preview()

    assert state.source_code_error == "Source is invalid."
    assert state.preview_ready is False


def test_admin_contract_versions_state_submit_version_saves_publishes_and_handles_errors(
    monkeypatch,
) -> None:
    state = AdminContractVersionManagerState(_reflex_internal_init=True)
    state.auth_session_token = "session-token"
    state.contract_slug = "escrow"
    state.semantic_version_value = "1.2.0"
    state.source_code_value = "@export\ndef run():\n    return 'ok'\n"
    state.changelog_value = "Draft notes."
    state.preview_ready = True

    create_calls: list[dict[str, object]] = []
    reload_slugs: list[str | None] = []

    def fake_create_admin_contract_version(**kwargs):
        create_calls.append(kwargs)
        return SimpleNamespace(semantic_version=kwargs["semantic_version"])

    def fake_reload_snapshot(*, contract_slug: str | None) -> AdminContractVersionManagerSnapshot:
        reload_slugs.append(contract_slug)
        return _build_snapshot()

    monkeypatch.setattr(admin_contract_versions_state_module, "session_scope", _fake_session_scope)
    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "create_admin_contract_version",
        fake_create_admin_contract_version,
    )
    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "load_admin_contract_version_manager_snapshot_safe",
        fake_reload_snapshot,
    )

    state.save_draft_version()

    assert create_calls[0]["publish_now"] is False
    assert reload_slugs == ["escrow"]
    assert state.save_success_message == "Saved draft version 1.2.0."
    assert state.semantic_version_value == ""
    assert state.source_code_value == ""
    assert state.changelog_value == ""
    assert state.preview_ready is False
    assert state.version_rows[0]["semantic_version"] == "1.1.0"

    state.semantic_version_value = "1.3.0"
    state.source_code_value = "@export\ndef run():\n    return 'published'\n"
    state.changelog_value = "Publish notes."

    state.publish_version()

    assert create_calls[1]["publish_now"] is True
    assert state.save_success_message == "Published version 1.3.0."

    def raise_source_error(**kwargs):
        del kwargs
        raise ContractVersionServiceError(
            ContractVersionServiceErrorCode.INVALID_SOURCE_CODE,
            "Publishable source required.",
            field="source_code",
        )

    monkeypatch.setattr(
        admin_contract_versions_state_module,
        "create_admin_contract_version",
        raise_source_error,
    )

    state.source_code_value = "bad source"
    state.save_draft_version()

    assert state.source_code_error == "Publishable source required."
    assert state.save_success_message == ""


def test_admin_contract_versions_state_helper_serializers_and_formatters() -> None:
    serialized_row = _serialize_version_row(
        AdminContractVersionHistoryEntry(
            semantic_version="0.9.0",
            status=PublicationStatus.DEPRECATED,
            previous_version=None,
            lint_status=None,
            created_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
            is_latest_published=False,
            public_detail_href=None,
        )
    )
    serialized_finding = _serialize_lint_finding(
        AdminContractVersionLintFinding(
            severity="fatal",
            line=None,
            column=None,
            message="No export found.",
        )
    )

    assert serialized_row["status_label"] == "Deprecated"
    assert serialized_row["status_color_scheme"] == "orange"
    assert serialized_row["lint_status_label"] == "Unavailable"
    assert serialized_row["previous_version_label"] == "Initial release"
    assert serialized_row["has_public_detail"] is False

    assert serialized_finding["severity_label"] == "Fatal"
    assert serialized_finding["severity_color_scheme"] == "tomato"
    assert serialized_finding["location_label"] == "Location unavailable"
    assert serialized_finding["message"] == "No export found."

    assert _publication_status_label(None) == "Pending"
    assert _publication_status_color_scheme(PublicationStatus.PUBLISHED) == "grass"
    assert _publication_status_color_scheme(PublicationStatus.ARCHIVED) == "orange"
    assert _publication_status_color_scheme(PublicationStatus.DRAFT) == "gray"
    assert _lint_status_label(LintStatus.PASS) == "Pass"
    assert _lint_status_label(LintStatus.FAIL) == "Fail"
    assert _lint_status_color_scheme(LintStatus.WARN) == "orange"
    assert _lint_status_color_scheme(None) == "gray"
    assert _format_lint_severity_label(" warn ") == "Warning"
    assert _format_lint_severity_label("  ") == "Issue"
    assert _lint_finding_color_scheme("warning") == "orange"
    assert _lint_finding_color_scheme("info") == "gray"
    assert _format_lint_finding_location(None, None) == "Location unavailable"
    assert _format_lint_finding_location(4, None) == "Line 4"
    assert _format_lint_finding_location(4, 2) == "Line 4, Column 2"
