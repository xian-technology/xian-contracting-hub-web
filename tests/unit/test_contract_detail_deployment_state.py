from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.models import (
    DeploymentStatus,
    DeploymentTransport,
    PlaygroundTarget,
    User,
    UserRole,
    UserStatus,
)
from contracting_hub.services.deployments import (
    ContractDeploymentAttemptResult,
    ContractDeploymentServiceError,
    ContractDeploymentServiceErrorCode,
)
from contracting_hub.states import ContractDetailState
from contracting_hub.utils.meta import LOGIN_ROUTE


def _build_user() -> User:
    return User(
        id=42,
        email="alice@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )


def _set_route_context(state: ContractDetailState, path: str) -> None:
    router_data = {
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.HEADERS: {"origin": "http://localhost:3000"},
    }
    object.__setattr__(state, "router_data", router_data)
    object.__setattr__(state, "router", RouterData.from_router_data(router_data))


def _build_state(path: str) -> ContractDetailState:
    state = ContractDetailState(_reflex_internal_init=True)
    _set_route_context(state, path)
    return state


def _redirect_path(event) -> str | None:
    if event is None:
        return None
    for key, value in event.args:
        if key._js_expr == "path":
            return value._var_value
    return None


@contextmanager
def _fake_session_scope():
    yield object()


def test_begin_deployment_login_remembers_the_current_contract_detail_path() -> None:
    state = _build_state("/contracts/escrow")
    state.contract_slug = "escrow"
    state.version_label = "1.0.0"
    state.selected_version_is_latest_public = False

    event = state.begin_deployment_login()

    assert state.post_login_path == "/contracts/escrow?version=1.0.0"
    assert _redirect_path(event) == LOGIN_ROUTE


def test_open_deployment_drawer_loads_saved_targets_for_authenticated_users(monkeypatch) -> None:
    state = _build_state("/contracts/escrow")
    state.contract_slug = "escrow"
    state.version_label = "2.0.0"
    state.available_versions = [
        {
            "semantic_version": "2.0.0",
            "href": "/contracts/escrow",
            "status_label": "Published",
            "status_color_scheme": "bronze",
            "published_label": "Mar 8, 2026",
            "is_selected": True,
            "is_latest_public": True,
        }
    ]

    monkeypatch.setattr(
        ContractDetailState,
        "_resolve_user_from_cookie",
        lambda self: _build_user(),
    )
    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.list_playground_targets",
        lambda **_kwargs: [
            PlaygroundTarget(
                id=9,
                user_id=42,
                label="Sandbox primary",
                playground_id="sandbox-main",
                is_default=True,
            )
        ],
    )

    event = state.open_deployment_drawer()

    assert event is None
    assert state.deployment_drawer_open is True
    assert state.deployment_version == "2.0.0"
    assert state.deployment_target_mode == "saved"
    assert state.deployment_saved_target_id == "9"
    assert state.deployment_target_count_label == "1 saved target"
    assert state.deployment_saved_targets[0]["playground_id"] == "sandbox-main"


def test_submit_deployment_records_redirect_results_and_refreshes_saved_targets(
    monkeypatch,
) -> None:
    state = _build_state("/contracts/escrow")
    state.contract_slug = "escrow"
    state.version_label = "2.0.0"
    state.available_versions = [
        {
            "semantic_version": "2.0.0",
            "href": "/contracts/escrow",
            "status_label": "Published",
            "status_color_scheme": "bronze",
            "published_label": "Mar 8, 2026",
            "is_selected": True,
            "is_latest_public": True,
        },
        {
            "semantic_version": "1.0.0",
            "href": "/contracts/escrow?version=1.0.0",
            "status_label": "Deprecated",
            "status_color_scheme": "gray",
            "published_label": "Feb 2, 2026",
            "is_selected": False,
            "is_latest_public": False,
        },
    ]
    state.deployment_drawer_open = True
    state.deployment_target_mode = "saved"
    state.deployment_saved_targets = [
        {
            "id": 9,
            "label": "Sandbox primary",
            "playground_id": "sandbox-main",
            "option_label": "Sandbox primary / sandbox-main / Default",
            "helper_label": "Never used / Default target",
            "is_default": True,
        }
    ]
    state.deployment_saved_target_id = "9"

    monkeypatch.setattr(
        ContractDetailState,
        "_resolve_user_from_cookie",
        lambda self: _build_user(),
    )
    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.deploy_contract_version",
        lambda **_kwargs: ContractDeploymentAttemptResult(
            deployment_id=17,
            contract_slug="escrow",
            semantic_version="1.0.0",
            playground_id="sandbox-main",
            playground_target_id=9,
            status=DeploymentStatus.REDIRECT_REQUIRED,
            transport=DeploymentTransport.DEEP_LINK,
            message="Open the playground redirect.",
            redirect_url="https://playground.local/deploy?payload=encoded",
            external_request_id=None,
            request_payload={"playground_id": "sandbox-main"},
            response_payload={"status": "redirect_required"},
            error_payload=None,
        ),
    )
    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.list_playground_targets",
        lambda **_kwargs: [
            PlaygroundTarget(
                id=9,
                user_id=42,
                label="Sandbox primary",
                playground_id="sandbox-main",
                is_default=True,
                last_used_at=datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc),
            )
        ],
    )

    updates = state.submit_deployment(
        {
            "semantic_version": "1.0.0",
            "target_mode": "saved",
            "playground_target_id": "9",
        }
    )

    assert next(updates) is None
    assert state.deployment_pending is True

    with pytest.raises(StopIteration):
        next(updates)

    assert state.deployment_pending is False
    assert state.deployment_result_status_label == "Redirect ready"
    assert (
        state.deployment_result_message == "Deployment recorded. Open the playground to continue."
    )
    assert (
        state.deployment_result_detail == "Deployment #17 / Version 1.0.0 / Playground sandbox-main"
    )
    assert state.deployment_result_redirect_url == "https://playground.local/deploy?payload=encoded"
    assert state.deployment_result_transport_label == "Deep link"
    assert state.deployment_target_count_label == "1 saved target"


def test_submit_deployment_maps_service_errors_to_field_messages(monkeypatch) -> None:
    state = _build_state("/contracts/escrow")
    state.contract_slug = "escrow"
    state.version_label = "2.0.0"
    state.available_versions = [
        {
            "semantic_version": "2.0.0",
            "href": "/contracts/escrow",
            "status_label": "Published",
            "status_color_scheme": "bronze",
            "published_label": "Mar 8, 2026",
            "is_selected": True,
            "is_latest_public": True,
        }
    ]

    monkeypatch.setattr(
        ContractDetailState,
        "_resolve_user_from_cookie",
        lambda self: _build_user(),
    )
    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.session_scope",
        _fake_session_scope,
    )

    def _fake_deploy_contract_version(**_kwargs):
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.INVALID_PLAYGROUND_ID,
            "Playground ID is required.",
            field="playground_id",
        )

    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.deploy_contract_version",
        _fake_deploy_contract_version,
    )

    updates = state.submit_deployment(
        {
            "semantic_version": "2.0.0",
            "playground_id": "   ",
        }
    )

    assert next(updates) is None
    assert state.deployment_pending is True

    with pytest.raises(StopIteration):
        next(updates)

    assert state.deployment_pending is False
    assert state.deployment_playground_id_error == "Enter a playground ID to continue."
    assert state.deployment_result_message == ""
