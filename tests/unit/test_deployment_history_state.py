from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.models import (
    DeploymentStatus,
    DeploymentTransport,
    Profile,
    User,
    UserRole,
    UserStatus,
)
from contracting_hub.services.deployment_history import (
    DeploymentHistoryEntrySnapshot,
    PrivateDeploymentHistorySnapshot,
    SavedTargetShortcutSnapshot,
)
from contracting_hub.states import DeploymentHistoryState
from contracting_hub.utils.meta import DEPLOYMENT_HISTORY_ROUTE


def _build_user() -> User:
    user = User(
        id=42,
        email="alice@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    user.profile = Profile(username="alice", display_name="Alice Validator")
    return user


def _set_route_context(state: DeploymentHistoryState, path: str) -> None:
    router_data = {
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.HEADERS: {"origin": "http://localhost:3000"},
    }
    object.__setattr__(state, "router_data", router_data)
    object.__setattr__(state, "router", RouterData.from_router_data(router_data))


def _build_state(path: str) -> DeploymentHistoryState:
    state = DeploymentHistoryState(_reflex_internal_init=True)
    _set_route_context(state, path)
    return state


@contextmanager
def _fake_session_scope():
    yield object()


def _build_snapshot() -> PrivateDeploymentHistorySnapshot:
    return PrivateDeploymentHistorySnapshot(
        deployments=(
            DeploymentHistoryEntrySnapshot(
                deployment_id=18,
                contract_slug="escrow",
                contract_display_name="Escrow",
                contract_name="con_escrow",
                semantic_version="1.1.0",
                playground_id="sandbox-main",
                playground_target_id=9,
                playground_target_label="Sandbox primary",
                status=DeploymentStatus.REDIRECT_REQUIRED,
                transport=DeploymentTransport.DEEP_LINK,
                redirect_url="https://playground.local/deploy?payload=encoded",
                external_request_id="req-redirect",
                initiated_at=datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc),
                completed_at=datetime(2026, 3, 9, 12, 1, tzinfo=timezone.utc),
                error_message=None,
            ),
            DeploymentHistoryEntrySnapshot(
                deployment_id=17,
                contract_slug="vault",
                contract_display_name="Vault",
                contract_name="con_vault",
                semantic_version="0.9.0",
                playground_id="adhoc-target",
                playground_target_id=None,
                playground_target_label=None,
                status=DeploymentStatus.FAILED,
                transport=DeploymentTransport.HTTP,
                redirect_url=None,
                external_request_id=None,
                initiated_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
                completed_at=datetime(2026, 3, 8, 10, 2, tzinfo=timezone.utc),
                error_message="Playground rejected the deployment payload.",
            ),
        ),
        saved_targets=(
            SavedTargetShortcutSnapshot(
                id=9,
                label="Sandbox primary",
                playground_id="sandbox-main",
                is_default=True,
                last_used_at=datetime(2026, 3, 9, 12, 1, tzinfo=timezone.utc),
            ),
        ),
    )


def test_load_page_populates_deployment_history_snapshot(monkeypatch) -> None:
    state = _build_state(DEPLOYMENT_HISTORY_ROUTE)

    monkeypatch.setattr(
        "contracting_hub.states.deployment_history.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        DeploymentHistoryState,
        "_resolve_user_from_cookie",
        lambda self: _build_user(),
    )
    monkeypatch.setattr(
        "contracting_hub.states.deployment_history.load_private_deployment_history_snapshot",
        lambda **_kwargs: _build_snapshot(),
    )

    event = state.load_page()

    assert event is None
    assert state.saved_target_shortcut_count_label == "1 saved target"
    assert state.deployment_history_count_label == "2 deployments"
    assert state.visible_deployment_entries[0]["contract_title"] == "Escrow"
    assert state.visible_deployment_entries[0]["status_label"] == "Redirect ready"
    assert state.visible_deployment_entries[1]["target_label"] == "Ad hoc target"


def test_set_target_filter_limits_visible_entries_to_one_saved_target() -> None:
    state = _build_state(DEPLOYMENT_HISTORY_ROUTE)

    state._apply_snapshot(_build_snapshot())
    state.set_target_filter("9")

    assert len(state.visible_deployment_entries) == 1
    assert state.visible_deployment_entries[0]["playground_id"] == "sandbox-main"
    assert state.deployment_history_count_label == "1 of 2 deployments"
    assert state.active_filter_description == "Viewing deployments for Sandbox primary."


def test_show_all_deployments_restores_the_full_history_list() -> None:
    state = _build_state(DEPLOYMENT_HISTORY_ROUTE)

    state._apply_snapshot(_build_snapshot())
    state.set_target_filter("9")
    state.show_all_deployments()

    assert len(state.visible_deployment_entries) == 2
    assert state.deployment_history_count_label == "2 deployments"
    assert state.active_filter_description == "Viewing all recorded deployments."
