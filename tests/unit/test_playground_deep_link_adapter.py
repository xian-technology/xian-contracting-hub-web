from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from contracting_hub.integrations import (
    DEFAULT_PLAYGROUND_PAYLOAD_QUERY_PARAM,
    DeepLinkPlaygroundAdapter,
    PlaygroundAdapterError,
    PlaygroundAdapterErrorCode,
    PlaygroundContractPayload,
    PlaygroundDeploymentRequest,
    PlaygroundDispatchStatus,
    PlaygroundTransport,
)


def test_deep_link_adapter_builds_redirect_url_with_serialized_payload() -> None:
    adapter = DeepLinkPlaygroundAdapter(base_url="https://playground.local/deploy")
    request = PlaygroundDeploymentRequest(
        playground_id=" target-123 ",
        contract=PlaygroundContractPayload(
            slug="escrow",
            name="con_escrow",
            version="1.2.0",
            source_code="def seed():\n    pass\n",
            metadata={"network": "sandbox"},
        ),
    )

    result = adapter.submit_deployment(request)
    query = parse_qs(urlsplit(result.redirect_url or "").query)
    payload = json.loads(query[DEFAULT_PLAYGROUND_PAYLOAD_QUERY_PARAM][0])

    assert result.status is PlaygroundDispatchStatus.REDIRECT_REQUIRED
    assert result.transport is PlaygroundTransport.DEEP_LINK
    assert result.message == "Open the playground redirect."
    assert payload["playground_id"] == "target-123"
    assert payload["contract"]["slug"] == "escrow"
    assert result.request_payload == request.as_payload()


def test_deep_link_adapter_rejects_missing_base_url() -> None:
    adapter = DeepLinkPlaygroundAdapter(base_url=None)
    request = PlaygroundDeploymentRequest(
        playground_id="target-123",
        contract=PlaygroundContractPayload(
            slug="escrow",
            name="con_escrow",
            version="1.2.0",
            source_code="def seed():\n    pass\n",
        ),
    )

    with pytest.raises(PlaygroundAdapterError) as error:
        adapter.submit_deployment(request)

    assert error.value.code is PlaygroundAdapterErrorCode.ADAPTER_MISCONFIGURED


def test_deep_link_adapter_rejects_blank_contract_source() -> None:
    adapter = DeepLinkPlaygroundAdapter(base_url="https://playground.local/deploy")
    request = PlaygroundDeploymentRequest(
        playground_id="target-123",
        contract=PlaygroundContractPayload(
            slug="escrow",
            name="con_escrow",
            version="1.2.0",
            source_code="   ",
        ),
    )

    with pytest.raises(PlaygroundAdapterError) as error:
        adapter.submit_deployment(request)

    assert error.value.code is PlaygroundAdapterErrorCode.INVALID_SOURCE
