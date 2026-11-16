"""Source-only links to the browser playground's portable workspace format."""

from __future__ import annotations

import base64
import json
import zlib
from urllib.parse import urlsplit, urlunsplit

MAX_SOURCE_BYTES = 131_072
MAX_SHARE_FRAGMENT_CHARS = 32_000


def build_playground_url(*, base_url: str, contract_name: str, source_code: str) -> str:
    """Open source in the editor, without deploying it or transferring VM state."""
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
        raise ValueError("Playground URL must be an HTTP(S) URL without credentials.")
    if len(source_code.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("This source exceeds the playground's 128 KiB compiler limit.")
    workspace = {
        "format": "xian-playground-workspace",
        "version": 1,
        "editor": {"code": source_code, "contractName": contract_name},
        "environment": {
            "signer": "demo",
            "now": "2024-02-01T12:30:00",
            "blockNum": "100",
            "blockHash": "0xabc...",
            "chainId": "playground-local",
            "inputHash": "playground-seed",
        },
        "metering": {"enabled": True, "chiLimit": ""},
        "contracts": [],
    }
    payload = json.dumps(workspace, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(payload, wbits=-15)
    fragment = "w=" + base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    if len(fragment) + 1 > MAX_SHARE_FRAGMENT_CHARS:
        raise ValueError(
            "This source is too large for a share link. "
            "Download source and paste it into the playground."
        )
    return urlunsplit(parsed._replace(fragment=fragment))
