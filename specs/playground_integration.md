# Playground Integration Contract

## Purpose
This document defines the app-side contract for Xian playground deployments before the concrete adapter is implemented. The goal is to keep Reflex states and services stable whether the playground currently accepts deep links, an HTTP API, or a hybrid of both.

The canonical Python contract lives in [`contracting_hub/integrations/playground.py`](/home/endogen/projects/contracting-hub/contracting_hub/integrations/playground.py).

## Current Playground ID Flow
The current hub-side flow treats the playground ID as an opaque user-supplied identifier.

1. An authenticated user selects a saved playground ID or enters an ad hoc one.
2. The deployment service resolves a specific immutable contract version into a `PlaygroundContractPayload`.
3. The service constructs a `PlaygroundDeploymentRequest` with the chosen `playground_id`, the contract payload, and request metadata such as `initiated_at`.
4. The adapter receives that request and hands it off through its configured transport.
5. The service records either the accepted result payload or a structured adapter error in deployment history.

Current normalization rule:
- Only surrounding whitespace is trimmed from `playground_id`.
- The ID remains otherwise opaque at this stage.
- Strong validation rules for saved playground IDs are deferred to implementation plan task `3.6`.

## Payload Shape
Adapters must accept the normalized request payload below, either by sending it directly over HTTP or by encoding it into a deep link.

```json
{
  "playground_id": "target-123",
  "contract": {
    "slug": "escrow",
    "name": "con_escrow",
    "version": "1.2.0",
    "source_code": "def seed():\n    pass\n",
    "source_hash_sha256": "6b7d5a...",
    "changelog": "Add claim timeout support",
    "metadata": {
      "author_username": "alice",
      "network": "sandbox"
    }
  },
  "deployment": {
    "channel": "contracting_hub",
    "initiated_at": "2026-03-09T10:00:00+00:00",
    "initiated_by_user_id": 42,
    "callback_url": "https://hub.local/deployments/callback"
  },
  "client_context": {
    "request_origin": "contract_detail"
  }
}
```

Field semantics:
- `playground_id`: opaque target identifier selected by the user.
- `contract.slug`: stable hub slug for local routing and audit correlation.
- `contract.name`: Xian contract name intended for deployment.
- `contract.version`: immutable semantic version selected by the user.
- `contract.source_code`: exact version snapshot that will be sent to the playground.
- `contract.source_hash_sha256`: deterministic hash of `source_code` for audit and deduplication.
- `contract.metadata`: optional auxiliary metadata safe to send to the playground integration.
- `deployment.channel`: fixed source marker so external systems can identify contracting-hub initiated requests.
- `deployment.initiated_at`: UTC timestamp created when the request object is built.
- `deployment.initiated_by_user_id`: optional local actor reference.
- `deployment.callback_url`: optional return path for API-backed or hybrid flows.
- `client_context`: optional UI or workflow metadata for logging and diagnostics.

## Adapter Response Contract
Concrete adapters implement `PlaygroundAdapter.submit_deployment(request)`.

Successful handoff responses return `PlaygroundDeploymentResult`:
- `status="accepted"`: the adapter submitted the payload directly and may include `external_request_id`.
- `status="redirect_required"`: the adapter generated a deep link and must include `redirect_url`.
- `transport`: one of `deep_link`, `http`, or `hybrid`.
- `request_payload`: the exact normalized payload the service should persist alongside deployment history.

## Error Semantics
Adapters raise `PlaygroundAdapterError` for rejected or failed handoffs. Errors are structured so services can persist them and map them to user-facing messages without parsing arbitrary exception text.

| Code | Retryable | Meaning |
| --- | --- | --- |
| `invalid_playground_id` | no | The supplied target ID is empty or malformed for the adapter. |
| `invalid_contract_name` | no | The contract name cannot be sent to the playground. |
| `invalid_version` | no | The requested contract version metadata is invalid or incomplete. |
| `invalid_source` | no | The source snapshot is empty, corrupt, or otherwise unsendable. |
| `unsupported_transport` | no | The configured adapter cannot fulfill the requested transport behavior. |
| `payload_rejected` | depends | The upstream playground rejected a syntactically valid request. |
| `adapter_misconfigured` | no | Required adapter configuration is missing or inconsistent. |
| `unavailable` | yes | The playground service is temporarily unavailable. |
| `timeout` | yes | The upstream handoff timed out. |
| `unknown` | depends | An unexpected adapter failure occurred. |

Persisted error payload shape:

```json
{
  "code": "payload_rejected",
  "message": "Playground rejected the deployment payload.",
  "retryable": false,
  "upstream_status": 422,
  "details": {
    "field": "contract.source_code"
  }
}
```

## Implementation Notes
- Keep the adapter layer pure Python and independent from Reflex state classes.
- Delay `xian-py` imports until a concrete adapter is added in task `3.7`; the boundary defined here should remain importable in test environments without the SDK.
- Deployment history should store both `request_payload` and serialized adapter errors so deep-link and HTTP flows share one audit trail.
