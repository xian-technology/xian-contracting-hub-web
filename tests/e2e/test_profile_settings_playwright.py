from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from contracting_hub.utils.meta import PROFILE_SETTINGS_ROUTE

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]


def test_authenticated_users_can_manage_profile_settings(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/register")

    register_form = page.locator('[data-testid="register-form"]')
    expect(register_form).to_be_visible()

    register_form.locator('input[name="username"]').fill("frank_builder")
    register_form.locator('input[name="email"]').fill("frank@example.com")
    register_form.locator('input[name="display_name"]').fill("Frank Builder")
    register_form.locator('input[name="password"]').fill("correct horse battery staple")
    register_form.get_by_role("button", name="Create account").click()
    expect(page).to_have_url(f"{live_server_url}/")
    expect(page.locator('[data-testid="session-navigation"]')).to_contain_text("Frank Builder")

    page.goto(f"{live_server_url}{PROFILE_SETTINGS_ROUTE}")

    profile_form = page.locator('[data-testid="profile-settings-form"]')
    session_navigation = page.locator('[data-testid="session-navigation"]')
    settings_url = f"{live_server_url}{PROFILE_SETTINGS_ROUTE}/"

    expect(profile_form).to_be_visible()
    expect(page.locator('[data-testid="playground-target-form"]')).to_have_count(0)
    expect(page).to_have_url(settings_url)
    expect(profile_form.locator('input[name="username"]')).to_have_value("frank_builder")
    expect(profile_form.locator('input[name="display_name"]')).to_have_value("Frank Builder")

    profile_form.locator('input[name="username"]').fill("eve_ops")
    profile_form.locator('input[name="display_name"]').fill("Eve Ops")
    page.locator('textarea[name="bio"]').fill("Deploys and reviews treasury contracts.")
    profile_form.locator('input[name="website_url"]').fill("https://example.com/eve")
    profile_form.locator('input[name="github_url"]').fill("https://github.com/eve")
    profile_form.locator('input[name="xian_profile_url"]').fill("https://xian.org/u/eve")
    profile_form.get_by_role("button", name="Save profile").click()

    expect(profile_form).to_contain_text("Profile updated.")
    expect(session_navigation).to_contain_text("Eve Ops")
    expect(session_navigation).to_contain_text("@eve_ops")

    page.locator('[data-testid="avatar-upload"] input[type="file"]').set_input_files(
        {
            "name": "avatar.png",
            "mimeType": "image/png",
            "buffer": b"fake-avatar",
        }
    )

    expect(profile_form).to_contain_text("Avatar updated.")
    expect(profile_form).to_contain_text("Avatar on file")
    expect(profile_form.get_by_role("button", name="Remove avatar")).to_be_visible()

    profile_form.get_by_role("button", name="Remove avatar").click()

    expect(profile_form).to_contain_text("Avatar removed.")
    expect(profile_form).to_contain_text("No avatar uploaded yet")
