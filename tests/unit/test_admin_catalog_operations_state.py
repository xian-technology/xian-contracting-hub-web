from __future__ import annotations

from contextlib import contextmanager

import reflex as rx

import contracting_hub.states.admin_catalog_operations as admin_catalog_operations_state_module
from contracting_hub.models import Profile, PublicationStatus, User, UserRole, UserStatus
from contracting_hub.services.admin_catalog_operations import (
    AdminAuditLogInspectionEntry,
    AdminCatalogOperationsError,
    AdminCatalogOperationsErrorCode,
    AdminCatalogOperationsSnapshot,
    AdminCategoryManagementEntry,
    AdminFeaturedContractEntry,
)
from contracting_hub.services.auth import AuthServiceError, AuthServiceErrorCode
from contracting_hub.states.admin_catalog_operations import (
    AdminCatalogOperationsState,
    _audit_log_count_label,
    _category_count_label,
    _featured_count_label,
    _linked_contract_count_label,
    _publication_status_color_scheme,
)
from contracting_hub.utils.meta import HOME_ROUTE


def _build_admin_user() -> User:
    user = User(
        id=7,
        email="admin@example.com",
        password_hash="hashed",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    user.profile = Profile(username="admin", display_name="Catalog Admin")
    return user


def _build_snapshot(*, is_featured: bool = True) -> AdminCatalogOperationsSnapshot:
    return AdminCatalogOperationsSnapshot(
        categories=(
            AdminCategoryManagementEntry(
                category_id=1,
                slug="treasury",
                name="Treasury",
                description="Treasury contracts.",
                sort_order=15,
                contract_count=2,
                updated_at_label="2026-03-09",
                can_delete=False,
            ),
        ),
        featured_contracts=(
            AdminFeaturedContractEntry(
                contract_id=3,
                slug="escrow",
                display_name="Escrow",
                contract_name="con_escrow",
                author_name="Alice Curator",
                categories_label="Treasury",
                latest_public_version="1.0.0",
                status_label="Published",
                status=PublicationStatus.PUBLISHED.value,
                is_featured=is_featured,
                updated_at_label="2026-03-09",
                public_detail_href="/contracts/escrow",
                edit_href="/admin/contracts/escrow/edit",
            ),
        ),
        audit_logs=(
            AdminAuditLogInspectionEntry(
                audit_log_id=4,
                created_at_label="2026-03-09",
                admin_label="Catalog Admin",
                action="set_contract_featured_state",
                action_label="Set Contract Featured State",
                entity_type_label="Contract",
                summary="Marked contract escrow as featured.",
                details_pretty_json='{"slug": "escrow"}',
                has_details=True,
            ),
        ),
    )


def _redirect_path(event: rx.event.EventSpec | None) -> str | None:
    if event is None:
        return None
    for key, value in event.args:
        if key._js_expr == "path":
            return value._var_value
    return None


def test_admin_catalog_operations_state_load_page_applies_snapshot_and_auth_shell(
    monkeypatch,
) -> None:
    state = AdminCatalogOperationsState(_reflex_internal_init=True)

    monkeypatch.setattr(
        AdminCatalogOperationsState,
        "_resolve_user_from_cookie",
        lambda self: _build_admin_user(),
    )
    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "load_admin_catalog_operations_snapshot_safe",
        lambda: _build_snapshot(),
    )

    state.load_page()

    assert state.current_user_id == 7
    assert state.current_identity_label == "Catalog Admin"
    assert state.current_identity_secondary == "@admin"
    assert state.has_current_identity_secondary is True
    assert state.is_authenticated is True
    assert state.has_categories is True
    assert state.has_featured_contracts is True
    assert state.has_audit_logs is True
    assert state.category_count_label == "1 category"
    assert state.featured_count_label == "1 featured contract"
    assert state.audit_log_count_label == "1 recent audit entry"
    assert state.category_rows[0]["slug"] == "treasury"
    assert state.featured_contract_rows[0]["has_public_detail"] is True
    assert state.audit_log_rows[0]["summary"] == "Marked contract escrow as featured."


def test_admin_catalog_operations_state_setters_edit_flow_and_helper_labels() -> None:
    state = AdminCatalogOperationsState(_reflex_internal_init=True)
    state.category_rows = [
        {
            "category_id": "1",
            "slug": "treasury",
            "name": "Treasury",
            "description": "Treasury contracts.",
            "sort_order_label": "15",
            "contract_count_label": "2 linked contracts",
            "updated_at_label": "2026-03-09",
            "can_delete": False,
        }
    ]
    state.category_slug_error = "old"
    state.category_name_error = "old"
    state.category_description_error = "old"
    state.category_sort_order_error = "old"

    state.set_category_slug_value("treasury-v2")
    state.set_category_name_value("Treasury V2")
    state.set_category_description_value("Updated")
    state.set_category_sort_order_value("20")
    state.start_edit_category("1")

    assert state.category_slug_value == "treasury"
    assert state.category_name_value == "Treasury"
    assert state.category_description_value == "Treasury contracts."
    assert state.category_sort_order_value == "15"
    assert state.is_editing_category is True
    assert state.category_form_heading == "Edit category"
    assert state.category_submit_label == "Save category changes"

    state.cancel_category_edit()
    state.start_edit_category("99")

    assert state.is_editing_category is False
    assert state.category_sort_order_value == "0"
    assert state.category_form_error == "The selected category is no longer available."
    assert _category_count_label(2) == "2 categories"
    assert _linked_contract_count_label(1) == "1 linked contract"
    assert _audit_log_count_label(3) == "3 recent audit entries"
    assert _publication_status_color_scheme(PublicationStatus.DEPRECATED.value) == "orange"
    assert _featured_count_label(_build_snapshot(is_featured=False).featured_contracts) == (
        "0 featured contracts"
    )


def test_admin_catalog_operations_state_submit_form_handles_create_update_and_errors(
    monkeypatch,
) -> None:
    state = AdminCatalogOperationsState(_reflex_internal_init=True)
    state.auth_session_token = "session-token"
    state.category_slug_value = "analytics"
    state.category_name_value = "Analytics"
    state.category_description_value = "Telemetry"
    state.category_sort_order_value = "30"

    create_calls: list[tuple[str, str, str, str]] = []
    update_calls: list[tuple[int, str]] = []

    @contextmanager
    def fake_session_scope():
        yield object()

    monkeypatch.setattr(admin_catalog_operations_state_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "load_admin_catalog_operations_snapshot_safe",
        lambda: _build_snapshot(),
    )

    def fake_create_admin_category(
        *,
        session,
        session_token: str,
        slug: str,
        name: str,
        description: str,
        sort_order: str,
    ) -> None:
        create_calls.append((session_token, slug, name, sort_order))

    def fake_update_admin_category(
        *,
        session,
        session_token: str,
        category_id: int,
        slug: str,
        name: str,
        description: str,
        sort_order: str,
    ) -> None:
        update_calls.append((category_id, slug))

    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "create_admin_category",
        fake_create_admin_category,
    )
    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "update_admin_category",
        fake_update_admin_category,
    )

    state.submit_category_form({})

    assert create_calls == [("session-token", "analytics", "Analytics", "30")]
    assert state.category_success_message == "Category created."
    assert state.category_slug_value == ""
    assert state.category_rows[0]["slug"] == "treasury"

    state.editing_category_id = "1"
    state.category_slug_value = "treasury"
    state.category_name_value = "Treasury"
    state.category_description_value = "Updated"
    state.category_sort_order_value = "15"
    state.submit_category_form({})

    assert update_calls == [(1, "treasury")]
    assert state.category_success_message == "Category updated."

    def failing_create(**_: object) -> None:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_SLUG,
            "Bad slug.",
            field="slug",
        )

    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "create_admin_category",
        failing_create,
    )
    state.submit_category_form({})

    assert state.category_slug_error == "Bad slug."


def test_admin_catalog_operations_state_delete_toggle_sync_and_logout(monkeypatch) -> None:
    state = AdminCatalogOperationsState(_reflex_internal_init=True)
    state.auth_session_token = "session-token"
    state.category_rows = [
        {
            "category_id": "1",
            "slug": "treasury",
            "name": "Treasury",
            "description": "Treasury contracts.",
            "sort_order_label": "15",
            "contract_count_label": "2 linked contracts",
            "updated_at_label": "2026-03-09",
            "can_delete": False,
        }
    ]
    state.featured_contract_rows = [
        {
            "contract_id": "3",
            "slug": "escrow",
            "display_name": "Escrow",
            "contract_name": "con_escrow",
            "author_name": "Alice Curator",
            "categories_label": "Treasury",
            "latest_public_version": "1.0.0",
            "status_label": "Published",
            "status_color_scheme": "grass",
            "is_featured": False,
            "featured_label": "Not featured",
            "toggle_label": "Feature contract",
            "toggle_variant": "solid",
            "updated_at_label": "2026-03-09",
            "public_detail_href": "/contracts/escrow",
            "has_public_detail": True,
            "edit_href": "/admin/contracts/escrow/edit",
        }
    ]
    state.category_success_message = "done"
    state.featured_success_message = "done"

    deleted_ids: list[int] = []
    featured_calls: list[tuple[str, bool]] = []
    logout_calls: list[str] = []

    @contextmanager
    def fake_session_scope():
        yield object()

    def fake_delete_admin_category(*, session, session_token: str, category_id: int) -> None:
        deleted_ids.append(category_id)

    def fake_set_admin_contract_featured_state(
        *,
        session,
        session_token: str,
        contract_slug: str,
        featured: bool,
    ) -> None:
        featured_calls.append((contract_slug, featured))

    def fake_resolve_current_user(*, session, session_token: str) -> User:
        return _build_admin_user()

    def fake_logout_user(*, session, session_token: str) -> bool:
        logout_calls.append(session_token)
        return True

    monkeypatch.setattr(admin_catalog_operations_state_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "delete_admin_category",
        fake_delete_admin_category,
    )
    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "set_admin_contract_featured_state",
        fake_set_admin_contract_featured_state,
    )
    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "load_admin_catalog_operations_snapshot_safe",
        lambda: _build_snapshot(),
    )
    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "resolve_current_user",
        fake_resolve_current_user,
    )
    monkeypatch.setattr(admin_catalog_operations_state_module, "logout_user", fake_logout_user)

    state.sync_auth_state()
    assert state.current_identity_label == "Catalog Admin"

    state.delete_category("1")
    state.toggle_contract_featured("escrow")
    assert state.category_success_message == "Category deleted."
    assert state.featured_success_message == "Contract removed from featured content."

    logout_event = state.logout_current_user()

    assert deleted_ids == [1]
    assert featured_calls == [("escrow", False)]
    assert logout_calls == ["session-token"]
    assert state.auth_session_token == ""
    assert state.is_authenticated is False
    assert _redirect_path(logout_event) == HOME_ROUTE


def test_admin_catalog_operations_state_error_paths_are_mapped(monkeypatch) -> None:
    state = AdminCatalogOperationsState(_reflex_internal_init=True)
    state.auth_session_token = "session-token"

    @contextmanager
    def fake_session_scope():
        yield object()

    monkeypatch.setattr(admin_catalog_operations_state_module, "session_scope", fake_session_scope)

    def failing_delete(**_: object) -> None:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.CATEGORY_DELETE_NOT_ALLOWED,
            "Still linked.",
            field="category",
        )

    def failing_toggle(**_: object) -> None:
        raise AuthServiceError(
            AuthServiceErrorCode.AUTHENTICATION_REQUIRED,
            "Login again.",
            field="session",
        )

    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "delete_admin_category",
        failing_delete,
    )
    monkeypatch.setattr(
        admin_catalog_operations_state_module,
        "set_admin_contract_featured_state",
        failing_toggle,
    )

    state.delete_category("1")
    state.toggle_contract_featured("missing")
    state._apply_category_error(
        AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_NAME,
            "Bad name.",
            field="name",
        )
    )
    state._apply_category_error(
        AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_DESCRIPTION,
            "Bad description.",
            field="description",
        )
    )
    state._apply_category_error(
        AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_SORT_ORDER,
            "Bad order.",
            field="sort_order",
        )
    )
    state._apply_category_error(RuntimeError("Unexpected"))

    assert state.category_form_error == "Unexpected"
    assert state.category_name_error == "Bad name."
    assert state.category_description_error == "Bad description."
    assert state.category_sort_order_error == "Bad order."
    assert state.featured_error_message == "The selected contract is no longer available."

    state.featured_contract_rows = [
        {
            "contract_id": "3",
            "slug": "escrow",
            "display_name": "Escrow",
            "contract_name": "con_escrow",
            "author_name": "Alice Curator",
            "categories_label": "Treasury",
            "latest_public_version": "1.0.0",
            "status_label": "Published",
            "status_color_scheme": "grass",
            "is_featured": True,
            "featured_label": "Featured",
            "toggle_label": "Remove spotlight",
            "toggle_variant": "soft",
            "updated_at_label": "2026-03-09",
            "public_detail_href": "/contracts/escrow",
            "has_public_detail": True,
            "edit_href": "/admin/contracts/escrow/edit",
        }
    ]
    state.toggle_contract_featured("escrow")

    assert state.featured_error_message == "Login again."
