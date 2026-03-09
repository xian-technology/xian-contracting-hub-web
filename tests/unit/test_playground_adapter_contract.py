from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

import pytest

from contracting_hub.integrations import (
    PLAYGROUND_DEPLOYMENT_CHANNEL,
    PlaygroundAdapterError,
    PlaygroundAdapterErrorCode,
    PlaygroundContractPayload,
    PlaygroundDeploymentRequest,
    PlaygroundDeploymentResult,
    PlaygroundDispatchStatus,
    PlaygroundTransport,
)


def test_contract_payload_serializes_source_hash_and_metadata() -> None:
    payload = PlaygroundContractPayload(
        slug="escrow",
        name="con_escrow",
        version="1.2.0",
        source_code="def seed():\n    pass\n",
        changelog="Add timeout handling",
        metadata={"network": "sandbox"},
    ).as_payload()

    assert payload["slug"] == "escrow"
    assert payload["name"] == "con_escrow"
    assert payload["version"] == "1.2.0"
    assert payload["metadata"] == {"network": "sandbox"}
    assert (
        payload["source_hash_sha256"]
        == sha256("def seed():\n    pass\n".encode("utf-8")).hexdigest()
    )


def test_deployment_request_serializes_normalized_playground_payload() -> None:
    request = PlaygroundDeploymentRequest(
        playground_id="  target-123  ",
        contract=PlaygroundContractPayload(
            slug="escrow",
            name="con_escrow",
            version="1.2.0",
            source_code="def seed():\n    pass\n",
        ),
        initiated_at=datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc),
        initiated_by_user_id=42,
        callback_url="https://hub.local/deployments/callback",
        client_context={"request_origin": "contract_detail"},
    )

    payload = request.as_payload()

    assert request.normalized_playground_id == "target-123"
    assert payload["playground_id"] == "target-123"
    assert payload["deployment"]["channel"] == PLAYGROUND_DEPLOYMENT_CHANNEL
    assert payload["deployment"]["initiated_by_user_id"] == 42
    assert payload["deployment"]["callback_url"] == "https://hub.local/deployments/callback"
    assert payload["client_context"] == {"request_origin": "contract_detail"}


def test_redirect_result_requires_redirect_url() -> None:
    with pytest.raises(ValueError, match="redirect_url is required"):
        PlaygroundDeploymentResult(
            status=PlaygroundDispatchStatus.REDIRECT_REQUIRED,
            transport=PlaygroundTransport.DEEP_LINK,
            message="Open the playground redirect.",
            request_payload={"playground_id": "target-123"},
        )


def test_adapter_error_serializes_structured_payload() -> None:
    error = PlaygroundAdapterError(
        PlaygroundAdapterErrorCode.PAYLOAD_REJECTED,
        "Playground rejected the deployment payload.",
        retryable=False,
        upstream_status=422,
        details={"field": "contract.source_code"},
    )

    assert error.as_payload() == {
        "code": "payload_rejected",
        "message": "Playground rejected the deployment payload.",
        "retryable": False,
        "upstream_status": 422,
        "details": {"field": "contract.source_code"},
    }
