from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import reflex as rx
from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.models import Profile, User, UserRole, UserStatus
from contracting_hub.services.auth import (
    AuthenticatedSession,
    AuthServiceError,
    AuthServiceErrorCode,
)
from contracting_hub.states import AuthState


def _build_user(*, role: UserRole = UserRole.USER) -> User:
    user = User(
        id=42 if role is UserRole.USER else 7,
        email="alice@example.com" if role is UserRole.USER else "admin@example.com",
        password_hash="hashed",
        role=role,
        status=UserStatus.ACTIVE,
    )
    user.profile = Profile(
        username="alice" if role is UserRole.USER else "admin",
        display_name="Alice Validator" if role is UserRole.USER else "Local Admin",
    )
    return user


def _set_route_context(state: AuthState, path: str) -> None:
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


@contextmanager
def _fake_session_scope():
    yield object()


def test_submit_login_persists_cookie_and_uses_post_login_redirect(monkeypatch) -> None:
    state = AuthState(_reflex_internal_init=True)
    _set_route_context(state, "/login")
    state.post_login_path = "/browse"

    def _fake_login_user(*, session, email: str, password: str):
        assert session is not None
        assert email == "alice@example.com"
        assert password == "correct horse battery staple"
        return AuthenticatedSession(
            session_token="new-session-token",
            expires_at=datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc),
            user=_build_user(),
        )

    monkeypatch.setattr("contracting_hub.states.auth.session_scope", _fake_session_scope)
    monkeypatch.setattr("contracting_hub.states.auth.login_user", _fake_login_user)
    monkeypatch.setattr(AuthState, "_resolve_user_from_cookie", lambda self: _build_user())

    event = state.submit_login(
        {
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        }
    )

    assert state.auth_session_token == "new-session-token"
    assert state.current_user_id == 42
    assert state.current_username == "alice"
    assert state.post_login_path == ""
    assert _redirect_path(event) == "/browse"


def test_submit_registration_maps_field_level_service_errors(monkeypatch) -> None:
    state = AuthState(_reflex_internal_init=True)
    _set_route_context(state, "/register")

    def _fake_register_user(**_kwargs):
        raise AuthServiceError(
            AuthServiceErrorCode.DUPLICATE_USERNAME,
            "This username is already in use.",
            field="username",
        )

    monkeypatch.setattr("contracting_hub.states.auth.session_scope", _fake_session_scope)
    monkeypatch.setattr("contracting_hub.states.auth.register_user", _fake_register_user)

    event = state.submit_registration(
        {
            "email": "alice@example.com",
            "username": "alice",
            "password": "correct horse battery staple",
        }
    )

    assert event is None
    assert state.auth_session_token == ""
    assert state.register_username_error == "This username is already in use."
    assert state.register_email_error == ""
    assert state.register_password_error == ""


def test_logout_current_user_clears_state_and_stays_on_public_route(monkeypatch) -> None:
    state = AuthState(_reflex_internal_init=True)
    _set_route_context(state, "/browse")
    state.auth_session_token = "valid-session-token"
    state._apply_user_snapshot(_build_user())

    captured: dict[str, str] = {}

    def _fake_logout_user(*, session, session_token: str | None) -> bool:
        assert session is not None
        captured["session_token"] = session_token or ""
        return True

    monkeypatch.setattr("contracting_hub.states.auth.session_scope", _fake_session_scope)
    monkeypatch.setattr("contracting_hub.states.auth.logout_user", _fake_logout_user)

    event = state.logout_current_user()

    assert captured == {"session_token": "valid-session-token"}
    assert state.auth_session_token == ""
    assert state.current_user_id is None
    assert state.current_username is None
    assert _redirect_path(event) == "/browse"
