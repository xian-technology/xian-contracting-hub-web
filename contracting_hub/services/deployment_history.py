"""Authenticated deployment-history snapshot helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlmodel import Session

from contracting_hub.models import DeploymentStatus, DeploymentTransport, User, UserStatus
from contracting_hub.repositories import DeploymentHistoryRecord, DeploymentRepository
from contracting_hub.repositories.playground_targets import PlaygroundTargetRepository

DEFAULT_PRIVATE_DEPLOYMENT_HISTORY_LIMIT = 50


@dataclass(frozen=True)
class SavedTargetShortcutSnapshot:
    """Saved playground-target content rendered as account-level shortcuts."""

    id: int
    label: str
    playground_id: str
    is_default: bool
    last_used_at: datetime | None


@dataclass(frozen=True)
class DeploymentHistoryEntrySnapshot:
    """Serialized authenticated deployment-history content."""

    deployment_id: int
    contract_slug: str
    contract_display_name: str
    contract_name: str
    semantic_version: str
    playground_id: str
    playground_target_id: int | None
    playground_target_label: str | None
    status: DeploymentStatus
    transport: DeploymentTransport | None
    redirect_url: str | None
    external_request_id: str | None
    initiated_at: datetime
    completed_at: datetime | None
    error_message: str | None


@dataclass(frozen=True)
class PrivateDeploymentHistorySnapshot:
    """Authenticated deployment history plus saved-target shortcuts."""

    deployments: tuple[DeploymentHistoryEntrySnapshot, ...]
    saved_targets: tuple[SavedTargetShortcutSnapshot, ...]


class DeploymentHistoryServiceErrorCode(StrEnum):
    """Stable snapshot-loading failures for authenticated deployment history."""

    USER_DISABLED = "user_disabled"
    USER_NOT_FOUND = "user_not_found"


class DeploymentHistoryServiceError(ValueError):
    """Structured error returned when a deployment-history snapshot cannot load."""

    def __init__(
        self,
        code: DeploymentHistoryServiceErrorCode,
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
        """Serialize the snapshot-loading failure for UI callers."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


def load_private_deployment_history_snapshot(
    *,
    session: Session,
    user_id: int,
    limit: int = DEFAULT_PRIVATE_DEPLOYMENT_HISTORY_LIMIT,
) -> PrivateDeploymentHistorySnapshot:
    """Load one authenticated user's deployment history and saved targets."""
    deployment_repository = DeploymentRepository(session)
    target_repository = PlaygroundTargetRepository(session)
    user = _require_active_user(repository=deployment_repository, user_id=user_id)
    persisted_user_id = _require_persisted_id(user.id, label="user")

    deployment_records = deployment_repository.list_history_for_user(
        user_id=persisted_user_id,
        limit=limit,
    )
    saved_targets = target_repository.list_targets_for_user(user_id=persisted_user_id)
    return PrivateDeploymentHistorySnapshot(
        deployments=tuple(_build_deployment_history_entry(record) for record in deployment_records),
        saved_targets=tuple(
            SavedTargetShortcutSnapshot(
                id=_require_persisted_id(target.id, label="saved target"),
                label=target.label,
                playground_id=target.playground_id,
                is_default=target.is_default,
                last_used_at=target.last_used_at,
            )
            for target in saved_targets
        ),
    )


def _build_deployment_history_entry(
    record: DeploymentHistoryRecord,
) -> DeploymentHistoryEntrySnapshot:
    return DeploymentHistoryEntrySnapshot(
        deployment_id=record.deployment_id,
        contract_slug=record.contract_slug,
        contract_display_name=record.contract_display_name,
        contract_name=record.contract_name,
        semantic_version=record.semantic_version,
        playground_id=record.playground_id,
        playground_target_id=record.playground_target_id,
        playground_target_label=record.playground_target_label,
        status=record.status,
        transport=record.transport,
        redirect_url=record.redirect_url,
        external_request_id=record.external_request_id,
        initiated_at=record.initiated_at,
        completed_at=record.completed_at,
        error_message=_extract_error_message(record.error_payload),
    )


def _extract_error_message(payload: dict[str, object] | None) -> str | None:
    if payload is None:
        return None
    message = payload.get("message")
    if not isinstance(message, str):
        return None
    normalized_message = message.strip()
    return normalized_message or None


def _require_active_user(
    *,
    repository: DeploymentRepository,
    user_id: int,
) -> User:
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise DeploymentHistoryServiceError(
            DeploymentHistoryServiceErrorCode.USER_NOT_FOUND,
            f"User {user_id!r} does not exist.",
            field="user_id",
            details={"user_id": user_id},
        )
    if user.status is not UserStatus.ACTIVE:
        raise DeploymentHistoryServiceError(
            DeploymentHistoryServiceErrorCode.USER_DISABLED,
            "Only active users can review deployment history.",
            field="user_id",
            details={"user_id": user_id, "status": user.status.value},
        )
    return user


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is None:
        raise RuntimeError(f"{label.title()} is missing a persisted identifier.")
    return value


__all__ = [
    "DEFAULT_PRIVATE_DEPLOYMENT_HISTORY_LIMIT",
    "DeploymentHistoryEntrySnapshot",
    "DeploymentHistoryServiceError",
    "DeploymentHistoryServiceErrorCode",
    "PrivateDeploymentHistorySnapshot",
    "SavedTargetShortcutSnapshot",
    "load_private_deployment_history_snapshot",
]
