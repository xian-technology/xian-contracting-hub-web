from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]


def test_contract_detail_inline_engagement_supports_login_prompt_star_and_rating(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/contracts/escrow")

    engagement_panel = page.locator('[data-testid="contract-engagement-panel"]')
    star_toggle = page.locator('[data-testid="contract-star-toggle"]')
    detail_header = page.locator('[data-testid="contract-detail-header"]')

    expect(engagement_panel).to_be_visible()
    expect(engagement_panel).to_contain_text("Log in to save favorites and rate this contract.")
    expect(engagement_panel).to_contain_text("2 total stars")

    star_toggle.click()
    expect(engagement_panel).to_contain_text("Log in to star this contract.")

    page.goto(f"{live_server_url}/register")

    register_form = page.locator('[data-testid="register-form"]')
    expect(register_form).to_be_visible()

    register_form.locator('input[name="username"]').fill("gina_builder")
    register_form.locator('input[name="email"]').fill("gina@example.com")
    register_form.locator('input[name="display_name"]').fill("Gina Builder")
    register_form.locator('input[name="password"]').fill("correct horse battery staple")
    register_form.get_by_role("button", name="Create account").click()

    expect(page).to_have_url(f"{live_server_url}/contracts/escrow")
    expect(engagement_panel).to_contain_text("Choose a score from 1 to 5.")

    star_toggle.click()
    expect(engagement_panel).to_contain_text("Saved to favorites.")
    expect(engagement_panel).to_contain_text("3 total stars")

    page.locator('[data-testid="contract-rating-option-4"]').click()

    expect(engagement_panel).to_contain_text("Rating saved.")
    expect(engagement_panel).to_contain_text("Your rating: 4/5")
    expect(detail_header).to_contain_text("4.3 avg")
    expect(detail_header).to_contain_text("3 ratings")
