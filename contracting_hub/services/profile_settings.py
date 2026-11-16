"""Private profile-settings snapshot helpers for authenticated pages."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from contracting_hub.repositories import AuthRepository
from contracting_hub.services.profiles import ProfileServiceError, ProfileServiceErrorCode


@dataclass(frozen=True)
class PrivateProfileSettingsSnapshot:
    """Authenticated profile-settings content loaded for one user."""

    username: str
    display_name: str | None
    bio: str | None
    avatar_path: str | None
    website_url: str | None
    github_url: str | None
    xian_profile_url: str | None


def load_private_profile_settings_snapshot(
    *,
    session: Session,
    user_id: int,
) -> PrivateProfileSettingsSnapshot:
    """Load the authenticated developer's editable profile."""
    repository = AuthRepository(session)
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise ProfileServiceError(
            ProfileServiceErrorCode.USER_NOT_FOUND,
            f"User {user_id!r} does not exist.",
            field="user_id",
            details={"user_id": user_id},
        )

    profile = user.profile
    return PrivateProfileSettingsSnapshot(
        username="" if profile is None else profile.username,
        display_name=None if profile is None else profile.display_name,
        bio=None if profile is None else profile.bio,
        avatar_path=None if profile is None else profile.avatar_path,
        website_url=None if profile is None else profile.website_url,
        github_url=None if profile is None else profile.github_url,
        xian_profile_url=None if profile is None else profile.xian_profile_url,
    )


__all__ = [
    "PrivateProfileSettingsSnapshot",
    "load_private_profile_settings_snapshot",
]
