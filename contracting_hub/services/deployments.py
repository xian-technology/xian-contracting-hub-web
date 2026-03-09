"""Service helpers for playground deployment workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlmodel import Session

from contracting_hub.config import AppSettings, get_settings
from contracting_hub.integrations import (
    DeepLinkPlaygroundAdapter,
    PlaygroundAdapter,
    PlaygroundAdapterError,
    PlaygroundAdapterErrorCode,
    PlaygroundContractPayload,
    PlaygroundDeploymentRequest,
    PlaygroundDeploymentResult,
    PlaygroundDispatchStatus,
    PlaygroundTransport,
)
from contracting_hub.models import (
    ContractVersion,
    DeploymentHistory,
    DeploymentStatus,
    DeploymentTransport,
    PlaygroundTarget,
    PublicationStatus,
    User,
    UserStatus,
    utc_now,
)
from contracting_hub.repositories import DeploymentRepository

DEPLOYABLE_CONTRACT_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)


@dataclass(frozen=True)
class ContractDeploymentAttemptResult:
    """Stable result returned after a deployment handoff is recorded."""

    deployment_id: int
    contract_slug: str
    semantic_version: str
    playground_id: str
    playground_target_id: int | None
    status: DeploymentStatus
    transport: DeploymentTransport | None
    message: str
    redirect_url: str | None
    external_request_id: str | None
    request_payload: dict[str, Any]
    response_payload: dict[str, Any] | None
    error_payload: dict[str, Any] | None


class ContractDeploymentServiceErrorCode(StrEnum):
    """Stable deployment-service failures exposed to callers."""

    CONTRACT_VERSION_NOT_DEPLOYABLE = "contract_version_not_deployable"
    CONTRACT_VERSION_NOT_FOUND = "contract_version_not_found"
    INVALID_CALLBACK_URL = "invalid_callback_url"
    INVALID_CLIENT_CONTEXT = "invalid_client_context"
    INVALID_PLAYGROUND_ID = "invalid_playground_id"
    PLAYGROUND_TARGET_CONFLICT = "playground_target_conflict"
    PLAYGROUND_TARGET_NOT_FOUND = "playground_target_not_found"
    PLAYGROUND_TARGET_REQUIRED = "playground_target_required"
    USER_DISABLED = "user_disabled"
    USER_NOT_FOUND = "user_not_found"


class ContractDeploymentServiceError(ValueError):
    """Structured service error for deployment precondition failures."""

    def __init__(
        self,
        code: ContractDeploymentServiceErrorCode,
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


def deploy_contract_version(
    *,
    session: Session,
    user_id: int,
    contract_slug: str,
    semantic_version: str,
    playground_target_id: int | None = None,
    playground_id: str | None = None,
    adapter: PlaygroundAdapter | None = None,
    callback_url: str | None = None,
    client_context: Mapping[str, object] | None = None,
    settings: AppSettings | None = None,
) -> ContractDeploymentAttemptResult:
    """Submit one contract version to the configured playground adapter and record the outcome."""
    repository = DeploymentRepository(session)
    user = _require_active_user(repository=repository, user_id=user_id)
    version = _require_existing_contract_version(
        repository=repository,
        contract_slug=contract_slug,
        semantic_version=semantic_version,
    )
    _require_deployable_contract_version(version)
    target = _resolve_playground_target(
        repository=repository,
        user_id=user_id,
        target_id=playground_target_id,
        playground_id=playground_id,
    )
    resolved_playground_id = _resolve_playground_id(playground_id=playground_id, target=target)
    normalized_client_context = _normalize_client_context(client_context)
    resolved_settings = settings or get_settings()
    normalized_callback_url = _normalize_callback_url(
        callback_url if callback_url is not None else resolved_settings.playground_callback_url
    )
    deployment_request = PlaygroundDeploymentRequest(
        playground_id=resolved_playground_id,
        contract=_build_contract_payload(version),
        initiated_by_user_id=_require_persisted_id(user.id, label="user"),
        callback_url=normalized_callback_url,
        client_context=normalized_client_context,
    )
    resolved_adapter = adapter or DeepLinkPlaygroundAdapter(
        base_url=resolved_settings.playground_deep_link_base_url
    )

    try:
        adapter_result = resolved_adapter.submit_deployment(deployment_request)
    except PlaygroundAdapterError as error:
        return _record_failed_deployment(
            session=session,
            repository=repository,
            user=user,
            version=version,
            target=target,
            request=deployment_request,
            adapter=resolved_adapter,
            error=error,
        )
    except Exception as error:  # pragma: no cover - guarded by integration behavior
        return _record_failed_deployment(
            session=session,
            repository=repository,
            user=user,
            version=version,
            target=target,
            request=deployment_request,
            adapter=resolved_adapter,
            error=PlaygroundAdapterError(
                PlaygroundAdapterErrorCode.UNKNOWN,
                "Unexpected playground adapter failure.",
                details={
                    "exception_type": type(error).__name__,
                    "message": str(error),
                },
            ),
        )

    return _record_successful_deployment(
        session=session,
        repository=repository,
        user=user,
        version=version,
        target=target,
        request=deployment_request,
        result=adapter_result,
    )


def contract_status_supports_deployments(status: PublicationStatus) -> bool:
    """Return whether a contract or version status is deployable by end users."""
    return status in DEPLOYABLE_CONTRACT_STATUSES


def _record_successful_deployment(
    *,
    session: Session,
    repository: DeploymentRepository,
    user: User,
    version: ContractVersion,
    target: PlaygroundTarget | None,
    request: PlaygroundDeploymentRequest,
    result: PlaygroundDeploymentResult,
) -> ContractDeploymentAttemptResult:
    completed_at = utc_now()
    persisted_target_id = (
        None if target is None else _require_persisted_id(target.id, label="target")
    )
    deployment = DeploymentHistory(
        user_id=_require_persisted_id(user.id, label="user"),
        contract_version_id=_require_persisted_id(version.id, label="contract version"),
        playground_target_id=persisted_target_id,
        playground_id=request.normalized_playground_id,
        status=_deployment_status_for_dispatch(result.status),
        transport=_deployment_transport_for_adapter(result.transport),
        external_request_id=result.external_request_id,
        redirect_url=result.redirect_url,
        request_payload=result.request_payload,
        response_payload=_serialize_success_payload(result),
        initiated_at=request.initiated_at,
        completed_at=completed_at,
    )
    if target is not None:
        target.last_used_at = completed_at
    repository.add_deployment(deployment)
    session.commit()
    session.refresh(deployment)
    return ContractDeploymentAttemptResult(
        deployment_id=_require_persisted_id(deployment.id, label="deployment"),
        contract_slug=version.contract.slug,
        semantic_version=version.semantic_version,
        playground_id=deployment.playground_id,
        playground_target_id=deployment.playground_target_id,
        status=deployment.status,
        transport=deployment.transport,
        message=result.message,
        redirect_url=deployment.redirect_url,
        external_request_id=deployment.external_request_id,
        request_payload=deployment.request_payload,
        response_payload=deployment.response_payload,
        error_payload=deployment.error_payload,
    )


def _record_failed_deployment(
    *,
    session: Session,
    repository: DeploymentRepository,
    user: User,
    version: ContractVersion,
    target: PlaygroundTarget | None,
    request: PlaygroundDeploymentRequest,
    adapter: PlaygroundAdapter,
    error: PlaygroundAdapterError,
) -> ContractDeploymentAttemptResult:
    completed_at = utc_now()
    persisted_target_id = (
        None if target is None else _require_persisted_id(target.id, label="target")
    )
    deployment = DeploymentHistory(
        user_id=_require_persisted_id(user.id, label="user"),
        contract_version_id=_require_persisted_id(version.id, label="contract version"),
        playground_target_id=persisted_target_id,
        playground_id=request.normalized_playground_id,
        status=DeploymentStatus.FAILED,
        transport=_deployment_transport_for_adapter(adapter.capabilities.transport),
        request_payload=request.as_payload(),
        error_payload=error.as_payload(),
        initiated_at=request.initiated_at,
        completed_at=completed_at,
    )
    if target is not None:
        target.last_used_at = completed_at
    repository.add_deployment(deployment)
    session.commit()
    session.refresh(deployment)
    return ContractDeploymentAttemptResult(
        deployment_id=_require_persisted_id(deployment.id, label="deployment"),
        contract_slug=version.contract.slug,
        semantic_version=version.semantic_version,
        playground_id=deployment.playground_id,
        playground_target_id=deployment.playground_target_id,
        status=deployment.status,
        transport=deployment.transport,
        message=str(error),
        redirect_url=deployment.redirect_url,
        external_request_id=deployment.external_request_id,
        request_payload=deployment.request_payload,
        response_payload=deployment.response_payload,
        error_payload=deployment.error_payload,
    )


def _require_active_user(
    *,
    repository: DeploymentRepository,
    user_id: int,
) -> User:
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.USER_NOT_FOUND,
            f"User {user_id!r} does not exist.",
            field="user_id",
            details={"user_id": user_id},
        )
    if user.status is not UserStatus.ACTIVE:
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.USER_DISABLED,
            "Only active users can deploy contracts.",
            field="user_id",
            details={"user_id": user_id, "status": user.status.value},
        )
    return user


def _require_existing_contract_version(
    *,
    repository: DeploymentRepository,
    contract_slug: str,
    semantic_version: str,
) -> ContractVersion:
    version = repository.get_contract_version_by_slug(
        contract_slug=contract_slug,
        semantic_version=semantic_version,
        include_unpublished=True,
    )
    if version is None:
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.CONTRACT_VERSION_NOT_FOUND,
            f"Contract version {contract_slug!r}@{semantic_version!r} does not exist.",
            field="semantic_version",
            details={
                "contract_slug": contract_slug,
                "semantic_version": semantic_version,
            },
        )
    return version


def _require_deployable_contract_version(version: ContractVersion) -> None:
    contract = version.contract
    contract_is_deployable = contract_status_supports_deployments(contract.status)
    version_is_deployable = contract_status_supports_deployments(version.status)
    if not contract_is_deployable or not version_is_deployable:
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.CONTRACT_VERSION_NOT_DEPLOYABLE,
            "Only public contract versions can be deployed.",
            field="semantic_version",
            details={
                "contract_slug": contract.slug,
                "semantic_version": version.semantic_version,
                "contract_status": contract.status.value,
                "version_status": version.status.value,
            },
        )


def _resolve_playground_target(
    *,
    repository: DeploymentRepository,
    user_id: int,
    target_id: int | None,
    playground_id: str | None,
) -> PlaygroundTarget | None:
    if target_id is not None and _playground_id_argument_provided(playground_id):
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.PLAYGROUND_TARGET_CONFLICT,
            "Choose either a saved playground target or an ad hoc playground ID.",
            field="playground_target_id",
            details={"playground_target_id": target_id},
        )
    if target_id is None:
        return None

    target = repository.get_playground_target_by_id(user_id=user_id, target_id=target_id)
    if target is not None:
        return target

    raise ContractDeploymentServiceError(
        ContractDeploymentServiceErrorCode.PLAYGROUND_TARGET_NOT_FOUND,
        f"Saved playground target {target_id!r} does not exist.",
        field="playground_target_id",
        details={"playground_target_id": target_id},
    )


def _resolve_playground_id(
    *,
    playground_id: str | None,
    target: PlaygroundTarget | None,
) -> str:
    if target is not None:
        return target.playground_id
    if playground_id is None:
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.PLAYGROUND_TARGET_REQUIRED,
            "A saved playground target or ad hoc playground ID is required.",
            field="playground_id",
        )
    return normalize_ad_hoc_playground_id(playground_id)


def normalize_ad_hoc_playground_id(playground_id: str) -> str:
    """Trim an ad hoc playground identifier while keeping it otherwise opaque."""
    if not isinstance(playground_id, str):
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.INVALID_PLAYGROUND_ID,
            "Playground ID must be a string.",
            field="playground_id",
            details={"expected_type": "str"},
        )
    normalized_playground_id = playground_id.strip()
    if normalized_playground_id:
        return normalized_playground_id

    raise ContractDeploymentServiceError(
        ContractDeploymentServiceErrorCode.INVALID_PLAYGROUND_ID,
        "Playground ID is required.",
        field="playground_id",
    )


def _playground_id_argument_provided(playground_id: str | None) -> bool:
    if playground_id is None:
        return False
    if not isinstance(playground_id, str):
        return True
    return bool(playground_id.strip())


def _normalize_client_context(
    client_context: Mapping[str, object] | None,
) -> dict[str, object]:
    if client_context is None:
        return {}
    if not isinstance(client_context, Mapping):
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.INVALID_CLIENT_CONTEXT,
            "Client context must be a mapping.",
            field="client_context",
            details={"expected_type": "mapping"},
        )

    normalized_client_context: dict[str, object] = {}
    for key, value in client_context.items():
        if not isinstance(key, str):
            raise ContractDeploymentServiceError(
                ContractDeploymentServiceErrorCode.INVALID_CLIENT_CONTEXT,
                "Client context keys must be strings.",
                field="client_context",
                details={"invalid_key": key},
            )
        normalized_client_context[key] = value
    return normalized_client_context


def _normalize_callback_url(callback_url: str | None) -> str | None:
    if callback_url is None:
        return None
    if not isinstance(callback_url, str):
        raise ContractDeploymentServiceError(
            ContractDeploymentServiceErrorCode.INVALID_CALLBACK_URL,
            "Callback URL must be a string.",
            field="callback_url",
            details={"expected_type": "str"},
        )
    normalized_callback_url = callback_url.strip()
    return normalized_callback_url or None


def _build_contract_payload(version: ContractVersion) -> PlaygroundContractPayload:
    metadata: dict[str, object] = {}
    contract = version.contract
    author = contract.author
    if author is not None and author.profile is not None:
        metadata["author_username"] = author.profile.username
    if contract.network is not None:
        metadata["network"] = contract.network.value
    return PlaygroundContractPayload(
        slug=contract.slug,
        name=contract.contract_name,
        version=version.semantic_version,
        source_code=version.source_code,
        changelog=version.changelog,
        metadata=metadata,
    )


def _serialize_success_payload(result: PlaygroundDeploymentResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": result.status.value,
        "transport": result.transport.value,
        "message": result.message,
    }
    if result.redirect_url is not None:
        payload["redirect_url"] = result.redirect_url
    if result.external_request_id is not None:
        payload["external_request_id"] = result.external_request_id
    return payload


def _deployment_status_for_dispatch(status: PlaygroundDispatchStatus) -> DeploymentStatus:
    if status is PlaygroundDispatchStatus.ACCEPTED:
        return DeploymentStatus.ACCEPTED
    return DeploymentStatus.REDIRECT_REQUIRED


def _deployment_transport_for_adapter(transport: PlaygroundTransport) -> DeploymentTransport:
    if transport is PlaygroundTransport.DEEP_LINK:
        return DeploymentTransport.DEEP_LINK
    if transport is PlaygroundTransport.HTTP:
        return DeploymentTransport.HTTP
    return DeploymentTransport.HYBRID


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is None:
        raise RuntimeError(f"{label} must be persisted before deployment workflows run.")
    return value


__all__ = [
    "DEPLOYABLE_CONTRACT_STATUSES",
    "ContractDeploymentAttemptResult",
    "ContractDeploymentServiceError",
    "ContractDeploymentServiceErrorCode",
    "contract_status_supports_deployments",
    "deploy_contract_version",
    "normalize_ad_hoc_playground_id",
]
