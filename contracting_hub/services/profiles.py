"""Profile editing services for developer-facing account data."""

from __future__ import annotations

from enum import StrEnum
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from contracting_hub.config import AppSettings
from contracting_hub.integrations.storage import LocalFileStorage, UploadValidationError
from contracting_hub.models import Profile
from contracting_hub.repositories import AuthRepository
from contracting_hub.services.auth import AuthServiceError, AuthServiceErrorCode, normalize_username
from contracting_hub.services.uploads import delete_managed_upload, store_avatar_upload

MAX_PROFILE_DISPLAY_NAME_LENGTH = 100
MAX_PROFILE_BIO_LENGTH = 1000
MAX_PROFILE_URL_LENGTH = 500
ALLOWED_PROFILE_URL_SCHEMES = frozenset({"http", "https"})


class ProfileServiceErrorCode(StrEnum):
    """Stable profile-service failures exposed to callers."""

    DUPLICATE_USERNAME = "duplicate_username"
    INVALID_AVATAR = "invalid_avatar"
    INVALID_BIO = "invalid_bio"
    INVALID_DISPLAY_NAME = "invalid_display_name"
    INVALID_URL = "invalid_url"
    INVALID_USERNAME = "invalid_username"
    PROFILE_NOT_FOUND = "profile_not_found"
    USER_NOT_FOUND = "user_not_found"


class ProfileServiceError(ValueError):
    """Structured service error for profile management workflows."""

    def __init__(
        self,
        code: ProfileServiceErrorCode,
        message: str,
        *,
        field: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.details = details or {}

    def as_payload(self) -> dict[str, object]:
        """Serialize the service failure for UI or API responses."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


def update_profile(
    *,
    session: Session,
    user_id: int,
    username: str,
    display_name: str | None = None,
    bio: str | None = None,
    website_url: str | None = None,
    github_url: str | None = None,
    xian_profile_url: str | None = None,
) -> Profile:
    """Create or update the editable public profile for the given user."""
    repository = AuthRepository(session)
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise ProfileServiceError(
            ProfileServiceErrorCode.USER_NOT_FOUND,
            f"User {user_id!r} does not exist.",
            field="user_id",
            details={"user_id": user_id},
        )

    normalized_username = _normalize_profile_username(username)
    existing_profile = repository.get_profile_by_username(normalized_username)
    if existing_profile is not None and existing_profile.user_id != user.id:
        raise ProfileServiceError(
            ProfileServiceErrorCode.DUPLICATE_USERNAME,
            "This username is already in use.",
            field="username",
            details={"username": normalized_username},
        )

    profile = user.profile
    if profile is None:
        profile = Profile(user_id=user.id, username=normalized_username)
        user.profile = profile

    profile.username = normalized_username
    profile.display_name = normalize_profile_display_name(display_name)
    profile.bio = normalize_profile_bio(bio)
    profile.website_url = normalize_profile_url(website_url, field="website_url")
    profile.github_url = normalize_profile_url(github_url, field="github_url")
    profile.xian_profile_url = normalize_profile_url(
        xian_profile_url,
        field="xian_profile_url",
    )

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _looks_like_duplicate_username_violation(error):
            raise ProfileServiceError(
                ProfileServiceErrorCode.DUPLICATE_USERNAME,
                "This username is already in use.",
                field="username",
                details={"username": normalized_username},
            ) from error
        raise

    session.refresh(profile)
    return profile


def replace_profile_avatar(
    *,
    session: Session,
    user_id: int,
    filename: str,
    content: bytes,
    content_type: str | None,
    settings: AppSettings | None = None,
    storage: LocalFileStorage | None = None,
) -> Profile:
    """Replace the current avatar image for an existing user profile."""
    profile = _require_existing_profile(session=session, user_id=user_id)

    try:
        stored_upload = store_avatar_upload(
            filename=filename,
            content=content,
            content_type=content_type,
            settings=settings,
            storage=storage,
        )
    except UploadValidationError as error:
        raise ProfileServiceError(
            ProfileServiceErrorCode.INVALID_AVATAR,
            str(error),
            field="avatar",
            details=error.as_payload(),
        ) from error

    previous_avatar_path = profile.avatar_path
    profile.avatar_path = stored_upload.storage_key

    try:
        session.commit()
    except Exception:
        session.rollback()
        delete_managed_upload(stored_upload.storage_key, settings=settings, storage=storage)
        raise

    session.refresh(profile)

    if previous_avatar_path and previous_avatar_path != stored_upload.storage_key:
        delete_managed_upload(previous_avatar_path, settings=settings, storage=storage)

    return profile


def remove_profile_avatar(
    *,
    session: Session,
    user_id: int,
    settings: AppSettings | None = None,
    storage: LocalFileStorage | None = None,
) -> Profile:
    """Clear the current avatar image from an existing user profile."""
    profile = _require_existing_profile(session=session, user_id=user_id)
    previous_avatar_path = profile.avatar_path
    if previous_avatar_path is None:
        return profile

    profile.avatar_path = None
    session.commit()
    session.refresh(profile)
    delete_managed_upload(previous_avatar_path, settings=settings, storage=storage)
    return profile


def normalize_profile_display_name(display_name: str | None) -> str | None:
    """Trim an optional display name and enforce the stored length limit."""
    return _normalize_optional_text(
        display_name,
        field="display_name",
        code=ProfileServiceErrorCode.INVALID_DISPLAY_NAME,
        max_length=MAX_PROFILE_DISPLAY_NAME_LENGTH,
        label="Display name",
    )


def normalize_profile_bio(bio: str | None) -> str | None:
    """Trim an optional bio and enforce the stored length limit."""
    return _normalize_optional_text(
        bio,
        field="bio",
        code=ProfileServiceErrorCode.INVALID_BIO,
        max_length=MAX_PROFILE_BIO_LENGTH,
        label="Bio",
    )


def normalize_profile_url(value: str | None, *, field: str) -> str | None:
    """Trim and validate an optional external profile URL."""
    normalized_value = _normalize_optional_text(
        value,
        field=field,
        code=ProfileServiceErrorCode.INVALID_URL,
        max_length=MAX_PROFILE_URL_LENGTH,
        label="URL",
    )
    if normalized_value is None:
        return None

    parsed_url = urlparse(normalized_value)
    if parsed_url.scheme.lower() not in ALLOWED_PROFILE_URL_SCHEMES or not parsed_url.netloc:
        raise ProfileServiceError(
            ProfileServiceErrorCode.INVALID_URL,
            "URL must start with http:// or https:// and include a hostname.",
            field=field,
            details={"value": normalized_value},
        )

    return normalized_value


def _require_existing_profile(*, session: Session, user_id: int) -> Profile:
    repository = AuthRepository(session)
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise ProfileServiceError(
            ProfileServiceErrorCode.USER_NOT_FOUND,
            f"User {user_id!r} does not exist.",
            field="user_id",
            details={"user_id": user_id},
        )
    if user.profile is None:
        raise ProfileServiceError(
            ProfileServiceErrorCode.PROFILE_NOT_FOUND,
            f"User {user_id!r} does not have a profile yet.",
            field="profile",
            details={"user_id": user_id},
        )
    return user.profile


def _normalize_profile_username(username: str) -> str:
    try:
        return normalize_username(username)
    except AuthServiceError as error:
        if error.code is AuthServiceErrorCode.INVALID_USERNAME:
            raise ProfileServiceError(
                ProfileServiceErrorCode.INVALID_USERNAME,
                str(error),
                field="username",
                details=error.details,
            ) from error
        raise


def _normalize_optional_text(
    value: str | None,
    *,
    field: str,
    code: ProfileServiceErrorCode,
    max_length: int,
    label: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProfileServiceError(
            code,
            f"{label} must be a string.",
            field=field,
            details={"expected_type": "str"},
        )

    normalized_value = value.strip()
    if not normalized_value:
        return None
    if len(normalized_value) > max_length:
        raise ProfileServiceError(
            code,
            f"{label} must be {max_length} characters or fewer.",
            field=field,
            details={"max_length": max_length},
        )
    return normalized_value


def _looks_like_duplicate_username_violation(error: IntegrityError) -> bool:
    return "profiles.username" in str(error.orig).lower()


__all__ = [
    "ALLOWED_PROFILE_URL_SCHEMES",
    "MAX_PROFILE_BIO_LENGTH",
    "MAX_PROFILE_DISPLAY_NAME_LENGTH",
    "MAX_PROFILE_URL_LENGTH",
    "ProfileServiceError",
    "ProfileServiceErrorCode",
    "normalize_profile_bio",
    "normalize_profile_display_name",
    "normalize_profile_url",
    "remove_profile_avatar",
    "replace_profile_avatar",
    "update_profile",
]
