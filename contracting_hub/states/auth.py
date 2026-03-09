"""Cookie-backed auth state and reusable route guards."""

from __future__ import annotations

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import User, UserRole
from contracting_hub.services.auth import (
    RouteGuardMode,
    evaluate_route_guard,
    resolve_current_user,
)
from contracting_hub.utils.meta import HOME_ROUTE

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

    @rx.var
    def is_authenticated(self) -> bool:
        """Return whether the current browser has an active user session."""
        return self.current_user_id is not None

    @rx.var
    def is_admin(self) -> bool:
        """Return whether the current browser is authenticated as an admin."""
        return self.current_user_role == UserRole.ADMIN.value

    def sync_auth_state(self) -> None:
        """Refresh the current-user snapshot from the cookie-backed session."""
        self._apply_user_snapshot(self._resolve_user_from_cookie())

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

    def _guard_route(self, mode: RouteGuardMode) -> rx.event.EventSpec | None:
        user = self._resolve_user_from_cookie()
        self._apply_user_snapshot(user)
        decision = evaluate_route_guard(
            mode=mode,
            user=user,
            login_route=HOME_ROUTE,
            home_route=HOME_ROUTE,
        )
        if decision.allow or decision.redirect_to is None:
            return None

        if decision.remember_requested_path:
            current_path = self.router.url.path or HOME_ROUTE
            if current_path != decision.redirect_to:
                self.post_login_path = current_path

        return rx.redirect(decision.redirect_to, replace=True)

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


__all__ = [
    "AUTH_SESSION_COOKIE_NAME",
    "POST_LOGIN_PATH_STORAGE_KEY",
    "AuthState",
]
