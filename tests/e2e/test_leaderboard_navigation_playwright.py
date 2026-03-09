from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]


def test_public_leaderboard_filters_link_to_developer_profiles(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/")

    page.get_by_role("link", name="Developers").click()

    leaderboard_page = page.locator('[data-testid="developer-leaderboard-page"]')
    leaderboard_filters = page.locator('[data-testid="developer-leaderboard-filters"]')
    leaderboard_results = page.locator('[data-testid="developer-leaderboard-results"]')
    leaderboard_cards = page.locator('[data-testid="developer-leaderboard-card"]')

    expect(page).to_have_url(f"{live_server_url}/developers")
    expect(leaderboard_page).to_be_visible()
    expect(leaderboard_results).to_contain_text("2 developers")
    expect(leaderboard_cards).to_have_count(2)
    expect(leaderboard_cards.filter(has_text="Alice Validator")).to_have_count(1)
    expect(leaderboard_cards.filter(has_text="Bob Review")).to_have_count(1)

    leaderboard_filters.locator('select[name="sort"]').select_option("weighted_rating")
    leaderboard_filters.locator('select[name="timeframe"]').select_option("recent")
    leaderboard_filters.locator('select[name="window"]').select_option("90")
    leaderboard_filters.get_by_role("button", name="Apply ranking").click()

    expect(page).to_have_url(
        f"{live_server_url}/developers?sort=weighted_rating&timeframe=recent&window=90"
    )
    query = parse_qs(urlparse(page.url).query)
    assert query == {
        "sort": ["weighted_rating"],
        "timeframe": ["recent"],
        "window": ["90"],
    }

    expect(leaderboard_results).to_contain_text("Top rated")
    expect(leaderboard_results).to_contain_text("Recent window")
    expect(leaderboard_results).to_contain_text("Last 90 days")

    alice_card = leaderboard_cards.filter(has_text="Alice Validator")
    alice_card.get_by_role("link", name="View profile").click()

    profile_page = page.locator('[data-testid="developer-profile-page"]')
    profile_overview = page.locator('[data-testid="developer-profile-overview"]')
    profile_contracts = page.locator('[data-testid="developer-profile-contracts"]')

    expect(page).to_have_url(f"{live_server_url}/developers/alice")
    expect(profile_page).to_be_visible()
    expect(profile_overview).to_contain_text("Alice Validator")
    expect(profile_overview).to_contain_text("@alice")
    expect(profile_overview).to_contain_text("Builds reusable escrow releases for treasury teams.")
    expect(profile_contracts).to_contain_text("Escrow")

    profile_contracts.get_by_role("link", name="Escrow").click()

    expect(page).to_have_url(f"{live_server_url}/contracts/escrow")
    expect(page.locator('[data-testid="contract-detail-header"]')).to_be_visible()
