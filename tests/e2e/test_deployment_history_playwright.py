from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from contracting_hub.utils.meta import DEPLOYMENT_HISTORY_ROUTE, PROFILE_SETTINGS_ROUTE

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]


def test_authenticated_users_can_review_deployment_history_and_filter_by_saved_target(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/register")

    register_form = page.locator('[data-testid="register-form"]')
    expect(register_form).to_be_visible()

    register_form.locator('input[name="username"]').fill("history_builder")
    register_form.locator('input[name="email"]').fill("history@example.com")
    register_form.locator('input[name="display_name"]').fill("History Builder")
    register_form.locator('input[name="password"]').fill("correct horse battery staple")
    register_form.get_by_role("button", name="Create account").click()

    expect(page).to_have_url(f"{live_server_url}/")

    page.goto(f"{live_server_url}{PROFILE_SETTINGS_ROUTE}")

    profile_form = page.locator('[data-testid="profile-settings-form"]')
    target_form = page.locator('[data-testid="playground-target-form"]')
    settings_url = f"{live_server_url}{PROFILE_SETTINGS_ROUTE}/"

    expect(profile_form).to_be_visible()
    expect(target_form).to_be_visible()
    expect(page).to_have_url(settings_url)
    expect(profile_form.locator('input[name="username"]')).to_have_value("history_builder")
    expect(profile_form.locator('input[name="display_name"]')).to_have_value("History Builder")

    target_form.locator('input[name="label"]').fill("Sandbox primary")
    target_form.locator('input[name="playground_id"]').fill("sandbox-main")
    target_form.locator('select[name="is_default"]').select_option("yes")
    target_form.get_by_role("button", name="Add saved target").click()

    expect(page.locator("body")).to_contain_text("Saved playground target added.")

    page.goto(f"{live_server_url}/contracts/escrow")

    deploy_trigger = page.locator('[data-testid="contract-deployment-trigger"]')
    expect(deploy_trigger).to_contain_text("Deploy version")
    deploy_trigger.click()

    deployment_form = page.locator('[data-testid="contract-deployment-form"]')
    deployment_result = page.locator('[data-testid="contract-deployment-result"]')

    expect(deployment_form).to_be_visible()
    expect(deployment_form.locator('select[name="playground_target_id"]')).to_be_visible()

    deployment_form.locator('select[name="semantic_version"]').select_option("1.0.0")
    deployment_form.get_by_role("button", name="Deploy version").click()

    expect(deployment_result).to_be_visible()
    expect(deployment_result).to_contain_text("Redirect ready")

    page.goto(f"{live_server_url}{DEPLOYMENT_HISTORY_ROUTE}")

    history_page = page.locator('[data-testid="deployment-history-page"]')
    shortcut_card = page.locator('[data-testid="deployment-history-shortcut"]').first
    history_entry = page.locator('[data-testid="deployment-history-entry"]').first
    history_url = f"{live_server_url}{DEPLOYMENT_HISTORY_ROUTE}/"

    expect(page).to_have_url(history_url)
    expect(history_page).to_be_visible()
    expect(history_page).to_contain_text("Viewing all recorded deployments.")
    expect(shortcut_card).to_contain_text("Sandbox primary")
    expect(history_entry).to_contain_text("Escrow")
    expect(history_entry).to_contain_text("Redirect ready")
    expect(history_entry).to_contain_text("sandbox-main")

    shortcut_card.get_by_role("button", name="Filter history").click()

    expect(history_page).to_contain_text("Viewing deployments for Sandbox primary.")
    expect(page.locator('[data-testid="deployment-history-entry"]')).to_have_count(1)
