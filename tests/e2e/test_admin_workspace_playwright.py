from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.playwright, pytest.mark.timeout(120)]

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "secret-password"
CONTRACT_SLUG = "settlement-vault"
CONTRACT_NAME = "con_settlement_vault"
DISPLAY_NAME = "Settlement Vault"


def _url_pattern(base_url: str, path: str) -> re.Pattern[str]:
    normalized = path.rstrip("/") or "/"
    return re.compile(rf"{re.escape(base_url)}{re.escape(normalized)}/?$")


def _login_as_admin(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/admin/contracts")

    login_form = page.locator('[data-testid="login-form"]')
    expect(login_form).to_be_visible()
    expect(page).to_have_url(_url_pattern(live_server_url, "/login"))

    login_form.locator('input[name="email"]').fill(ADMIN_EMAIL)
    login_form.locator('input[name="password"]').fill(ADMIN_PASSWORD)
    login_form.get_by_role("button", name="Log in").click()

    expect(page.locator('[data-testid="admin-contract-page"]')).to_be_visible()
    expect(page).to_have_url(_url_pattern(live_server_url, "/admin/contracts"))


def test_non_admin_users_are_redirected_away_from_admin_routes(
    page: Page,
    live_server_url: str,
) -> None:
    page.goto(f"{live_server_url}/admin/contracts")

    login_form = page.locator('[data-testid="login-form"]')
    expect(login_form).to_be_visible()
    expect(page).to_have_url(_url_pattern(live_server_url, "/login"))

    page.goto(f"{live_server_url}/register")

    register_form = page.locator('[data-testid="register-form"]')
    expect(register_form).to_be_visible()

    register_form.locator('input[name="username"]').fill("admin_guard_tester")
    register_form.locator('input[name="email"]').fill("guard@example.com")
    register_form.locator('input[name="display_name"]').fill("Guard Tester")
    register_form.locator('input[name="password"]').fill("correct horse battery staple")
    register_form.get_by_role("button", name="Create account").click()

    expect(page).to_have_url(_url_pattern(live_server_url, "/"))
    expect(page.locator('[data-testid="session-navigation"]')).to_contain_text("Guard Tester")

    page.goto(f"{live_server_url}/admin/contracts")

    expect(page).to_have_url(_url_pattern(live_server_url, "/"))
    expect(page.locator('[data-testid="admin-contract-page"]')).to_have_count(0)


def test_admins_can_create_publish_archive_and_manage_relations(
    page: Page,
    live_server_url: str,
) -> None:
    _login_as_admin(page, live_server_url)

    page.locator('[data-testid="admin-contract-create-trigger"]').click()

    editor_form = page.locator('[data-testid="admin-contract-editor-form"]')
    primary_category = editor_form.locator('select[name="primary_category_id"]')
    expect(editor_form).to_be_visible()
    expect(primary_category).to_have_value(re.compile(r"\d+"))

    editor_form.locator('input[name="slug"]').fill(CONTRACT_SLUG)
    editor_form.locator('input[name="contract_name"]').fill(CONTRACT_NAME)
    editor_form.locator('input[name="display_name"]').fill(DISPLAY_NAME)
    editor_form.locator('input[name="short_summary"]').fill("Curated settlement vault workflow.")
    editor_form.locator('textarea[name="long_description"]').fill(
        "Coordinates settlement approvals and vault handoff rules for treasury teams."
    )
    editor_form.locator('input[name="author_label"]').fill("Treasury Ops")
    editor_form.locator('input[name="tags"]').fill("settlement, vault")
    editor_form.get_by_role("button", name="Create draft contract").click()

    expect(page).to_have_url(
        _url_pattern(live_server_url, f"/admin/contracts/{CONTRACT_SLUG}/edit")
    )
    expect(editor_form.locator('input[name="display_name"]')).to_have_value(DISPLAY_NAME)
    expect(page.get_by_role("button", name="Manage relations")).to_be_visible()

    page.get_by_role("button", name="Manage relations").click()

    relation_form = page.locator('[data-testid="admin-contract-relation-form"]')
    outgoing_relations = page.locator('[data-testid="admin-contract-relation-outgoing"]')
    target_select = relation_form.locator('select[name="target_contract_id"]')
    expect(relation_form).to_be_visible()
    expect(target_select.locator("option")).to_have_count(6)

    target_select.select_option(label="Escrow (con_escrow) - Published")
    relation_form.locator('select[name="relation_type"]').select_option("companion")
    relation_form.locator('textarea[name="note"]').fill("Initial curator link.")
    relation_form.get_by_role("button", name="Add relation").click()

    expect(outgoing_relations).to_contain_text("Escrow")
    expect(outgoing_relations).to_contain_text("Companion")
    expect(outgoing_relations).to_contain_text("Initial curator link.")

    outgoing_row = page.locator('[data-testid="admin-contract-relation-row-outgoing"]').first
    outgoing_row.get_by_role("button", name="Edit").click()

    target_select.select_option(label="Vault (con_vault) - Published")
    relation_form.locator('select[name="relation_type"]').select_option("depends_on")
    relation_form.locator('textarea[name="note"]').fill("Updated rollout dependency.")
    relation_form.get_by_role("button", name="Save relation changes").click()

    expect(outgoing_relations).to_contain_text("Vault")
    expect(outgoing_relations).to_contain_text("Depends on")
    expect(outgoing_relations).to_contain_text("Updated rollout dependency.")

    outgoing_row.get_by_role("button", name="Remove").click()
    expect(outgoing_relations).to_contain_text("No outgoing relations yet")

    page.goto(f"{live_server_url}/admin/contracts")

    draft_row = page.locator('[data-testid="admin-contract-row"]').filter(has_text="Draft Escrow")
    vault_row = page.locator('[data-testid="admin-contract-row"]').filter(has_text="con_vault")

    expect(draft_row).to_have_count(1)
    expect(draft_row).to_contain_text(
        "Draft-only shell. Safe to delete if the entry is no longer needed."
    )
    expect(draft_row.get_by_role("button", name="Publish")).to_be_disabled()

    expect(vault_row).to_have_count(1)
    vault_row.get_by_role("button", name="Archive").click()

    expect(page.locator('[data-testid="admin-contract-page"]')).to_contain_text(
        "Contract archived while preserving its version history."
    )

    page.goto(f"{live_server_url}/browse")

    vault_card = page.locator('[data-testid="browse-result-card"]').filter(has_text="Vault")
    expect(vault_card).to_have_count(0)

    page.goto(f"{live_server_url}/admin/contracts")

    archived_vault_row = page.locator('[data-testid="admin-contract-row"]').filter(
        has_text="con_archived_vault"
    )
    expect(archived_vault_row).to_have_count(1)
    archived_vault_row.get_by_role("button", name="Publish").click()

    expect(page.locator('[data-testid="admin-contract-page"]')).to_contain_text(
        "Contract published and restored to the public catalog."
    )

    page.goto(f"{live_server_url}/browse")

    archived_vault_card = page.locator('[data-testid="browse-result-card"]').filter(
        has_text="Archived Vault"
    )
    expect(archived_vault_card).to_have_count(1)
