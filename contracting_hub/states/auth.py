"""Cookie-backed auth state and reusable route guards."""

from __future__ import annotations

from typing import Any

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import User, UserRole
from contracting_hub.services.auth import (
    AuthServiceError,
    RouteGuardMode,
    evaluate_route_guard,
    login_user,
    logout_user,
    register_user,
    resolve_current_user,
)
from contracting_hub.utils.meta import HOME_ROUTE, LOGIN_ROUTE, REGISTER_ROUTE

AUTH_SESSION_COOKIE_NAME = "contracting_hub_session"
POST_LOGIN_PATH_STORAGE_KEY = "contracting_hub_post_login_path"

_SETTINGS = get_settings()


class AuthState(rx.State):
    """Shared auth/session state for protected routes and actions."""

    auth_session_token: str = rx.Cookie(
        "",
        name=AUTH_SESSION_COOKIE_NAME,
        path="/",
        same_site="lax",
        secure=_SETTINGS.environment == "production",
    )
    post_login_path: str = rx.LocalStorage("", name=POST_LOGIN_PATH_STORAGE_KEY)
    current_user_id: int | None = None
    current_user_email: str | None = None
    current_user_role: str | None = None
    current_username: str | None = None
    current_display_name: str | None = None
    login_email_error: str = ""
    login_password_error: str = ""
    login_form_error: str = ""
    register_email_error: str = ""
    register_username_error: str = ""
    register_password_error: str = ""
    register_form_error: str = ""

    @rx.var
    def is_authenticated(self) -> bool:
        """Return whether the current browser has an active user session."""
        return self.current_user_id is not None

    @rx.var
    def is_admin(self) -> bool:
        """Return whether the current browser is authenticated as an admin."""
        return self.current_user_role == UserRole.ADMIN.value

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

    def sync_auth_state(self) -> None:
        """Refresh the current-user snapshot from the cookie-backed session."""
        self._apply_user_snapshot(self._resolve_user_from_cookie())

    def load_login_page(self) -> rx.event.EventSpec | None:
        """Prepare the login screen and redirect authenticated users away from it."""
        self._clear_login_feedback()
        return self.guard_anonymous_route()

    def load_registration_page(self) -> rx.event.EventSpec | None:
        """Prepare the registration screen and redirect authenticated users away from it."""
        self._clear_registration_feedback()
        return self.guard_anonymous_route()

    def guard_anonymous_route(self) -> rx.event.EventSpec | None:
        """Redirect authenticated users away from anonymous-only routes."""
        return self._guard_route(RouteGuardMode.ANONYMOUS_ONLY)

    def guard_authenticated_route(self) -> rx.event.EventSpec | None:
        """Redirect anonymous visitors away from authenticated routes."""
        return self._guard_route(RouteGuardMode.AUTHENTICATED)

    def guard_admin_route(self) -> rx.event.EventSpec | None:
        """Redirect non-admin viewers away from admin routes."""
        return self._guard_route(RouteGuardMode.ADMIN)

    def clear_post_login_path(self) -> None:
        """Drop any remembered redirect path after a successful auth flow."""
        self.post_login_path = ""

    def submit_login(self, form_data: dict[str, Any]) -> rx.event.EventSpec | None:
        """Authenticate the submitted credentials and persist the session cookie."""
        self._clear_login_feedback()

        try:
            with session_scope() as session:
                authenticated_session = login_user(
                    session=session,
                    email=str(form_data.get("email", "")),
                    password=str(form_data.get("password", "")),
                )
        except AuthServiceError as error:
            self._apply_login_error(error)
            return None

        self.auth_session_token = authenticated_session.session_token
        self.sync_auth_state()
        redirect_to = self._resolve_post_auth_redirect()
        self.clear_post_login_path()
        return rx.redirect(redirect_to, replace=True)

    def submit_registration(self, form_data: dict[str, Any]) -> rx.event.EventSpec | None:
        """Create a new user account, then authenticate it immediately."""
        self._clear_registration_feedback()
        email = str(form_data.get("email", ""))
        password = str(form_data.get("password", ""))

        try:
            with session_scope() as session:
                register_user(
                    session=session,
                    email=email,
                    username=str(form_data.get("username", "")),
                    password=password,
                    display_name=str(form_data.get("display_name", "")).strip() or None,
                )
                authenticated_session = login_user(
                    session=session,
                    email=email,
                    password=password,
                )
        except AuthServiceError as error:
            self._apply_registration_error(error)
            return None

        self.auth_session_token = authenticated_session.session_token
        self.sync_auth_state()
        redirect_to = self._resolve_post_auth_redirect()
        self.clear_post_login_path()
        return rx.redirect(redirect_to, replace=True)

    def logout_current_user(self) -> rx.event.EventSpec:
        """Invalidate the current cookie-backed session and refresh the shell state."""
        if self.auth_session_token:
            with session_scope() as session:
                logout_user(
                    session=session,
                    session_token=self.auth_session_token,
                )

        self.auth_session_token = ""
        self._apply_user_snapshot(None)
        self.clear_post_login_path()
        self._clear_login_feedback()
        self._clear_registration_feedback()
        return rx.redirect(self._resolve_post_logout_redirect(), replace=True)

    def _guard_route(self, mode: RouteGuardMode) -> rx.event.EventSpec | None:
        user = self._resolve_user_from_cookie()
        self._apply_user_snapshot(user)
        decision = evaluate_route_guard(
            mode=mode,
            user=user,
            login_route=LOGIN_ROUTE,
            home_route=HOME_ROUTE,
        )
        if decision.allow or decision.redirect_to is None:
            return None

        if decision.remember_requested_path:
            current_path = self.router.url.path or HOME_ROUTE
            if current_path != decision.redirect_to:
                self.post_login_path = current_path

        return rx.redirect(decision.redirect_to, replace=True)

    def _apply_login_error(self, error: AuthServiceError) -> None:
        if error.field == "email":
            self.login_email_error = str(error)
            return
        if error.field == "password":
            self.login_password_error = str(error)
            return
        self.login_form_error = str(error)

    def _apply_registration_error(self, error: AuthServiceError) -> None:
        if error.field == "email":
            self.register_email_error = str(error)
            return
        if error.field == "username":
            self.register_username_error = str(error)
            return
        if error.field == "password":
            self.register_password_error = str(error)
            return
        self.register_form_error = str(error)

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
            self.current_user_role = None
            self.current_username = None
            self.current_display_name = None
            return

        self.current_user_id = user.id
        self.current_user_email = user.email
        self.current_user_role = user.role.value
        self.current_username = user.profile.username if user.profile is not None else None
        self.current_display_name = user.profile.display_name if user.profile is not None else None

    def _clear_login_feedback(self) -> None:
        self.login_email_error = ""
        self.login_password_error = ""
        self.login_form_error = ""

    def _clear_registration_feedback(self) -> None:
        self.register_email_error = ""
        self.register_username_error = ""
        self.register_password_error = ""
        self.register_form_error = ""

    def _resolve_post_auth_redirect(self) -> str:
        candidate = (self.post_login_path or "").strip()
        if not candidate or not candidate.startswith("/"):
            return HOME_ROUTE
        if candidate in {HOME_ROUTE, LOGIN_ROUTE, REGISTER_ROUTE}:
            return HOME_ROUTE
        return candidate

    def _resolve_post_logout_redirect(self) -> str:
        current_path = self.router.url.path or HOME_ROUTE
        if current_path in {LOGIN_ROUTE, REGISTER_ROUTE}:
            return HOME_ROUTE
        return current_path


__all__ = [
    "AUTH_SESSION_COOKIE_NAME",
    "POST_LOGIN_PATH_STORAGE_KEY",
    "AuthState",
]
