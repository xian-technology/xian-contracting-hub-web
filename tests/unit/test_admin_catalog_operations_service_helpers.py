from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

import contracting_hub.services.admin_catalog_operations as admin_catalog_operations_module
from contracting_hub.models import (
    Category,
    Contract,
    ContractCategoryLink,
    Profile,
    PublicationStatus,
    User,
    UserRole,
    UserStatus,
)
from contracting_hub.services.admin_catalog_operations import (
    AdminCatalogOperationsError,
    AdminCatalogOperationsErrorCode,
    _build_featured_contract_entry,
    _ensure_unique_category_values,
    _format_admin_timestamp,
    _linked_contract_ids_for_category,
    _require_category,
    _require_contract,
    _resolve_admin_label,
    _resolve_author_name,
    _serialize_audit_details,
    build_empty_admin_catalog_operations_snapshot,
    create_admin_category,
    load_admin_catalog_operations_snapshot_safe,
    normalize_admin_category_description,
    normalize_admin_category_name,
    normalize_admin_category_slug,
    normalize_admin_category_sort_order,
    set_admin_contract_featured_state,
    update_admin_category,
)


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def test_normalize_admin_category_slug_trims_and_lowercases() -> None:
    assert normalize_admin_category_slug("  DeFi_tools  ") == "defi_tools"


def test_normalize_admin_category_slug_rejects_invalid_characters() -> None:
    with pytest.raises(AdminCatalogOperationsError) as error_info:
        normalize_admin_category_slug("defi tools")

    assert error_info.value.code is AdminCatalogOperationsErrorCode.INVALID_CATEGORY_SLUG
    assert error_info.value.field == "slug"


def test_normalize_admin_category_sort_order_defaults_blank_and_rejects_text() -> None:
    assert normalize_admin_category_sort_order(None) == 0
    assert normalize_admin_category_sort_order("") == 0

    with pytest.raises(AdminCatalogOperationsError) as error_info:
        normalize_admin_category_sort_order("first")

    assert error_info.value.code is AdminCatalogOperationsErrorCode.INVALID_CATEGORY_SORT_ORDER
    assert error_info.value.field == "sort_order"


def test_error_payload_empty_snapshot_and_safe_loader_fallback(monkeypatch) -> None:
    error = AdminCatalogOperationsError(
        AdminCatalogOperationsErrorCode.INVALID_CATEGORY_NAME,
        "Bad category.",
        field="name",
        details={"name": "bad"},
    )

    @contextmanager
    def failing_session_scope():
        raise sa.exc.OperationalError("SELECT 1", {}, Exception("boom"))
        yield object()

    monkeypatch.setattr(
        admin_catalog_operations_module,
        "session_scope",
        failing_session_scope,
    )

    snapshot = build_empty_admin_catalog_operations_snapshot()
    safe_snapshot = load_admin_catalog_operations_snapshot_safe()

    assert error.as_payload() == {
        "code": "invalid_category_name",
        "field": "name",
        "message": "Bad category.",
        "details": {"name": "bad"},
    }
    assert snapshot.categories == ()
    assert safe_snapshot.audit_logs == ()


def test_validation_and_serialization_helpers_cover_edge_cases() -> None:
    with pytest.raises(AdminCatalogOperationsError) as blank_name_error:
        normalize_admin_category_name("   ")
    with pytest.raises(AdminCatalogOperationsError) as long_name_error:
        normalize_admin_category_name("x" * 129)
    with pytest.raises(AdminCatalogOperationsError) as long_description_error:
        normalize_admin_category_description("x" * 513)

    assert blank_name_error.value.code is AdminCatalogOperationsErrorCode.INVALID_CATEGORY_NAME
    assert long_name_error.value.field == "name"
    assert long_description_error.value.field == "description"
    assert _serialize_audit_details({}) == "{}"
    assert '"count": 3' in _serialize_audit_details({"count": 3})
    assert _format_admin_timestamp(None) == "No updates yet"
    assert _format_admin_timestamp(datetime(2026, 3, 9, 12, 0, 0)) == "2026-03-09"


def test_author_admin_and_featured_entry_helpers_cover_fallbacks() -> None:
    user = User(
        id=4,
        email="alice@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    user.profile = Profile(username="alice", display_name=None)
    contract = Contract(
        id=9,
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Escrow helper.",
        long_description="Long description.",
        status=PublicationStatus.PUBLISHED,
        featured=False,
        author=user,
    )
    contract.category_links = []

    featured_entry = _build_featured_contract_entry(contract)

    assert _resolve_author_name(contract) == "@alice"
    assert _resolve_admin_label(None) == "Unknown admin"
    assert _resolve_admin_label(user) == "@alice"
    assert featured_entry.latest_public_version == "No public version yet"
    assert featured_entry.categories_label == "Uncategorized"
    assert featured_entry.public_detail_href == "/contracts/escrow"

    contract.author = None
    contract.author_label = "Core Team"
    assert _resolve_author_name(contract) == "Core Team"

    contract.author_label = None
    assert _resolve_author_name(contract) == "Unassigned"


def test_uniqueness_and_lookup_helpers_raise_expected_errors() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        category = Category(slug="defi", name="DeFi", sort_order=10)
        contract = Contract(
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Escrow helper.",
            long_description="Long description.",
            status=PublicationStatus.PUBLISHED,
            featured=False,
        )
        session.add_all([category, contract])
        session.commit()
        assert category.id is not None
        assert contract.id is not None

        session.add(
            ContractCategoryLink(
                contract_id=contract.id,
                category_id=category.id,
                is_primary=True,
                sort_order=0,
            )
        )
        session.commit()

        with pytest.raises(AdminCatalogOperationsError) as duplicate_slug_error:
            _ensure_unique_category_values(session=session, slug="defi", name="Treasury")
        with pytest.raises(AdminCatalogOperationsError) as duplicate_name_error:
            _ensure_unique_category_values(session=session, slug="treasury", name="DeFi")
        with pytest.raises(AdminCatalogOperationsError) as missing_category_error:
            _require_category(session=session, category_id=999)
        with pytest.raises(AdminCatalogOperationsError) as blank_contract_error:
            _require_contract(session=session, contract_slug="")
        with pytest.raises(AdminCatalogOperationsError) as missing_contract_error:
            _require_contract(session=session, contract_slug="missing")

        assert (
            duplicate_slug_error.value.code
            is AdminCatalogOperationsErrorCode.DUPLICATE_CATEGORY_SLUG
        )
        assert (
            duplicate_name_error.value.code
            is AdminCatalogOperationsErrorCode.DUPLICATE_CATEGORY_NAME
        )
        assert (
            missing_category_error.value.code is AdminCatalogOperationsErrorCode.CATEGORY_NOT_FOUND
        )
        assert blank_contract_error.value.code is AdminCatalogOperationsErrorCode.CONTRACT_NOT_FOUND
        assert (
            missing_contract_error.value.code is AdminCatalogOperationsErrorCode.CONTRACT_NOT_FOUND
        )
        assert _linked_contract_ids_for_category(session=session, category_id=category.id) == [
            contract.id
        ]


def test_create_update_integrity_paths_and_featured_noop(monkeypatch) -> None:
    admin_user = User(
        id=8,
        email="admin@example.com",
        password_hash="hashed",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    category = Category(id=3, slug="defi", name="DeFi", sort_order=10)
    contract = Contract(
        id=4,
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Escrow helper.",
        long_description="Long description.",
        status=PublicationStatus.PUBLISHED,
        featured=False,
        latest_published_version_id=1,
    )

    class DummySession:
        def add(self, _value: object) -> None:
            return None

        def flush(self) -> None:
            raise sa.exc.IntegrityError("INSERT", {}, Exception("duplicate"))

        def commit(self) -> None:
            raise AssertionError("commit should not be called")

        def refresh(self, _value: object) -> None:
            raise AssertionError("refresh should not be called")

    class DummyFeatureSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, value: object) -> None:
            self.added.append(value)

        def commit(self) -> None:
            raise AssertionError("commit should not be called on no-op")

        def refresh(self, _value: object) -> None:
            raise AssertionError("refresh should not be called on no-op")

    monkeypatch.setattr(
        admin_catalog_operations_module,
        "require_admin_user",
        lambda **_: admin_user,
    )
    monkeypatch.setattr(
        admin_catalog_operations_module,
        "_ensure_unique_category_values",
        lambda **_: None,
    )
    monkeypatch.setattr(
        admin_catalog_operations_module,
        "_require_category",
        lambda **_: category,
    )
    monkeypatch.setattr(
        admin_catalog_operations_module,
        "_linked_contract_ids_for_category",
        lambda **_: [],
    )
    monkeypatch.setattr(
        admin_catalog_operations_module,
        "rebuild_contract_search_document",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(AdminCatalogOperationsError) as create_error:
        create_admin_category(
            session=DummySession(),
            session_token="session-token",
            slug="defi",
            name="DeFi",
            description=None,
            sort_order=10,
        )
    with pytest.raises(AdminCatalogOperationsError) as update_error:
        update_admin_category(
            session=DummySession(),
            session_token="session-token",
            category_id=3,
            slug="defi",
            name="DeFi",
            description=None,
            sort_order=10,
        )

    monkeypatch.setattr(
        admin_catalog_operations_module,
        "_require_contract",
        lambda **_: contract,
    )
    feature_session = DummyFeatureSession()
    returned_contract = set_admin_contract_featured_state(
        session=feature_session,
        session_token="session-token",
        contract_slug="escrow",
        featured=False,
    )

    assert create_error.value.code is AdminCatalogOperationsErrorCode.DUPLICATE_CATEGORY_SLUG
    assert update_error.value.code is AdminCatalogOperationsErrorCode.DUPLICATE_CATEGORY_SLUG
    assert returned_contract is contract
    assert feature_session.added == []
