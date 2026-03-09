from __future__ import annotations

import reflex as rx
from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.models import Profile, User, UserRole, UserStatus
from contracting_hub.services.auth import RouteGuardMode, evaluate_route_guard
from contracting_hub.states import AuthState
from contracting_hub.utils.meta import HOME_ROUTE


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


def test_evaluate_route_guard_handles_public_anonymous_authenticated_and_admin_access() -> None:
    user = _build_user(role=UserRole.USER)
    admin = _build_user(role=UserRole.ADMIN)

    assert (
        evaluate_route_guard(
            mode=RouteGuardMode.PUBLIC,
            user=None,
            login_route="/login",
            home_route=HOME_ROUTE,
        ).allow
        is True
    )

    anonymous_only = evaluate_route_guard(
        mode=RouteGuardMode.ANONYMOUS_ONLY,
        user=user,
        login_route="/login",
        home_route=HOME_ROUTE,
    )
    assert anonymous_only.allow is False
    assert anonymous_only.redirect_to == HOME_ROUTE

    authenticated = evaluate_route_guard(
        mode=RouteGuardMode.AUTHENTICATED,
        user=None,
        login_route="/login",
        home_route=HOME_ROUTE,
    )
    assert authenticated.allow is False
    assert authenticated.redirect_to == "/login"
    assert authenticated.remember_requested_path is True

    assert (
        evaluate_route_guard(
            mode=RouteGuardMode.AUTHENTICATED,
            user=admin,
            login_route="/login",
            home_route=HOME_ROUTE,
        ).allow
        is True
    )

    admin_only = evaluate_route_guard(
        mode=RouteGuardMode.ADMIN,
        user=user,
        login_route="/login",
        home_route=HOME_ROUTE,
        unauthorized_route="/forbidden",
    )
    assert admin_only.allow is False
    assert admin_only.redirect_to == "/forbidden"
    assert admin_only.remember_requested_path is False


def test_auth_state_authenticated_guard_clears_stale_cookie_and_remembers_path(
    monkeypatch,
) -> None:
    state = AuthState(_reflex_internal_init=True)
    _set_route_context(state, "/settings")
    state.auth_session_token = "stale-session-token"

    monkeypatch.setattr(AuthState, "_resolve_user_from_cookie", lambda self: None)

    event = state.guard_authenticated_route()

    assert state.auth_session_token == ""
    assert state.current_user_id is None
    assert state.post_login_path == "/settings"
    assert _redirect_path(event) == HOME_ROUTE


def test_auth_state_admin_guard_redirects_standard_users_without_post_login_capture(
    monkeypatch,
) -> None:
    state = AuthState(_reflex_internal_init=True)
    _set_route_context(state, "/admin")
    state.auth_session_token = "valid-session-token"

    monkeypatch.setattr(AuthState, "_resolve_user_from_cookie", lambda self: _build_user())

    event = state.guard_admin_route()

    assert state.auth_session_token == "valid-session-token"
    assert state.current_user_id == 42
    assert state.current_user_role == UserRole.USER.value
    assert state.current_username == "alice"
    assert state.current_display_name == "Alice Validator"
    assert state.post_login_path == ""
    assert _redirect_path(event) == HOME_ROUTE
