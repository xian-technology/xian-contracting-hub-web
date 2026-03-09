from __future__ import annotations

from contextlib import contextmanager

import pytest
from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.models import User, UserRole, UserStatus
from contracting_hub.services.ratings import (
    ContractRatingServiceError,
    ContractRatingServiceErrorCode,
)
from contracting_hub.services.stars import ContractStarToggleResult
from contracting_hub.states import ContractDetailState


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


@contextmanager
def _fake_session_scope():
    yield object()


def test_toggle_star_prompts_anonymous_users_to_log_in(monkeypatch) -> None:
    state = _build_state("/contracts/escrow")
    state.contract_slug = "escrow"
    state.selected_version_is_latest_public = True

    monkeypatch.setattr(
        ContractDetailState,
        "_resolve_user_from_cookie",
        lambda self: None,
    )

    called = {"toggle_service": False}

    def _fake_toggle_contract_star(**_kwargs):
        called["toggle_service"] = True
        raise AssertionError("star service should not run for anonymous users")

    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.toggle_contract_star",
        _fake_toggle_contract_star,
    )

    list(state.toggle_star())

    assert called["toggle_service"] is False
    assert state.engagement_login_prompt_message == "Log in to star this contract."
    assert state.post_login_path == "/contracts/escrow"


def test_toggle_star_applies_optimistic_state_before_success(monkeypatch) -> None:
    state = _build_state("/contracts/escrow")
    state.contract_slug = "escrow"
    state._apply_star_count(2)

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
        "contracting_hub.states.contract_detail.toggle_contract_star",
        lambda **_kwargs: ContractStarToggleResult(
            contract_id=7,
            contract_slug="escrow",
            star_count=3,
            starred_by_user=True,
        ),
    )

    updates = state.toggle_star()
    assert next(updates) is None

    assert state.star_pending is True
    assert state.starred_by_current_user is True
    assert state.star_count_value == 3
    assert state.star_count == "3"

    with pytest.raises(StopIteration):
        next(updates)

    assert state.star_pending is False
    assert state.engagement_success_message == "Saved to favorites."
    assert state.engagement_error_message == ""


def test_submit_rating_rolls_back_optimistic_changes_after_error(monkeypatch) -> None:
    state = _build_state("/contracts/escrow")
    state.contract_slug = "escrow"
    state._apply_rating_aggregate(
        average_rating=4.5,
        rating_count=2,
    )

    monkeypatch.setattr(
        ContractDetailState,
        "_resolve_user_from_cookie",
        lambda self: _build_user(),
    )
    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.session_scope",
        _fake_session_scope,
    )

    def _fake_submit_contract_rating(**_kwargs):
        raise ContractRatingServiceError(
            ContractRatingServiceErrorCode.CONTRACT_NOT_RATEABLE,
            "Only public contracts can be rated.",
            field="contract_slug",
        )

    monkeypatch.setattr(
        "contracting_hub.states.contract_detail.submit_contract_rating",
        _fake_submit_contract_rating,
    )

    updates = state.submit_rating(4)
    assert next(updates) is None

    assert state.rating_pending is True
    assert state.current_user_rating_score == 4
    assert state.rating_count_value == 3
    assert state.rating_headline == "4.3 avg"

    with pytest.raises(StopIteration):
        next(updates)

    assert state.rating_pending is False
    assert state.current_user_rating_score is None
    assert state.rating_count_value == 2
    assert state.rating_headline == "4.5 avg"
    assert state.engagement_error_message == "Only public contracts can be rated."
