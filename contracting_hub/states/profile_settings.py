"""Authenticated state for the profile settings page."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import User
from contracting_hub.services.auth import logout_user, resolve_current_user
from contracting_hub.services.playground_targets import (
    PlaygroundTargetServiceError,
    create_playground_target,
    delete_playground_target,
    update_playground_target,
)
from contracting_hub.services.profile_settings import (
    PrivatePlaygroundTargetSnapshot,
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
PLAYGROUND_DEFAULT_NO = "no"
PLAYGROUND_DEFAULT_YES = "yes"
_SETTINGS = get_settings()


class PlaygroundTargetPayload(TypedDict):
    """Serialized playground-target content stored in state."""

    id: int
    label: str
    playground_id: str
    is_default: bool
    default_badge_label: str
    last_used_label: str


class ProfileSettingsState(rx.State):
    """Authenticated UI state for profile editing and saved playground targets."""

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
    playground_targets: list[PlaygroundTargetPayload] = []
    playground_target_count_label: str = "0 saved targets"
    playground_target_label: str = ""
    playground_target_playground_id: str = ""
    playground_target_default_choice: str = PLAYGROUND_DEFAULT_NO
    editing_playground_target_id: int | None = None
    playground_target_success_message: str = ""
    playground_target_form_error: str = ""
    playground_target_label_error: str = ""
    playground_target_playground_id_error: str = ""

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
    def has_playground_targets(self) -> bool:
        """Return whether the user has any saved playground targets."""
        return bool(self.playground_targets)

    @rx.var
    def is_editing_playground_target(self) -> bool:
        """Return whether the saved-target form is editing an existing row."""
        return self.editing_playground_target_id is not None

    @rx.var
    def playground_target_form_title(self) -> str:
        """Return the heading shown above the saved-target form."""
        return "Edit saved target" if self.is_editing_playground_target else "Add saved target"

    @rx.var
    def playground_target_submit_label(self) -> str:
        """Return the submit-button copy for the saved-target form."""
        return "Save target changes" if self.is_editing_playground_target else "Add saved target"

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
        self._clear_playground_target_feedback()
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

        self._reset_playground_target_form()
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
        self._clear_playground_target_feedback()
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

    def set_playground_target_label(self, value: str) -> None:
        """Update the saved-target label input."""
        self.playground_target_label = value

    def set_playground_target_playground_id(self, value: str) -> None:
        """Update the saved-target playground ID input."""
        self.playground_target_playground_id = value

    def set_playground_target_default_choice(self, value: str) -> None:
        """Update the saved-target default-selection input."""
        self.playground_target_default_choice = value

    def reset_playground_target_form(self) -> None:
        """Reset the saved-target form back to create mode."""
        self._reset_playground_target_form()

    def _reset_playground_target_form(self) -> None:
        self.editing_playground_target_id = None
        self.playground_target_label = ""
        self.playground_target_playground_id = ""
        self.playground_target_default_choice = (
            PLAYGROUND_DEFAULT_NO if self.has_playground_targets else PLAYGROUND_DEFAULT_YES
        )
        self._clear_playground_target_feedback()

    def edit_playground_target(self, target_id: int) -> None:
        """Populate the saved-target form with an existing target row."""
        target = next(
            (candidate for candidate in self.playground_targets if candidate["id"] == target_id),
            None,
        )
        if target is None:
            self.playground_target_form_error = "Saved playground target not found."
            return

        self._clear_playground_target_feedback()
        self.editing_playground_target_id = target_id
        self.playground_target_label = target["label"]
        self.playground_target_playground_id = target["playground_id"]
        self.playground_target_default_choice = (
            PLAYGROUND_DEFAULT_YES if target["is_default"] else PLAYGROUND_DEFAULT_NO
        )

    def submit_playground_target(self, form_data: dict[str, Any]) -> None:
        """Create or update one saved playground target for the current user."""
        self._clear_playground_target_feedback()
        user_id = self.current_user_id
        if user_id is None:
            self.playground_target_form_error = (
                "Authentication is required to manage saved playground targets."
            )
            return

        label = str(form_data.get("label", ""))
        playground_id = str(form_data.get("playground_id", ""))
        is_default = (
            str(form_data.get("is_default", PLAYGROUND_DEFAULT_NO)).strip().lower()
            == PLAYGROUND_DEFAULT_YES
        )

        try:
            with session_scope() as session:
                if self.editing_playground_target_id is None:
                    create_playground_target(
                        session=session,
                        user_id=user_id,
                        label=label,
                        playground_id=playground_id,
                        is_default=is_default,
                    )
                    success_message = "Saved playground target added."
                else:
                    update_playground_target(
                        session=session,
                        user_id=user_id,
                        target_id=self.editing_playground_target_id,
                        label=label,
                        playground_id=playground_id,
                        is_default=is_default,
                    )
                    success_message = "Saved playground target updated."
                snapshot = load_private_profile_settings_snapshot(session=session, user_id=user_id)
        except PlaygroundTargetServiceError as error:
            self._apply_playground_target_error(error)
            return

        self._apply_snapshot(snapshot)
        self._reset_playground_target_form()
        self.playground_target_success_message = success_message

    def delete_playground_target(self, target_id: int) -> None:
        """Delete one saved playground target from the current user's list."""
        self._clear_playground_target_feedback()
        user_id = self.current_user_id
        if user_id is None:
            self.playground_target_form_error = (
                "Authentication is required to manage saved playground targets."
            )
            return

        try:
            with session_scope() as session:
                delete_playground_target(session=session, user_id=user_id, target_id=target_id)
                snapshot = load_private_profile_settings_snapshot(session=session, user_id=user_id)
        except PlaygroundTargetServiceError as error:
            self._apply_playground_target_error(error)
            return

        self._apply_snapshot(snapshot)
        if self.editing_playground_target_id == target_id:
            self._reset_playground_target_form()
        self.playground_target_success_message = "Saved playground target removed."

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
        self.playground_targets = [
            _serialize_playground_target(target) for target in snapshot.playground_targets
        ]
        self.playground_target_count_label = _format_target_count_label(
            len(self.playground_targets)
        )

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

    def _apply_playground_target_error(self, error: PlaygroundTargetServiceError) -> None:
        if error.field == "label":
            self.playground_target_label_error = str(error)
            return
        if error.field == "playground_id":
            self.playground_target_playground_id_error = str(error)
            return
        self.playground_target_form_error = str(error)

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

    def _clear_playground_target_feedback(self) -> None:
        self.playground_target_success_message = ""
        self.playground_target_form_error = ""
        self.playground_target_label_error = ""
        self.playground_target_playground_id_error = ""


def _serialize_playground_target(
    target: PrivatePlaygroundTargetSnapshot,
) -> PlaygroundTargetPayload:
    return {
        "id": target.id,
        "label": target.label,
        "playground_id": target.playground_id,
        "is_default": target.is_default,
        "default_badge_label": "Default" if target.is_default else "",
        "last_used_label": _format_last_used_label(target.last_used_at),
    }


def _format_last_used_label(value) -> str:
    if value is None:
        return "Never used"
    return value.strftime("%b %d, %Y").replace(" 0", " ")


def _format_target_count_label(count: int) -> str:
    return "1 saved target" if count == 1 else f"{count} saved targets"


def _format_upload_limit(max_bytes: int) -> str:
    megabytes = max_bytes / (1024 * 1024)
    if megabytes.is_integer():
        return f"{int(megabytes)} MB"
    return f"{megabytes:.1f} MB"


__all__ = [
    "PLAYGROUND_DEFAULT_NO",
    "PLAYGROUND_DEFAULT_YES",
    "PROFILE_AVATAR_UPLOAD_ID",
    "PlaygroundTargetPayload",
    "ProfileSettingsState",
]
