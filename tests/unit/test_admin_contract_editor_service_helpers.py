from __future__ import annotations

import sqlalchemy as sa

import contracting_hub.services.admin_contract_editor as admin_contract_editor_module
from contracting_hub.models import Category, ContractNetwork, Profile, User, UserStatus
from contracting_hub.services.admin_contract_editor import (
    AdminContractEditorMode,
    AdminContractEditorServiceError,
    AdminContractEditorServiceErrorCode,
    _normalize_author_assignment,
    _normalize_category_assignments,
    _normalize_contract_name,
    _normalize_contract_network,
    _normalize_contract_slug,
    _normalize_contract_tags,
    _normalize_contract_url,
    _normalize_display_name,
    _normalize_featured_flag,
    _normalize_license_name,
    _normalize_long_description,
    _normalize_optional_int,
    _normalize_short_summary,
    _raise_duplicate_identity_error,
    _require_persisted_id,
    build_empty_admin_contract_editor_snapshot,
    load_admin_contract_editor_snapshot_safe,
)


def test_build_empty_admin_contract_editor_snapshot_tracks_mode_from_slug() -> None:
    create_snapshot = build_empty_admin_contract_editor_snapshot()
    edit_snapshot = build_empty_admin_contract_editor_snapshot(contract_slug="escrow")

    assert create_snapshot.mode is AdminContractEditorMode.CREATE
    assert create_snapshot.slug == ""
    assert edit_snapshot.mode is AdminContractEditorMode.EDIT
    assert edit_snapshot.slug == "escrow"


def test_normalize_contract_tags_deduplicates_and_strips_values() -> None:
    assert _normalize_contract_tags(" Escrow, treasury,\nEscrow,  ") == (
        "escrow",
        "treasury",
    )


def test_normalize_contract_slug_and_name_wrap_validation_failures() -> None:
    try:
        _normalize_contract_slug("Escrow")
    except AdminContractEditorServiceError as error:
        assert error.code is AdminContractEditorServiceErrorCode.INVALID_SLUG
        assert error.field == "slug"
    else:
        raise AssertionError("Expected invalid slug validation to raise.")

    try:
        _normalize_contract_name("escrow")
    except AdminContractEditorServiceError as error:
        assert error.code is AdminContractEditorServiceErrorCode.INVALID_CONTRACT_NAME
        assert error.field == "contract_name"
    else:
        raise AssertionError("Expected invalid contract-name validation to raise.")


def test_normalize_contract_url_accepts_http_and_https_only() -> None:
    assert (
        _normalize_contract_url(
            "https://docs.example.com/contracts/escrow",
            field="documentation_url",
        )
        == "https://docs.example.com/contracts/escrow"
    )

    try:
        _normalize_contract_url("ftp://example.com/contracts/escrow", field="documentation_url")
    except AdminContractEditorServiceError as error:
        assert error.code is AdminContractEditorServiceErrorCode.INVALID_URL
        assert error.field == "documentation_url"
    else:
        raise AssertionError("Expected invalid URL scheme to raise.")


def test_admin_contract_editor_service_error_serializes_payload() -> None:
    error = AdminContractEditorServiceError(
        AdminContractEditorServiceErrorCode.INVALID_DISPLAY_NAME,
        "Display name is required.",
        field="display_name",
        details={"max_length": 128},
    )

    assert error.as_payload() == {
        "code": "invalid_display_name",
        "field": "display_name",
        "message": "Display name is required.",
        "details": {"max_length": 128},
    }


def test_normalizers_cover_display_summary_description_license_network_and_featured() -> None:
    assert _normalize_display_name("  Escrow   Vault  ") == "Escrow Vault"
    assert _normalize_short_summary("  Curated   vault   summary. ") == "Curated vault summary."
    assert _normalize_long_description("\nLong-form notes.\n") == "Long-form notes."
    assert _normalize_license_name("  Apache-2.0  ") == "Apache-2.0"
    assert _normalize_license_name("   ") is None
    assert _normalize_contract_network(ContractNetwork.SANDBOX) is ContractNetwork.SANDBOX
    assert _normalize_contract_network("testnet") is ContractNetwork.TESTNET
    assert _normalize_contract_network("") is None
    assert _normalize_featured_flag(True) is True
    assert _normalize_featured_flag("yes") is True
    assert _normalize_featured_flag(None) is False

    try:
        _normalize_display_name("")
    except AdminContractEditorServiceError as error:
        assert error.field == "display_name"
    else:
        raise AssertionError("Expected blank display name to raise.")

    try:
        _normalize_short_summary(None)  # type: ignore[arg-type]
    except AdminContractEditorServiceError as error:
        assert error.field == "short_summary"
    else:
        raise AssertionError("Expected non-string summary to raise.")

    try:
        _normalize_long_description("")
    except AdminContractEditorServiceError as error:
        assert error.field == "long_description"
    else:
        raise AssertionError("Expected blank description to raise.")

    try:
        _normalize_license_name("x" * 65)
    except AdminContractEditorServiceError as error:
        assert error.field == "license_name"
    else:
        raise AssertionError("Expected oversized license to raise.")

    try:
        _normalize_contract_network("unknown")
    except AdminContractEditorServiceError as error:
        assert error.field == "network"
    else:
        raise AssertionError("Expected unsupported network to raise.")


class _FakeSession:
    def __init__(self, lookup: dict[tuple[type[object], int], object]) -> None:
        self._lookup = lookup

    def get(self, model: type[object], identifier: int):
        return self._lookup.get((model, identifier))


def test_author_and_category_normalizers_validate_required_entities() -> None:
    active_author = User(id=4, email="alice@example.com", password_hash="hashed")
    active_author.status = UserStatus.ACTIVE
    active_author.profile = Profile(user_id=4, username="alice", display_name="Alice")
    defi = Category(id=10, slug="defi", name="DeFi", sort_order=10)
    utilities = Category(id=11, slug="utilities", name="Utilities", sort_order=20)
    session = _FakeSession(
        {
            (User, 4): active_author,
            (Category, 10): defi,
            (Category, 11): utilities,
        }
    )

    assert _normalize_author_assignment(
        session=session,
        author_user_id=4,
        author_label=None,
    ) == (4, None)
    assert _normalize_author_assignment(
        session=session,
        author_user_id=None,
        author_label=" Core Team ",
    ) == (None, "Core Team")
    assert _normalize_category_assignments(
        session=session,
        primary_category_id=10,
        secondary_category_ids=[11, 10, 11],
    ) == (10, 11)

    try:
        _normalize_author_assignment(session=session, author_user_id=None, author_label=None)
    except AdminContractEditorServiceError as error:
        assert error.field == "author_assignment"
    else:
        raise AssertionError("Expected missing author assignment to raise.")

    try:
        _normalize_category_assignments(
            session=session,
            primary_category_id=999,
            secondary_category_ids=[],
        )
    except AdminContractEditorServiceError as error:
        assert error.field == "primary_category_id"
    else:
        raise AssertionError("Expected missing primary category to raise.")


def test_numeric_and_integrity_helpers_raise_structured_errors(monkeypatch) -> None:
    assert _normalize_optional_int("12", field="primary_category_id") == 12
    assert _normalize_optional_int("", field="primary_category_id") is None

    try:
        _normalize_optional_int(None, field="primary_category_id", required=True)
    except AdminContractEditorServiceError as error:
        assert error.field == "primary_category_id"
    else:
        raise AssertionError("Expected missing required numeric value to raise.")

    try:
        _normalize_optional_int(True, field="primary_category_id")
    except AdminContractEditorServiceError as error:
        assert error.field == "primary_category_id"
    else:
        raise AssertionError("Expected boolean identifier to raise.")

    try:
        _raise_duplicate_identity_error(
            sa.exc.IntegrityError(
                "INSERT",
                {},
                Exception("UNIQUE constraint failed: contracts.slug"),
            ),
            slug="escrow",
            contract_name="con_escrow",
        )
    except AdminContractEditorServiceError as error:
        assert error.field == "slug"
    else:
        raise AssertionError("Expected duplicate slug error to raise.")

    try:
        _require_persisted_id(None, label="category")
    except AdminContractEditorServiceError as error:
        assert error.field == "category_id"
    else:
        raise AssertionError("Expected missing persisted id to raise.")

    def failing_session_scope():
        raise sa.exc.OperationalError("SELECT 1", {}, Exception("broken db"))

    monkeypatch.setattr(admin_contract_editor_module, "session_scope", failing_session_scope)

    snapshot = load_admin_contract_editor_snapshot_safe(contract_slug="escrow")

    assert snapshot.mode is AdminContractEditorMode.EDIT
    assert snapshot.slug == "escrow"
