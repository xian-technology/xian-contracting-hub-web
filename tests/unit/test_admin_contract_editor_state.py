from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import reflex as rx
from reflex import constants
from reflex.istate.data import RouterData

import contracting_hub.states.admin_contract_editor as admin_contract_editor_state_module
from contracting_hub.models import Profile, PublicationStatus, User, UserRole, UserStatus
from contracting_hub.services.admin_contract_editor import (
    AdminContractEditorAuthorOption,
    AdminContractEditorCategoryOption,
    AdminContractEditorMode,
    AdminContractEditorServiceError,
    AdminContractEditorServiceErrorCode,
    AdminContractEditorSnapshot,
)
from contracting_hub.services.auth import AuthServiceError, AuthServiceErrorCode
from contracting_hub.states.admin_contract_editor import AdminContractEditorState


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


def _set_route_context(
    state: AdminContractEditorState,
    path: str,
    *,
    params: dict[str, str] | None = None,
) -> None:
    router_data = {
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.HEADERS: {"origin": "http://localhost:3000"},
    }
    object.__setattr__(state, "router_data", router_data)
    object.__setattr__(state, "router", RouterData.from_router_data(router_data))
    object.__setattr__(state.router.page, "params", params or {})


def _redirect_path(event: rx.event.EventSpec | None) -> str | None:
    if event is None:
        return None
    for key, value in event.args:
        if key._js_expr == "path":
            return value._var_value
    return None


def _build_snapshot() -> AdminContractEditorSnapshot:
    return AdminContractEditorSnapshot(
        mode=AdminContractEditorMode.EDIT,
        contract_id=12,
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Managed escrow contract.",
        long_description="Long-form curator notes.",
        author_user_id=11,
        author_label="",
        featured=True,
        license_name="MIT",
        documentation_url="https://docs.example.com/escrow",
        source_repository_url="https://github.com/example/escrow",
        network=None,
        primary_category_id=2,
        secondary_category_ids=(1,),
        tags_text="escrow, settlement",
        status=PublicationStatus.PUBLISHED,
        latest_public_version="1.0.0",
        public_detail_href="/contracts/escrow",
        author_options=(
            AdminContractEditorAuthorOption(
                user_id=11,
                username="alice",
                display_label="Alice Curator",
                secondary_label="alice@example.com",
            ),
        ),
        category_options=(
            AdminContractEditorCategoryOption(
                category_id=1,
                slug="defi",
                name="DeFi",
                description="Treasury-oriented flows.",
            ),
            AdminContractEditorCategoryOption(
                category_id=2,
                slug="utilities",
                name="Utilities",
                description="Shared helper contracts.",
            ),
        ),
    )


def test_admin_contract_editor_state_load_page_applies_snapshot_and_auth_shell(monkeypatch) -> None:
    state = AdminContractEditorState(_reflex_internal_init=True)
    _set_route_context(state, "/admin/contracts/escrow/edit")

    monkeypatch.setattr(
        AdminContractEditorState,
        "_resolve_user_from_cookie",
        lambda self: _build_admin_user(),
    )
    monkeypatch.setattr(
        admin_contract_editor_state_module,
        "load_admin_contract_editor_snapshot_safe",
        lambda **_: _build_snapshot(),
    )

    state.load_page()

    assert state.current_user_id == 7
    assert state.current_identity_label == "Catalog Admin"
    assert state.current_identity_secondary == "@admin"
    assert state.is_edit_mode is True
    assert state.editor_heading == "Edit Escrow"
    assert state.contract_slug_value == "escrow"
    assert state.featured_choice == "yes"
    assert state.primary_category_id_value == "2"
    assert state.category_options[0]["is_secondary_selected"] is True
    assert state.category_options[1]["is_primary_selected"] is True


def test_admin_contract_editor_state_category_selection_updates_flags() -> None:
    state = AdminContractEditorState(_reflex_internal_init=True)
    state.primary_category_id_value = "1"
    state.category_options = [
        {
            "id": "1",
            "slug": "defi",
            "name": "DeFi",
            "description": "Primary",
            "is_primary_selected": True,
            "is_secondary_selected": False,
        },
        {
            "id": "2",
            "slug": "utilities",
            "name": "Utilities",
            "description": "Secondary",
            "is_primary_selected": False,
            "is_secondary_selected": False,
        },
        {
            "id": "3",
            "slug": "examples",
            "name": "Examples",
            "description": "Secondary",
            "is_primary_selected": False,
            "is_secondary_selected": False,
        },
    ]

    state.select_primary_category("2")
    state.toggle_secondary_category("3")

    assert state.primary_category_id_value == "2"
    assert state.category_options[1]["is_primary_selected"] is True
    assert state.category_options[1]["is_secondary_selected"] is False
    assert state.category_options[2]["is_secondary_selected"] is True
    assert state.secondary_category_count_label == "1 secondary category"


def test_admin_contract_editor_state_computed_values_setters_and_logout(monkeypatch) -> None:
    state = AdminContractEditorState(_reflex_internal_init=True)
    state.current_user_id = 7
    state.current_user_email = "admin@example.com"
    state.current_username = "admin"
    state.current_display_name = "Catalog Admin"
    state.editor_mode = "create"
    state.category_options = [
        {
            "id": "1",
            "slug": "defi",
            "name": "DeFi",
            "description": "Primary",
            "is_primary_selected": False,
            "is_secondary_selected": False,
        }
    ]
    state.public_detail_href = "/contracts/escrow"
    state.load_error_message = "missing"

    logout_calls: list[str] = []

    @contextmanager
    def fake_session_scope():
        yield object()

    def fake_logout_user(*, session, session_token: str) -> bool:
        logout_calls.append(session_token)
        return True

    monkeypatch.setattr(admin_contract_editor_state_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(admin_contract_editor_state_module, "logout_user", fake_logout_user)

    state.auth_session_token = "session-token"
    state.set_contract_slug_value("escrow")
    state.set_contract_name_value("con_escrow")
    state.set_display_name_value("Escrow")
    state.set_short_summary_value("Summary")
    state.set_long_description_value("Description")
    state.set_author_label_value("Core Team")
    state.set_featured_choice("yes")
    state.set_license_name_value("MIT")
    state.set_documentation_url_value("https://docs.example.com/escrow")
    state.set_source_repository_url_value("https://github.com/example/escrow")
    state.set_network_value("sandbox")
    state.set_tags_value("escrow")

    assert state.current_identity_label == "Catalog Admin"
    assert state.current_identity_secondary == "@admin"
    assert state.has_current_identity_secondary is True
    assert state.is_authenticated is True
    assert state.editor_heading == "Create contract"
    assert state.editor_intro.startswith("Create a draft contract shell")
    assert state.editor_submit_label == "Create draft contract"
    assert state.has_public_detail is True
    assert state.has_categories is True
    assert state.show_missing_contract_state is False

    event = state.logout_current_user()

    assert logout_calls == ["session-token"]
    assert state.auth_session_token == ""
    assert state.is_authenticated is False
    assert _redirect_path(event) == "/"


def test_admin_contract_editor_state_submit_form_redirects_on_create(monkeypatch) -> None:
    state = AdminContractEditorState(_reflex_internal_init=True)
    state.contract_slug_value = "escrow-v2"
    state.contract_name_value = "con_escrow_v2"
    state.display_name_value = "Escrow V2"
    state.short_summary_value = "Curated rewrite."
    state.long_description_value = "Long-form notes."
    state.author_label_value = "Core Team"
    state.primary_category_id_value = "2"

    @contextmanager
    def fake_session_scope():
        yield object()

    monkeypatch.setattr(admin_contract_editor_state_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(
        admin_contract_editor_state_module,
        "create_admin_contract_metadata",
        lambda **_: SimpleNamespace(slug="escrow-v2"),
    )

    event = state.submit_form({})

    assert _redirect_path(event) == "/admin/contracts/escrow-v2/edit"


def test_admin_contract_editor_state_handles_missing_contract_load_and_submit_errors(
    monkeypatch,
) -> None:
    state = AdminContractEditorState(_reflex_internal_init=True)
    _set_route_context(state, "/admin/contracts/missing/edit", params={"slug": "missing"})

    monkeypatch.setattr(
        AdminContractEditorState,
        "_resolve_user_from_cookie",
        lambda self: _build_admin_user(),
    )

    def failing_loader(**kwargs):
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.CONTRACT_NOT_FOUND,
            "The requested contract could not be found.",
            field="contract_slug",
        )

    monkeypatch.setattr(
        admin_contract_editor_state_module,
        "load_admin_contract_editor_snapshot_safe",
        failing_loader,
    )

    state.load_page()

    assert state.show_missing_contract_state is True
    assert state.load_error_message == "The requested contract could not be found."
    assert state.editor_heading == "Edit contract"

    state._apply_submit_error(
        AuthServiceError(
            AuthServiceErrorCode.AUTHENTICATION_REQUIRED,
            "Authentication is required.",
            field="session_token",
        )
    )
    assert state.form_error_message == "Authentication is required."

    state._apply_submit_error(
        AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_URL,
            "URLs must use http or https.",
            field="documentation_url",
        )
    )
    state._apply_submit_error(
        AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_URL,
            "URLs must use http or https.",
            field="source_repository_url",
        )
    )
    state._apply_submit_error(
        AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_NETWORK,
            "Choose a supported network value.",
            field="network",
        )
    )
    state._apply_submit_error(ValueError("Unexpected failure"))

    assert state.documentation_url_error == "URLs must use http or https."
    assert state.source_repository_url_error == "URLs must use http or https."
    assert state.network_error == "Choose a supported network value."
    assert state.form_error_message == "Unexpected failure"


def test_admin_contract_editor_state_submit_form_reloads_on_update_and_maps_errors(
    monkeypatch,
) -> None:
    state = AdminContractEditorState(_reflex_internal_init=True)
    state.editor_mode = "edit"
    state.editing_contract_slug = "escrow"
    state.contract_slug_value = "escrow"
    state.contract_name_value = "con_escrow"
    state.display_name_value = "Escrow"
    state.short_summary_value = "Curated rewrite."
    state.long_description_value = "Long-form notes."
    state.author_label_value = "Core Team"
    state.primary_category_id_value = "2"

    reloaded: list[str] = []

    @contextmanager
    def fake_session_scope():
        yield object()

    monkeypatch.setattr(admin_contract_editor_state_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(
        admin_contract_editor_state_module,
        "update_admin_contract_metadata",
        lambda **_: SimpleNamespace(slug="escrow"),
    )
    monkeypatch.setattr(
        AdminContractEditorState,
        "_reload_snapshot",
        lambda self, contract_slug=None: reloaded.append(contract_slug or ""),
    )

    event = state.submit_form({})

    assert event is None
    assert reloaded == ["escrow"]
    assert state.save_success_message == "Contract metadata updated."

    def failing_update(**kwargs) -> None:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.DUPLICATE_CONTRACT_NAME,
            "This contract name is already in use.",
            field="contract_name",
        )

    monkeypatch.setattr(
        admin_contract_editor_state_module,
        "update_admin_contract_metadata",
        failing_update,
    )

    state.submit_form({})

    assert state.contract_name_error == "This contract name is already in use."
