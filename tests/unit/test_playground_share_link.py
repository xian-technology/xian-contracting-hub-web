import base64
import json
import random
import string
import zlib
from urllib.parse import urlsplit

import pytest

from contracting_hub.integrations.playground import build_playground_url


def decode_workspace(url):
    fragment = urlsplit(url).fragment
    assert fragment.startswith("w=")
    encoded = fragment[2:]
    compressed = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    return json.loads(zlib.decompress(compressed, wbits=-15))


def test_share_link_preserves_exact_source_in_playground_workspace():
    source = "@export\ndef greet():\n    return 'Grüße 世界'\n"
    url = build_playground_url(
        base_url="http://127.0.0.1:3210/?theme=dark#old",
        contract_name="con_greeting",
        source_code=source,
    )
    doc = decode_workspace(url)
    assert urlsplit(url).query == "theme=dark"
    assert "source" not in urlsplit(url).query
    assert doc == {
        "format": "xian-playground-workspace",
        "version": 1,
        "editor": {"code": source, "contractName": "con_greeting"},
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


@pytest.mark.parametrize(
    "playground_base",
    ["", "/playground", "javascript:alert(1)", "https:///bad", "https://user:pass@host/"],
)
def test_share_link_rejects_unsafe_or_missing_host(playground_base):
    with pytest.raises(ValueError, match="Playground URL"):
        build_playground_url(base_url=playground_base, contract_name="con_a", source_code="pass")


def test_share_link_rejects_source_over_compiler_limit_in_bytes():
    with pytest.raises(ValueError, match="128 KiB"):
        build_playground_url(
            base_url="http://localhost:3210", contract_name="con_a", source_code="é" * 65537
        )


def test_share_link_accepts_source_at_compiler_limit():
    source = "é" * 65536
    assert (
        decode_workspace(
            build_playground_url(
                base_url="http://localhost:3210", contract_name="con_a", source_code=source
            )
        )["editor"]["code"]
        == source
    )


def test_share_link_rejects_oversized_fragment_with_export_guidance():
    source = "".join(random.Random(17).choices(string.printable, k=40000))
    with pytest.raises(ValueError, match="Download source"):
        build_playground_url(
            base_url="http://localhost:3210", contract_name="con_a", source_code=source
        )
