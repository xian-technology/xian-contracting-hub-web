"""Service helpers for saved playground target management."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from contracting_hub.models import PlaygroundTarget, UserStatus
from contracting_hub.repositories import PlaygroundTargetRepository

MIN_PLAYGROUND_ID_LENGTH = 3
MAX_PLAYGROUND_ID_LENGTH = 128
MAX_PLAYGROUND_TARGET_LABEL_LENGTH = 100
PLAYGROUND_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class PlaygroundTargetDeletionResult:
    """Deletion outcome returned after one saved playground target is removed."""

    deleted_target_id: int
    promoted_default_target_id: int | None


class PlaygroundTargetServiceErrorCode(StrEnum):
    """Stable playground-target failures exposed to callers."""

    DUPLICATE_PLAYGROUND_ID = "duplicate_playground_id"
    INVALID_LABEL = "invalid_label"
    INVALID_PLAYGROUND_ID = "invalid_playground_id"
    PLAYGROUND_TARGET_NOT_FOUND = "playground_target_not_found"
    USER_DISABLED = "user_disabled"
    USER_NOT_FOUND = "user_not_found"


class PlaygroundTargetServiceError(ValueError):
    """Structured service error for saved playground target workflows."""

    def __init__(
        self,
        code: PlaygroundTargetServiceErrorCode,
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


def list_playground_targets(
    *,
    session: Session,
    user_id: int,
) -> list[PlaygroundTarget]:
    """Return the current user's saved playground targets."""
    repository = PlaygroundTargetRepository(session)
    user = _require_active_user(repository=repository, user_id=user_id)
    persisted_user_id = _require_persisted_id(user.id, label="user")
    return repository.list_targets_for_user(user_id=persisted_user_id)


def create_playground_target(
    *,
    session: Session,
    user_id: int,
    label: str,
    playground_id: str,
    is_default: bool = False,
) -> PlaygroundTarget:
    """Create one saved playground target for the authenticated developer."""
    repository = PlaygroundTargetRepository(session)
    user = _require_active_user(repository=repository, user_id=user_id)
    persisted_user_id = _require_persisted_id(user.id, label="user")
    normalized_label = normalize_playground_target_label(label)
    normalized_playground_id = normalize_saved_playground_id(playground_id)

    if (
        repository.get_target_by_playground_id(
            user_id=persisted_user_id,
            playground_id=normalized_playground_id,
        )
        is not None
    ):
        raise _duplicate_playground_id_error(normalized_playground_id)

    existing_targets = repository.list_targets_for_user(user_id=persisted_user_id)
    target = PlaygroundTarget(
        user_id=persisted_user_id,
        label=normalized_label,
        playground_id=normalized_playground_id,
    )
    _apply_default_selection(
        target=target,
        other_targets=existing_targets,
        requested_default=is_default,
    )

    try:
        repository.add_target(target)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _looks_like_duplicate_target_violation(error):
            raise _duplicate_playground_id_error(normalized_playground_id) from error
        raise

    session.refresh(target)
    return target


def update_playground_target(
    *,
    session: Session,
    user_id: int,
    target_id: int,
    label: str,
    playground_id: str,
    is_default: bool | None = None,
) -> PlaygroundTarget:
    """Update the saved label, identifier, or default flag for one target."""
    repository = PlaygroundTargetRepository(session)
    user = _require_active_user(repository=repository, user_id=user_id)
    persisted_user_id = _require_persisted_id(user.id, label="user")
    target = _require_existing_target(
        repository=repository,
        user_id=persisted_user_id,
        target_id=target_id,
    )
    persisted_target_id = _require_persisted_id(target.id, label="playground target")
    normalized_label = normalize_playground_target_label(label)
    normalized_playground_id = normalize_saved_playground_id(playground_id)

    existing_target = repository.get_target_by_playground_id(
        user_id=persisted_user_id,
        playground_id=normalized_playground_id,
    )
    if existing_target is not None and existing_target.id != persisted_target_id:
        raise _duplicate_playground_id_error(normalized_playground_id)

    other_targets = [
        candidate
        for candidate in repository.list_targets_for_user(user_id=persisted_user_id)
        if candidate.id != persisted_target_id
    ]
    target.label = normalized_label
    target.playground_id = normalized_playground_id
    _apply_default_selection(
        target=target,
        other_targets=other_targets,
        requested_default=is_default,
    )

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _looks_like_duplicate_target_violation(error):
            raise _duplicate_playground_id_error(normalized_playground_id) from error
        raise

    session.refresh(target)
    return target


def delete_playground_target(
    *,
    session: Session,
    user_id: int,
    target_id: int,
) -> PlaygroundTargetDeletionResult:
    """Delete one saved playground target for the authenticated developer."""
    repository = PlaygroundTargetRepository(session)
    user = _require_active_user(repository=repository, user_id=user_id)
    persisted_user_id = _require_persisted_id(user.id, label="user")
    target = _require_existing_target(
        repository=repository,
        user_id=persisted_user_id,
        target_id=target_id,
    )
    persisted_target_id = _require_persisted_id(target.id, label="playground target")
    other_targets = [
        candidate
        for candidate in repository.list_targets_for_user(user_id=persisted_user_id)
        if candidate.id != persisted_target_id
    ]
    repository.delete_target(target)

    promoted_default_target = None
    if target.is_default:
        promoted_default_target = _promote_default_target(other_targets)

    session.commit()
    return PlaygroundTargetDeletionResult(
        deleted_target_id=persisted_target_id,
        promoted_default_target_id=(
            None
            if promoted_default_target is None
            else _require_persisted_id(
                promoted_default_target.id,
                label="playground target",
            )
        ),
    )


def normalize_playground_target_label(label: str) -> str:
    """Trim and validate a saved playground target label."""
    if not isinstance(label, str):
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.INVALID_LABEL,
            "Playground target label must be a string.",
            field="label",
            details={"expected_type": "str"},
        )

    normalized_label = label.strip()
    if not normalized_label:
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.INVALID_LABEL,
            "Playground target label is required.",
            field="label",
        )
    if len(normalized_label) > MAX_PLAYGROUND_TARGET_LABEL_LENGTH:
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.INVALID_LABEL,
            f"Playground target label must be {MAX_PLAYGROUND_TARGET_LABEL_LENGTH} "
            "characters or fewer.",
            field="label",
            details={"max_length": MAX_PLAYGROUND_TARGET_LABEL_LENGTH},
        )
    return normalized_label


def normalize_saved_playground_id(playground_id: str) -> str:
    """Trim and validate a saved playground identifier."""
    if not isinstance(playground_id, str):
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.INVALID_PLAYGROUND_ID,
            "Playground ID must be a string.",
            field="playground_id",
            details={"expected_type": "str"},
        )

    normalized_playground_id = playground_id.strip()
    if not normalized_playground_id:
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.INVALID_PLAYGROUND_ID,
            "Playground ID is required.",
            field="playground_id",
        )

    if not MIN_PLAYGROUND_ID_LENGTH <= len(normalized_playground_id) <= MAX_PLAYGROUND_ID_LENGTH:
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.INVALID_PLAYGROUND_ID,
            "Playground ID must be between 3 and 128 characters long.",
            field="playground_id",
            details={
                "min_length": MIN_PLAYGROUND_ID_LENGTH,
                "max_length": MAX_PLAYGROUND_ID_LENGTH,
            },
        )

    if not PLAYGROUND_ID_PATTERN.fullmatch(normalized_playground_id):
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.INVALID_PLAYGROUND_ID,
            "Playground ID must start with a letter or number and may only contain "
            "letters, numbers, periods, underscores, and hyphens.",
            field="playground_id",
            details={"value": normalized_playground_id},
        )

    return normalized_playground_id


def _require_active_user(
    *,
    repository: PlaygroundTargetRepository,
    user_id: int,
):
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.USER_NOT_FOUND,
            f"User {user_id!r} does not exist.",
            field="user_id",
            details={"user_id": user_id},
        )
    if user.status is not UserStatus.ACTIVE:
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.USER_DISABLED,
            "Only active users can manage saved playground targets.",
            field="user_id",
            details={"user_id": user_id, "status": user.status.value},
        )
    return user


def _require_existing_target(
    *,
    repository: PlaygroundTargetRepository,
    user_id: int,
    target_id: int,
) -> PlaygroundTarget:
    target = repository.get_target_by_id(user_id=user_id, target_id=target_id)
    if target is None:
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.PLAYGROUND_TARGET_NOT_FOUND,
            f"Saved playground target {target_id!r} does not exist.",
            field="target_id",
            details={"target_id": target_id},
        )
    return target


def _duplicate_playground_id_error(playground_id: str) -> PlaygroundTargetServiceError:
    return PlaygroundTargetServiceError(
        PlaygroundTargetServiceErrorCode.DUPLICATE_PLAYGROUND_ID,
        "This playground ID is already saved to your account.",
        field="playground_id",
        details={"playground_id": playground_id},
    )


def _apply_default_selection(
    *,
    target: PlaygroundTarget,
    other_targets: list[PlaygroundTarget],
    requested_default: bool | None,
) -> None:
    if requested_default is True:
        _set_exclusive_default(target=target, other_targets=other_targets)
        return

    if requested_default is False:
        promoted_target = _promote_default_target(other_targets)
        if promoted_target is None:
            target.is_default = True
        else:
            target.is_default = False
        return

    if target.is_default:
        _set_exclusive_default(target=target, other_targets=other_targets)
        return

    if any(candidate.is_default for candidate in other_targets):
        target.is_default = False
        return

    target.is_default = True


def _set_exclusive_default(
    *,
    target: PlaygroundTarget,
    other_targets: list[PlaygroundTarget],
) -> None:
    target.is_default = True
    for candidate in other_targets:
        candidate.is_default = False


def _promote_default_target(other_targets: list[PlaygroundTarget]) -> PlaygroundTarget | None:
    if not other_targets:
        return None

    promoted_target = next(
        (candidate for candidate in other_targets if candidate.is_default),
        other_targets[0],
    )
    for candidate in other_targets:
        candidate.is_default = candidate is promoted_target
    return promoted_target


def _looks_like_duplicate_target_violation(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return "uq_playground_targets_user_playground_id" in message or (
        "playground_targets.user_id, playground_targets.playground_id" in message
    )


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is None:
        raise RuntimeError(f"{label} must be persisted before playground target workflows run.")
    return value


__all__ = [
    "MAX_PLAYGROUND_ID_LENGTH",
    "MAX_PLAYGROUND_TARGET_LABEL_LENGTH",
    "MIN_PLAYGROUND_ID_LENGTH",
    "PLAYGROUND_ID_PATTERN",
    "PlaygroundTargetDeletionResult",
    "PlaygroundTargetServiceError",
    "PlaygroundTargetServiceErrorCode",
    "create_playground_target",
    "delete_playground_target",
    "list_playground_targets",
    "normalize_playground_target_label",
    "normalize_saved_playground_id",
    "update_playground_target",
]
