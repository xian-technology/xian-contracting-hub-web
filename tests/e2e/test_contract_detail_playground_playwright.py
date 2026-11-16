from __future__ import annotations

import base64
import json
import zlib
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]


def test_anonymous_contract_opens_selected_version_in_browser_playground(
    page: Page, live_server_url: str
) -> None:
    page.goto(f"{live_server_url}/contracts/escrow?version=1.0.0")
    link = page.get_by_role("link", name="Open in Playground", exact=True)
    expect(link).to_be_visible()
    href = link.get_attribute("href")
    assert href is not None
    parsed = urlsplit(href)
    assert parsed.scheme == "http"
    assert parsed.netloc == "127.0.0.1:3210"
    assert parsed.query == ""
    fragment = parsed.fragment.removeprefix("w=")
    data = base64.urlsafe_b64decode(fragment + "=" * (-len(fragment) % 4))
    workspace = json.loads(zlib.decompress(data, wbits=-15))
    assert workspace["editor"]["contractName"] == "con_escrow"
    assert (
        workspace["editor"]["code"]
        == "@export\ndef settle_release_path():\n    return 'legacy escrow'\n"
    )
    assert workspace["contracts"] == []
    assert link.get_attribute("target") == "_blank"
    expect(page.get_by_text("Playground ID", exact=True)).to_have_count(0)
