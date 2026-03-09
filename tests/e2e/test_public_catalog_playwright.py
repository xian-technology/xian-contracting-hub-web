from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]


def test_anonymous_users_can_browse_search_and_filter_contracts(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/browse")

    browse_results = page.locator('[data-testid="browse-results"]')
    browse_cards = page.locator('[data-testid="browse-result-card"]')

    expect(browse_results).to_be_visible()
    expect(browse_cards).to_have_count(3)
    expect(page.get_by_text("Draft Escrow")).to_have_count(0)

    filters = page.locator('[data-testid="browse-filters"]')
    filters.locator('input[name="query"]').fill(" escrow ")
    filters.locator('select[name="category"]').select_option("tooling")
    filters.locator('select[name="tag"]').select_option("utilities")
    filters.locator('select[name="sort"]').select_option("alphabetical")
    filters.get_by_role("button", name="Apply filters").click()

    expect(browse_cards).to_have_count(1)
    expect(browse_cards.first).to_contain_text("Escrow Toolkit")
    expect(browse_results).to_contain_text("Showing 1-1 of 1")

    query = parse_qs(urlparse(page.url).query)
    assert query == {
        "query": ["escrow"],
        "category": ["tooling"],
        "tag": ["utilities"],
        "sort": ["alphabetical"],
    }


def test_anonymous_users_can_open_contract_detail_switch_versions_and_view_diffs(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/contracts/escrow")

    detail_header = page.locator('[data-testid="contract-detail-header"]')
    version_history = page.locator('[data-testid="contract-version-history"]')
    diff_viewer = page.locator('[data-testid="contract-version-diff-viewer"]')
    source_viewer = page.locator('[data-testid="contract-source-viewer"]')

    expect(detail_header).to_be_visible()
    expect(detail_header).to_contain_text("Escrow")
    expect(detail_header).to_contain_text("con_escrow")
    expect(version_history).to_contain_text("2.0.0")
    expect(version_history).to_contain_text("1.0.0")

    expect(diff_viewer).to_be_visible()
    expect(diff_viewer).to_contain_text("2.0.0")
    expect(diff_viewer).to_contain_text("1.0.0")
    expect(diff_viewer).to_contain_text("released escrow")
    expect(diff_viewer).to_contain_text("legacy escrow")
    expect(diff_viewer).not_to_contain_text("draft escrow")

    version_history.locator("a").filter(has_text="1.0.0").click()

    expect(page).to_have_url(f"{live_server_url}/contracts/escrow?version=1.0.0")
    expect(source_viewer).to_contain_text("legacy escrow")
    expect(version_history).to_contain_text("Historical release")
    expect(diff_viewer).to_contain_text("Initial public release")
