from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]


def test_users_can_register_logout_and_log_back_in(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/register")

    register_form = page.locator('[data-testid="register-form"]')
    expect(register_form).to_be_visible()

    register_form.locator('input[name="username"]').fill("eve_builder")
    register_form.locator('input[name="email"]').fill("eve@example.com")
    register_form.locator('input[name="display_name"]').fill("Eve Builder")
    register_form.locator('input[name="password"]').fill("correct horse battery staple")
    register_form.get_by_role("button", name="Create account").click()

    session_navigation = page.locator('[data-testid="session-navigation"]')

    expect(page).to_have_url(f"{live_server_url}/")
    expect(session_navigation).to_contain_text("Eve Builder")
    expect(session_navigation).to_contain_text("@eve_builder")
    expect(session_navigation.get_by_role("button", name="Log out")).to_be_visible()

    page.goto(f"{live_server_url}/login")
    expect(page).to_have_url(f"{live_server_url}/")

    session_navigation.get_by_role("button", name="Log out").click()

    expect(page).to_have_url(f"{live_server_url}/")
    expect(session_navigation).to_contain_text("Log in")
    expect(session_navigation).to_contain_text("Create account")

    page.goto(f"{live_server_url}/login")

    login_form = page.locator('[data-testid="login-form"]')
    expect(login_form).to_be_visible()

    login_form.locator('input[name="email"]').fill("eve@example.com")
    login_form.locator('input[name="password"]').fill("correct horse battery staple")
    login_form.get_by_role("button", name="Log in").click()

    expect(page).to_have_url(f"{live_server_url}/")
    expect(session_navigation).to_contain_text("Eve Builder")
    expect(session_navigation).to_contain_text("@eve_builder")
