"""Playground adapter contract for deployment integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, Mapping, Protocol

from contracting_hub.models.base import utc_now

PLAYGROUND_DEPLOYMENT_CHANNEL = "contracting_hub"


class PlaygroundTransport(StrEnum):
    """Transport families the playground adapter may expose."""

    DEEP_LINK = "deep_link"
    HTTP = "http"
    HYBRID = "hybrid"


class PlaygroundDispatchStatus(StrEnum):
    """Normalized outcomes for an accepted deployment handoff."""

    ACCEPTED = "accepted"
    REDIRECT_REQUIRED = "redirect_required"


class PlaygroundAdapterErrorCode(StrEnum):
    """Stable error codes surfaced by the adapter boundary."""

    INVALID_PLAYGROUND_ID = "invalid_playground_id"
    INVALID_CONTRACT_NAME = "invalid_contract_name"
    INVALID_VERSION = "invalid_version"
    INVALID_SOURCE = "invalid_source"
    UNSUPPORTED_TRANSPORT = "unsupported_transport"
    PAYLOAD_REJECTED = "payload_rejected"
    ADAPTER_MISCONFIGURED = "adapter_misconfigured"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PlaygroundAdapterCapabilities:
    """Describe how a concrete adapter can hand deployments off."""

    transport: PlaygroundTransport
    supports_redirects: bool = False
    supports_request_tracking: bool = False


@dataclass(frozen=True)
class PlaygroundContractPayload:
    """Immutable contract version payload handed to a playground target."""

    slug: str
    name: str
    version: str
    source_code: str
    changelog: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def source_hash_sha256(self) -> str:
        """Return a stable hash of the source snapshot."""
        return sha256(self.source_code.encode("utf-8")).hexdigest()

    def as_payload(self) -> dict[str, Any]:
        """Serialize the contract snapshot to the adapter payload contract."""
        contract_payload: dict[str, Any] = {
            "slug": self.slug,
            "name": self.name,
            "version": self.version,
            "source_code": self.source_code,
            "source_hash_sha256": self.source_hash_sha256,
            "metadata": dict(self.metadata),
        }
        if self.changelog is not None:
            contract_payload["changelog"] = self.changelog
        return contract_payload


@dataclass(frozen=True)
class PlaygroundDeploymentRequest:
    """Normalized deployment request passed into the playground adapter."""

    playground_id: str
    contract: PlaygroundContractPayload
    initiated_at: datetime = field(default_factory=utc_now)
    initiated_by_user_id: int | None = None
    callback_url: str | None = None
    client_context: Mapping[str, Any] = field(default_factory=dict)

    @property
    def normalized_playground_id(self) -> str:
        """Trim surrounding whitespace while keeping the ID opaque."""
        return self.playground_id.strip()

    def as_payload(self) -> dict[str, Any]:
        """Serialize the deployment request to the stable adapter payload."""
        deployment_payload: dict[str, Any] = {
            "channel": PLAYGROUND_DEPLOYMENT_CHANNEL,
            "initiated_at": self.initiated_at.isoformat(),
        }
        if self.initiated_by_user_id is not None:
            deployment_payload["initiated_by_user_id"] = self.initiated_by_user_id
        if self.callback_url is not None:
            deployment_payload["callback_url"] = self.callback_url

        return {
            "playground_id": self.normalized_playground_id,
            "contract": self.contract.as_payload(),
            "deployment": deployment_payload,
            "client_context": dict(self.client_context),
        }


@dataclass(frozen=True)
class PlaygroundDeploymentResult:
    """Accepted adapter response returned after a handoff attempt."""

    status: PlaygroundDispatchStatus
    transport: PlaygroundTransport
    message: str
    request_payload: dict[str, Any]
    redirect_url: str | None = None
    external_request_id: str | None = None

    def __post_init__(self) -> None:
        if self.status is PlaygroundDispatchStatus.REDIRECT_REQUIRED and self.redirect_url is None:
            raise ValueError("redirect_url is required when status is redirect_required")


class PlaygroundAdapterError(RuntimeError):
    """Structured adapter failure surfaced to services and UI orchestration."""

    def __init__(
        self,
        code: PlaygroundAdapterErrorCode,
        message: str,
        *,
        retryable: bool = False,
        upstream_status: int | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.upstream_status = upstream_status
        self.details = dict(details or {})

    def as_payload(self) -> dict[str, Any]:
        """Serialize the error for persistence or UI mapping."""
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": str(self),
            "retryable": self.retryable,
            "details": self.details,
        }
        if self.upstream_status is not None:
            payload["upstream_status"] = self.upstream_status
        return payload


class PlaygroundAdapter(Protocol):
    """Adapter interface for Xian playground deployment handoffs."""

    name: str
    capabilities: PlaygroundAdapterCapabilities

    def submit_deployment(
        self,
        request: PlaygroundDeploymentRequest,
    ) -> PlaygroundDeploymentResult:
        """Send a deployment request to the configured playground integration."""


__all__ = [
    "PLAYGROUND_DEPLOYMENT_CHANNEL",
    "PlaygroundAdapter",
    "PlaygroundAdapterCapabilities",
    "PlaygroundAdapterError",
    "PlaygroundAdapterErrorCode",
    "PlaygroundContractPayload",
    "PlaygroundDeploymentRequest",
    "PlaygroundDeploymentResult",
    "PlaygroundDispatchStatus",
    "PlaygroundTransport",
]
