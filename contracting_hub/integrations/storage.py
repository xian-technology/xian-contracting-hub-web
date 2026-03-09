"""Local filesystem storage and upload validation helpers."""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Callable, Protocol, Sequence
from uuid import uuid4

from contracting_hub.config import AppSettings, get_settings

IMAGE_UPLOAD_CONTENT_TYPES = frozenset({"image/gif", "image/jpeg", "image/png", "image/webp"})
IMAGE_UPLOAD_EXTENSIONS = frozenset({".gif", ".jpeg", ".jpg", ".png", ".webp"})
FILENAME_SEGMENT_PATTERN = re.compile(r"[^a-z0-9_-]+")
PATH_SEGMENT_PATTERN = re.compile(r"[^a-z0-9._-]+")


class UploadValidationErrorCode(StrEnum):
    """Stable upload validation failures exposed to services and UI state."""

    EMPTY_UPLOAD = "empty_upload"
    FILE_TOO_LARGE = "file_too_large"
    UNSUPPORTED_CONTENT_TYPE = "unsupported_content_type"
    UNSUPPORTED_EXTENSION = "unsupported_extension"
    INVALID_STORAGE_KEY = "invalid_storage_key"


class UploadValidationError(ValueError):
    """Structured upload validation error."""

    def __init__(
        self,
        code: UploadValidationErrorCode,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def as_payload(self) -> dict[str, object]:
        """Serialize the validation failure for error mapping."""
        return {
            "code": self.code.value,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class UploadConstraints:
    """Validation settings for a managed upload class."""

    max_bytes: int | None = None
    allowed_extensions: frozenset[str] = field(default_factory=frozenset)
    allowed_content_types: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_extensions",
            frozenset(extension.lower() for extension in self.allowed_extensions),
        )
        object.__setattr__(
            self,
            "allowed_content_types",
            frozenset(content_type.lower() for content_type in self.allowed_content_types),
        )


@dataclass(frozen=True, slots=True)
class UploadCandidate:
    """In-memory upload payload before validation and persistence."""

    filename: str
    content: bytes
    content_type: str | None = None

    @property
    def size_bytes(self) -> int:
        """Return the upload size in bytes."""
        return len(self.content)

    @property
    def extension(self) -> str:
        """Return the normalized original file extension when present."""
        return Path(self.filename).suffix.lower()

    @property
    def normalized_content_type(self) -> str | None:
        """Return the normalized MIME type when provided."""
        if self.content_type is None:
            return None
        return self.content_type.partition(";")[0].lower().strip()


@dataclass(frozen=True, slots=True)
class StoredUpload:
    """Stored upload metadata returned after a successful save."""

    storage_key: str
    absolute_path: Path
    original_filename: str
    content_type: str | None
    size_bytes: int


UploadValidator = Callable[[UploadCandidate, UploadConstraints], None]


def validate_not_empty(upload: UploadCandidate, _constraints: UploadConstraints) -> None:
    """Reject empty uploads early."""
    if upload.size_bytes == 0:
        raise UploadValidationError(
            UploadValidationErrorCode.EMPTY_UPLOAD,
            "Upload content cannot be empty.",
        )


def validate_max_bytes(upload: UploadCandidate, constraints: UploadConstraints) -> None:
    """Ensure the upload size stays within the configured limit."""
    if constraints.max_bytes is None or upload.size_bytes <= constraints.max_bytes:
        return

    raise UploadValidationError(
        UploadValidationErrorCode.FILE_TOO_LARGE,
        "Upload exceeds the configured size limit.",
        details={
            "max_bytes": constraints.max_bytes,
            "received_bytes": upload.size_bytes,
        },
    )


def validate_content_type(upload: UploadCandidate, constraints: UploadConstraints) -> None:
    """Ensure the upload MIME type is allowed when constrained."""
    if not constraints.allowed_content_types:
        return

    content_type = upload.normalized_content_type
    if content_type and content_type in constraints.allowed_content_types:
        return

    raise UploadValidationError(
        UploadValidationErrorCode.UNSUPPORTED_CONTENT_TYPE,
        "Upload content type is not allowed.",
        details={"allowed_content_types": sorted(constraints.allowed_content_types)},
    )


def validate_extension(upload: UploadCandidate, constraints: UploadConstraints) -> None:
    """Ensure the filename extension is allowed when constrained."""
    if not constraints.allowed_extensions:
        return

    if upload.extension in constraints.allowed_extensions:
        return

    raise UploadValidationError(
        UploadValidationErrorCode.UNSUPPORTED_EXTENSION,
        "Upload file extension is not allowed.",
        details={"allowed_extensions": sorted(constraints.allowed_extensions)},
    )


def validate_upload(
    upload: UploadCandidate,
    constraints: UploadConstraints,
    *,
    validators: Sequence[UploadValidator] = (),
) -> None:
    """Run the default and caller-supplied validation hooks for an upload."""
    for validator in (
        validate_not_empty,
        validate_max_bytes,
        validate_content_type,
        validate_extension,
        *validators,
    ):
        validator(upload, constraints)


def avatar_upload_constraints(settings: AppSettings | None = None) -> UploadConstraints:
    """Return the default validation constraints for avatar images."""
    resolved_settings = settings or get_settings()
    return UploadConstraints(
        max_bytes=resolved_settings.avatar_upload_max_bytes,
        allowed_extensions=IMAGE_UPLOAD_EXTENSIONS,
        allowed_content_types=IMAGE_UPLOAD_CONTENT_TYPES,
    )


class FileStorage(Protocol):
    """Storage adapter boundary for managed file uploads."""

    root_dir: Path

    def save(
        self,
        upload: UploadCandidate,
        *,
        subdir: str | Path = "",
        constraints: UploadConstraints | None = None,
        validators: Sequence[UploadValidator] = (),
    ) -> StoredUpload:
        """Validate and persist the given upload."""

    def delete(self, storage_key: str) -> bool:
        """Delete a previously stored upload when it exists."""


@dataclass(slots=True)
class LocalFileStorage:
    """Filesystem-backed upload storage for local development."""

    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir = self.root_dir.resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        upload: UploadCandidate,
        *,
        subdir: str | Path = "",
        constraints: UploadConstraints | None = None,
        validators: Sequence[UploadValidator] = (),
    ) -> StoredUpload:
        """Validate an upload and write it beneath the configured storage root."""
        resolved_constraints = constraints or (UploadConstraints() if validators else None)
        if resolved_constraints is not None:
            validate_upload(upload, resolved_constraints, validators=validators)

        relative_dir = _normalize_storage_subdir(subdir)
        filename = _build_storage_filename(upload)
        relative_path = (relative_dir / filename) if relative_dir != Path(".") else Path(filename)
        absolute_path = self._resolve_storage_path(relative_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(upload.content)

        return StoredUpload(
            storage_key=relative_path.as_posix(),
            absolute_path=absolute_path,
            original_filename=upload.filename,
            content_type=upload.normalized_content_type,
            size_bytes=upload.size_bytes,
        )

    def delete(self, storage_key: str) -> bool:
        """Delete a stored upload by its relative storage key."""
        absolute_path = self._resolve_storage_path(Path(storage_key))
        if not absolute_path.exists() or not absolute_path.is_file():
            return False

        absolute_path.unlink()
        return True

    def _resolve_storage_path(self, relative_path: Path) -> Path:
        candidate_path = (self.root_dir / relative_path).resolve()
        if candidate_path != self.root_dir and self.root_dir not in candidate_path.parents:
            raise UploadValidationError(
                UploadValidationErrorCode.INVALID_STORAGE_KEY,
                "Upload path escapes the configured storage root.",
            )
        return candidate_path


def _normalize_storage_subdir(subdir: str | Path) -> Path:
    if not subdir:
        return Path(".")

    raw_path = Path(subdir)
    if raw_path.is_absolute():
        raise UploadValidationError(
            UploadValidationErrorCode.INVALID_STORAGE_KEY,
            "Upload subdirectories must be relative.",
        )

    normalized_segments: list[str] = []
    for segment in raw_path.parts:
        if segment in {"", "."}:
            continue
        if segment == "..":
            raise UploadValidationError(
                UploadValidationErrorCode.INVALID_STORAGE_KEY,
                "Upload subdirectories cannot traverse parent paths.",
            )

        normalized_segments.append(_slugify_path_segment(segment))

    return Path(*normalized_segments) if normalized_segments else Path(".")


def _build_storage_filename(upload: UploadCandidate) -> str:
    stem = _slugify_filename_segment(Path(upload.filename).stem)
    suffix = upload.extension or _guess_extension(upload.normalized_content_type)
    return f"{stem}-{uuid4().hex}{suffix}"


def _guess_extension(content_type: str | None) -> str:
    if not content_type:
        return ""
    guessed_extension = mimetypes.guess_extension(content_type, strict=False)
    return guessed_extension or ""


def _slugify_filename_segment(value: str) -> str:
    normalized_value = FILENAME_SEGMENT_PATTERN.sub("-", value.lower()).strip("-")
    return normalized_value or "upload"


def _slugify_path_segment(value: str) -> str:
    normalized_value = PATH_SEGMENT_PATTERN.sub("-", value.lower()).strip("-")
    return normalized_value or "upload"


__all__ = [
    "FileStorage",
    "IMAGE_UPLOAD_CONTENT_TYPES",
    "IMAGE_UPLOAD_EXTENSIONS",
    "LocalFileStorage",
    "StoredUpload",
    "UploadCandidate",
    "UploadConstraints",
    "UploadValidationError",
    "UploadValidationErrorCode",
    "UploadValidator",
    "avatar_upload_constraints",
    "validate_content_type",
    "validate_extension",
    "validate_max_bytes",
    "validate_not_empty",
    "validate_upload",
]
