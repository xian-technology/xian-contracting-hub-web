"""Service helpers for managed local uploads."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from contracting_hub.config import AppSettings, get_settings
from contracting_hub.integrations.storage import (
    LocalFileStorage,
    StoredUpload,
    UploadCandidate,
    UploadConstraints,
    UploadValidator,
    avatar_upload_constraints,
)

AVATAR_UPLOAD_SUBDIR = Path("avatars")


def get_upload_storage(settings: AppSettings | None = None) -> LocalFileStorage:
    """Return the default local upload storage adapter."""
    resolved_settings = settings or get_settings()
    return LocalFileStorage(root_dir=resolved_settings.uploads_dir)


def build_avatar_upload_constraints(settings: AppSettings | None = None) -> UploadConstraints:
    """Return avatar-specific upload validation settings."""
    resolved_settings = settings or get_settings()
    return avatar_upload_constraints(resolved_settings)


def build_managed_upload_constraints(
    settings: AppSettings | None = None,
    *,
    allowed_extensions: frozenset[str] | None = None,
    allowed_content_types: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> UploadConstraints:
    """Return generic upload validation settings for non-avatar assets."""
    resolved_settings = settings or get_settings()
    return UploadConstraints(
        max_bytes=(
            max_bytes if max_bytes is not None else resolved_settings.managed_upload_max_bytes
        ),
        allowed_extensions=allowed_extensions or frozenset(),
        allowed_content_types=allowed_content_types or frozenset(),
    )


def store_avatar_upload(
    *,
    filename: str,
    content: bytes,
    content_type: str | None,
    settings: AppSettings | None = None,
    validators: Sequence[UploadValidator] = (),
    storage: LocalFileStorage | None = None,
) -> StoredUpload:
    """Persist an avatar upload using the configured local storage adapter."""
    resolved_settings = settings or get_settings()
    resolved_storage = storage or get_upload_storage(resolved_settings)
    upload = UploadCandidate(filename=filename, content=content, content_type=content_type)
    avatar_subdir = resolved_settings.avatar_upload_dir.relative_to(resolved_settings.uploads_dir)
    return resolved_storage.save(
        upload,
        subdir=avatar_subdir,
        constraints=build_avatar_upload_constraints(resolved_settings),
        validators=validators,
    )


def delete_managed_upload(
    storage_key: str,
    *,
    settings: AppSettings | None = None,
    storage: LocalFileStorage | None = None,
) -> bool:
    """Delete a managed upload by storage key."""
    resolved_storage = storage or get_upload_storage(settings)
    return resolved_storage.delete(storage_key)


__all__ = [
    "AVATAR_UPLOAD_SUBDIR",
    "build_avatar_upload_constraints",
    "build_managed_upload_constraints",
    "delete_managed_upload",
    "get_upload_storage",
    "store_avatar_upload",
]
