from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]


def test_contract_detail_deployment_drawer_records_a_redirect_ready_result(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/contracts/escrow")

    deploy_trigger = page.locator('[data-testid="contract-deployment-trigger"]')

    expect(deploy_trigger).to_be_visible()
    expect(deploy_trigger).to_contain_text("Log in to deploy")

    deploy_trigger.click()
    expect(page).to_have_url(f"{live_server_url}/login")

    page.goto(f"{live_server_url}/register")

    register_form = page.locator('[data-testid="register-form"]')
    expect(register_form).to_be_visible()

    register_form.locator('input[name="username"]').fill("deploy_builder")
    register_form.locator('input[name="email"]').fill("deploy@example.com")
    register_form.locator('input[name="display_name"]').fill("Deploy Builder")
    register_form.locator('input[name="password"]').fill("correct horse battery staple")
    register_form.get_by_role("button", name="Create account").click()

    expect(page).to_have_url(f"{live_server_url}/contracts/escrow")

    deploy_trigger = page.locator('[data-testid="contract-deployment-trigger"]')
    expect(deploy_trigger).to_contain_text("Deploy version")
    deploy_trigger.click()

    drawer = page.locator('[data-testid="contract-deployment-drawer"]')
    deployment_form = page.locator('[data-testid="contract-deployment-form"]')
    deployment_result = page.locator('[data-testid="contract-deployment-result"]')

    expect(drawer).to_be_visible()
    expect(deployment_form).to_be_visible()

    deployment_form.locator('select[name="semantic_version"]').select_option("1.0.0")
    deployment_form.locator('input[name="playground_id"]').fill("adhoc-target")
    deployment_form.get_by_role("button", name="Deploy version").click()

    expect(deployment_result).to_be_visible()
    expect(deployment_result).to_contain_text("Redirect ready")
    expect(deployment_result).to_contain_text(
        "Deployment recorded. Open the playground to continue."
    )
    expect(deployment_result).to_contain_text("Version 1.0.0")
    expect(deployment_result).to_contain_text("Playground adhoc-target")

    open_playground_link = deployment_result.get_by_role("link", name="Open playground")
    expect(open_playground_link).to_have_attribute(
        "href",
        re.compile(r"^https://playground\.local/deploy\?payload="),
    )
