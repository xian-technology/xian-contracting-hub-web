"""Authenticated state for the profile settings page."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import User
from contracting_hub.services.auth import logout_user, resolve_current_user
from contracting_hub.services.profile_settings import (
    PrivateProfileSettingsSnapshot,
    load_private_profile_settings_snapshot,
)
from contracting_hub.services.profiles import (
    ProfileServiceError,
    remove_profile_avatar,
    replace_profile_avatar,
    update_profile,
)
from contracting_hub.states.auth import AUTH_SESSION_COOKIE_NAME
from contracting_hub.utils.meta import HOME_ROUTE

PROFILE_AVATAR_UPLOAD_ID = "profile-avatar-upload"
_SETTINGS = get_settings()


class ProfileSettingsState(rx.State):
    """Authenticated UI state for profile editing."""

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
    load_error_message: str = ""
    profile_username: str = ""
    profile_display_name: str = ""
    profile_bio: str = ""
    profile_website_url: str = ""
    profile_github_url: str = ""
    profile_xian_profile_url: str = ""
    profile_success_message: str = ""
    profile_form_error: str = ""
    profile_username_error: str = ""
    profile_display_name_error: str = ""
    profile_bio_error: str = ""
    profile_website_url_error: str = ""
    profile_github_url_error: str = ""
    profile_xian_profile_url_error: str = ""
    avatar_storage_key: str = ""
    avatar_success_message: str = ""
    avatar_error_message: str = ""

    @rx.var
    def is_authenticated(self) -> bool:
        """Return whether the current browser has an active user session."""
        return self.current_user_id is not None

    @rx.var
    def is_loading(self) -> bool:
        """Return whether the settings route is still loading the private snapshot."""
        return self.load_state == "loading"

    @rx.var
    def has_load_error(self) -> bool:
        """Return whether the settings route failed to load."""
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
    def has_avatar(self) -> bool:
        """Return whether the current profile has a stored avatar."""
        return bool(self.avatar_storage_key)

    @rx.var
    def avatar_filename_label(self) -> str:
        """Return the current stored avatar filename."""
        if not self.avatar_storage_key:
            return "No avatar on file"
        return Path(self.avatar_storage_key).name

    @rx.var
    def avatar_fallback(self) -> str:
        """Return initials used by the avatar placeholder."""
        source = (
            self.profile_display_name or self.profile_username or self.current_user_email or "UH"
        )
        letters = [part[0] for part in source.replace("@", " ").replace("_", " ").split() if part]
        if not letters:
            return "UH"
        return "".join(letters[:2]).upper()

    @rx.var
    def avatar_status_label(self) -> str:
        """Return the current avatar-management summary line."""
        return "Avatar on file" if self.has_avatar else "No avatar uploaded yet"

    @rx.var
    def avatar_upload_help_text(self) -> str:
        """Return the current avatar upload constraints in human-readable form."""
        return (
            "PNG, JPG, GIF, or WebP up to "
            f"{_format_upload_limit(_SETTINGS.avatar_upload_max_bytes)}. "
            "Selecting a file uploads it immediately."
        )

    def load_page(self) -> rx.event.EventSpec | None:
        """Load the authenticated profile snapshot after the parent auth guard runs."""
        self.load_state = "loading"
        self.load_error_message = ""
        self._clear_profile_feedback()
        self._clear_avatar_feedback()
        self._apply_user_snapshot(self._resolve_user_from_cookie())
        if self.current_user_id is None:
            self.load_error_message = "Authentication is required to manage profile settings."
            self.load_state = "error"
            return None

        try:
            self._load_snapshot()
        except ProfileServiceError as error:
            self.load_error_message = str(error)
            self.load_state = "error"
            return None
        except Exception as error:
            self.load_error_message = str(error)
            self.load_state = "error"
            return None

        self.load_state = "ready"
        return None

    def logout_current_user(self) -> rx.event.EventSpec:
        """Invalidate the current cookie-backed session from the settings page shell."""
        if self.auth_session_token:
            with session_scope() as session:
                logout_user(
                    session=session,
                    session_token=self.auth_session_token,
                )

        self.auth_session_token = ""
        self._apply_user_snapshot(None)
        self._clear_profile_feedback()
        self._clear_avatar_feedback()
        return rx.redirect(HOME_ROUTE, replace=True)

    def set_profile_username(self, value: str) -> None:
        """Update the current username input."""
        self.profile_username = value

    def set_profile_display_name(self, value: str) -> None:
        """Update the current display-name input."""
        self.profile_display_name = value

    def set_profile_bio(self, value: str) -> None:
        """Update the current bio input."""
        self.profile_bio = value

    def set_profile_website_url(self, value: str) -> None:
        """Update the current website URL input."""
        self.profile_website_url = value

    def set_profile_github_url(self, value: str) -> None:
        """Update the current GitHub URL input."""
        self.profile_github_url = value

    def set_profile_xian_profile_url(self, value: str) -> None:
        """Update the current Xian profile URL input."""
        self.profile_xian_profile_url = value

    def submit_profile(self, form_data: dict[str, Any]) -> None:
        """Persist the editable public profile fields for the current user."""
        self._clear_profile_feedback()
        user_id = self.current_user_id
        if user_id is None:
            self.profile_form_error = "Authentication is required to update your profile."
            return

        try:
            with session_scope() as session:
                update_profile(
                    session=session,
                    user_id=user_id,
                    username=str(form_data.get("username", "")),
                    display_name=str(form_data.get("display_name", "")).strip() or None,
                    bio=str(form_data.get("bio", "")).strip() or None,
                    website_url=str(form_data.get("website_url", "")).strip() or None,
                    github_url=str(form_data.get("github_url", "")).strip() or None,
                    xian_profile_url=str(form_data.get("xian_profile_url", "")).strip() or None,
                )
                snapshot = load_private_profile_settings_snapshot(session=session, user_id=user_id)
        except ProfileServiceError as error:
            self._apply_profile_error(error)
            return

        self._apply_snapshot(snapshot)
        self.current_username = snapshot.username or None
        self.current_display_name = snapshot.display_name
        self.profile_success_message = "Profile updated."

    def upload_avatar(self, files: list[rx.UploadFile]) -> rx.event.EventSpec:
        """Replace the current avatar image using the first uploaded file."""
        self._clear_avatar_feedback()
        user_id = self.current_user_id
        if user_id is None:
            self.avatar_error_message = "Authentication is required to update your avatar."
            return rx.clear_selected_files(PROFILE_AVATAR_UPLOAD_ID)

        if not files:
            self.avatar_error_message = "Choose an avatar image to upload."
            return rx.clear_selected_files(PROFILE_AVATAR_UPLOAD_ID)

        uploaded_file = files[0]
        file_name = uploaded_file.filename or uploaded_file.name or "avatar-upload"
        file_bytes = uploaded_file.file.read()
        content_type = getattr(uploaded_file, "content_type", None)

        try:
            with session_scope() as session:
                replace_profile_avatar(
                    session=session,
                    user_id=user_id,
                    filename=file_name,
                    content=file_bytes,
                    content_type=content_type,
                )
                snapshot = load_private_profile_settings_snapshot(session=session, user_id=user_id)
        except ProfileServiceError as error:
            self.avatar_error_message = str(error)
            return rx.clear_selected_files(PROFILE_AVATAR_UPLOAD_ID)

        self._apply_snapshot(snapshot)
        self.avatar_success_message = "Avatar updated."
        return rx.clear_selected_files(PROFILE_AVATAR_UPLOAD_ID)

    def remove_avatar(self) -> None:
        """Remove the currently stored avatar file."""
        self._clear_avatar_feedback()
        user_id = self.current_user_id
        if user_id is None:
            self.avatar_error_message = "Authentication is required to remove your avatar."
            return
        if not self.avatar_storage_key:
            self.avatar_error_message = "No avatar is currently stored."
            return

        try:
            with session_scope() as session:
                remove_profile_avatar(session=session, user_id=user_id)
                snapshot = load_private_profile_settings_snapshot(session=session, user_id=user_id)
        except ProfileServiceError as error:
            self.avatar_error_message = str(error)
            return

        self._apply_snapshot(snapshot)
        self.avatar_success_message = "Avatar removed."

    def _load_snapshot(self) -> None:
        user_id = self.current_user_id
        if user_id is None:
            return

        with session_scope() as session:
            snapshot = load_private_profile_settings_snapshot(session=session, user_id=user_id)
        self._apply_snapshot(snapshot)

    def _resolve_user_from_cookie(self) -> User | None:
        with session_scope() as session:
            return resolve_current_user(
                session=session,
                session_token=self.auth_session_token,
            )

    def _apply_snapshot(self, snapshot: PrivateProfileSettingsSnapshot) -> None:
        self.profile_username = snapshot.username
        self.profile_display_name = snapshot.display_name or ""
        self.profile_bio = snapshot.bio or ""
        self.profile_website_url = snapshot.website_url or ""
        self.profile_github_url = snapshot.github_url or ""
        self.profile_xian_profile_url = snapshot.xian_profile_url or ""
        self.avatar_storage_key = snapshot.avatar_path or ""

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

    def _apply_profile_error(self, error: ProfileServiceError) -> None:
        if error.field == "username":
            self.profile_username_error = str(error)
            return
        if error.field == "display_name":
            self.profile_display_name_error = str(error)
            return
        if error.field == "bio":
            self.profile_bio_error = str(error)
            return
        if error.field == "website_url":
            self.profile_website_url_error = str(error)
            return
        if error.field == "github_url":
            self.profile_github_url_error = str(error)
            return
        if error.field == "xian_profile_url":
            self.profile_xian_profile_url_error = str(error)
            return
        self.profile_form_error = str(error)

    def _clear_profile_feedback(self) -> None:
        self.profile_success_message = ""
        self.profile_form_error = ""
        self.profile_username_error = ""
        self.profile_display_name_error = ""
        self.profile_bio_error = ""
        self.profile_website_url_error = ""
        self.profile_github_url_error = ""
        self.profile_xian_profile_url_error = ""

    def _clear_avatar_feedback(self) -> None:
        self.avatar_success_message = ""
        self.avatar_error_message = ""


def _format_upload_limit(max_bytes: int) -> str:
    megabytes = max_bytes / (1024 * 1024)
    if megabytes.is_integer():
        return f"{int(megabytes)} MB"
    return f"{megabytes:.1f} MB"


__all__ = [
    "PROFILE_AVATAR_UPLOAD_ID",
    "ProfileSettingsState",
]
