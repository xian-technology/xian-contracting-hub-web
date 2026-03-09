from __future__ import annotations

from contextlib import contextmanager

import reflex as rx
from reflex import constants
from reflex.istate.data import RouterData

import contracting_hub.states.admin_contracts as admin_contracts_state_module
from contracting_hub.models import Profile, PublicationStatus, User, UserRole, UserStatus
from contracting_hub.services.admin_contracts import (
    AdminContractActionError,
    AdminContractActionErrorCode,
    AdminContractFeaturedFilter,
    AdminContractIndexEntry,
    AdminContractIndexSnapshot,
    AdminContractStatusFilter,
    AdminContractStatusTab,
)
from contracting_hub.states.admin_contracts import AdminContractsState
from contracting_hub.utils.meta import HOME_ROUTE


def _build_admin_user() -> User:
    user = User(
        id=7,
        email="admin@example.com",
        password_hash="hashed",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    user.profile = Profile(username="admin", display_name="Catalog Admin")
    return user


def _set_route_context(state: AdminContractsState, path: str) -> None:
    router_data = {
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.HEADERS: {"origin": "http://localhost:3000"},
    }
    object.__setattr__(state, "router_data", router_data)
    object.__setattr__(state, "router", RouterData.from_router_data(router_data))


def _redirect_path(event: rx.event.EventSpec | None) -> str | None:
    if event is None:
        return None
    for key, value in event.args:
        if key._js_expr == "path":
            return value._var_value
    return None


def _build_snapshot() -> AdminContractIndexSnapshot:
    return AdminContractIndexSnapshot(
        results=(
            AdminContractIndexEntry(
                slug="draft-escrow",
                display_name="Draft Escrow",
                contract_name="con_draft_escrow",
                short_summary="Draft-only escrow shell.",
                status=PublicationStatus.DRAFT,
                featured=False,
                author_name="Alice Curator",
                primary_category_name="DeFi",
                category_names=("DeFi",),
                latest_public_version=None,
                updated_at_label="2026-03-09",
                public_detail_href=None,
                edit_href="/admin/contracts/draft-escrow/edit",
                can_publish=False,
                can_archive=True,
                can_delete=True,
                action_hint="Draft-only shell. Safe to delete if the entry is no longer needed.",
            ),
        ),
        query="escrow",
        status_filter=AdminContractStatusFilter.DRAFT,
        featured_filter=AdminContractFeaturedFilter.FEATURED,
        status_tabs=(
            AdminContractStatusTab(
                value=AdminContractStatusFilter.DRAFT,
                label="Draft",
                count=1,
                is_active=True,
                href="/admin/contracts?query=escrow&status=draft&featured=featured",
            ),
        ),
        total_results=1,
    )


def test_admin_contracts_state_load_page_applies_snapshot_and_auth_shell(monkeypatch) -> None:
    state = AdminContractsState(_reflex_internal_init=True)
    _set_route_context(state, "/admin/contracts")

    monkeypatch.setattr(
        AdminContractsState,
        "_resolve_user_from_cookie",
        lambda self: _build_admin_user(),
    )
    monkeypatch.setattr(
        admin_contracts_state_module,
        "load_admin_contract_index_snapshot_safe",
        lambda **_: _build_snapshot(),
    )

    state.load_page()

    assert state.current_user_id == 7
    assert state.current_identity_label == "Catalog Admin"
    assert state.current_identity_secondary == "@admin"
    assert state.has_current_identity_secondary is True
    assert state.is_authenticated is True
    assert state.has_results is True
    assert state.query == "escrow"
    assert state.selected_status_filter == "draft"
    assert state.selected_featured_filter == "featured"
    assert state.result_count_label == "1 contract"
    assert state.contract_rows[0]["slug"] == "draft-escrow"
    assert (
        state.status_tabs[0]["href"]
        == "/admin/contracts?query=escrow&status=draft&featured=featured"
    )


def test_admin_contracts_state_apply_filters_and_logout(monkeypatch) -> None:
    state = AdminContractsState(_reflex_internal_init=True)
    _set_route_context(state, "/admin/contracts")
    state.selected_status_filter = "draft"
    state.auth_session_token = "session-token"
    state.current_user_id = 7
    state.action_success_message = "done"
    state.action_error_message = "error"

    logout_calls: list[str] = []

    @contextmanager
    def fake_session_scope():
        yield object()

    def fake_logout_user(*, session, session_token: str) -> bool:
        logout_calls.append(session_token)
        return True

    monkeypatch.setattr(admin_contracts_state_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(admin_contracts_state_module, "logout_user", fake_logout_user)

    filter_event = state.apply_filters({"query": " vault ", "featured": "not_featured"})
    logout_event = state.logout_current_user()

    assert (
        _redirect_path(filter_event)
        == "/admin/contracts?query=vault&status=draft&featured=not_featured"
    )
    assert logout_calls == ["session-token"]
    assert state.auth_session_token == ""
    assert state.current_user_id is None
    assert state.action_success_message == ""
    assert state.action_error_message == ""
    assert _redirect_path(logout_event) == HOME_ROUTE


def test_admin_contracts_state_action_wrappers_and_feedback(monkeypatch) -> None:
    state = AdminContractsState(_reflex_internal_init=True)
    recorded_actions: list[dict[str, object]] = []

    def fake_perform_action(self, **kwargs) -> None:
        recorded_actions.append(kwargs)

    monkeypatch.setattr(AdminContractsState, "_perform_action", fake_perform_action)

    state.publish_contract("escrow")
    state.archive_contract("vault")
    state.delete_contract("draft-escrow")

    assert [item["slug"] for item in recorded_actions] == [
        "escrow",
        "vault",
        "draft-escrow",
    ]
    assert recorded_actions[0]["success_message"] == (
        "Contract published and restored to the public catalog."
    )
    assert recorded_actions[1]["success_message"] == (
        "Contract archived while preserving its version history."
    )
    assert recorded_actions[2]["success_message"] == "Contract deleted."


def test_admin_contracts_state_perform_action_handles_success_and_failure(monkeypatch) -> None:
    state = AdminContractsState(_reflex_internal_init=True)
    state.query = "escrow"
    state.selected_status_filter = "draft"
    state.selected_featured_filter = "all"

    reloaded: list[tuple[str, str, str]] = []

    @contextmanager
    def fake_session_scope():
        yield object()

    def fake_reload_snapshot(self) -> None:
        reloaded.append(
            (
                self.query,
                self.selected_status_filter,
                self.selected_featured_filter,
            )
        )

    def failing_action(**kwargs) -> None:
        raise AdminContractActionError(
            AdminContractActionErrorCode.PUBLISHABLE_VERSION_REQUIRED,
            "Publish a contract version before making the contract public.",
        )

    monkeypatch.setattr(admin_contracts_state_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(AdminContractsState, "_reload_snapshot", fake_reload_snapshot)

    state._perform_action(
        slug="draft-escrow",
        action=lambda **kwargs: None,
        success_message="updated",
    )
    assert state.action_success_message == "updated"
    assert state.action_error_message == ""
    assert reloaded == [("escrow", "draft", "all")]

    state._perform_action(
        slug="draft-escrow",
        action=failing_action,
        success_message="ignored",
    )
    assert state.action_success_message == ""
    assert state.action_error_message == (
        "Publish a contract version before making the contract public."
    )
