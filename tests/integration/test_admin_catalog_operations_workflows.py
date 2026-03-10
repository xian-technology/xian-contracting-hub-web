from __future__ import annotations

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import (
    AdminAuditLog,
    Category,
    Contract,
    ContractCategoryLink,
    Profile,
    PublicationStatus,
    User,
    UserRole,
)
from contracting_hub.services.admin_catalog_operations import (
    AdminCatalogOperationsError,
    AdminCatalogOperationsErrorCode,
    create_admin_category,
    delete_admin_category,
    load_admin_catalog_operations_snapshot,
    set_admin_contract_featured_state,
    update_admin_category,
)
from contracting_hub.services.auth import hash_password, login_user
from contracting_hub.services.contract_search import search_contract_catalog
from contracting_hub.services.contract_versions import create_contract_version


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def _seed_admin_catalog(session: Session) -> tuple[str, int, int]:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("secret-password"),
        role=UserRole.ADMIN,
    )
    admin.profile = Profile(username="admin", display_name="Catalog Admin")
    alice = User(
        email="alice@example.com",
        password_hash=hash_password("author-password"),
    )
    alice.profile = Profile(username="alice", display_name="Alice Curator")

    defi = Category(
        slug="defi",
        name="DeFi",
        description="DeFi building blocks.",
        sort_order=10,
    )
    utilities = Category(
        slug="utilities",
        name="Utilities",
        description="Operational helpers.",
        sort_order=20,
    )

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Published escrow helper.",
        long_description="Published escrow reference implementation.",
        author=alice,
        status=PublicationStatus.PUBLISHED,
        featured=False,
        tags=["escrow", "settlement"],
    )
    draft_lab = Contract(
        slug="draft-lab",
        contract_name="con_draft_lab",
        display_name="Draft Lab",
        short_summary="Unpublished contract shell.",
        long_description="Draft-only lab entry.",
        author=alice,
        status=PublicationStatus.DRAFT,
        featured=False,
        tags=["draft"],
    )

    session.add_all(
        [
            admin,
            alice,
            defi,
            utilities,
            escrow,
            draft_lab,
            ContractCategoryLink(contract=escrow, category=defi, is_primary=True, sort_order=0),
        ]
    )
    session.commit()

    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="1.0.0",
        changelog="Initial public release.",
        source_code="@export\ndef escrow_marker():\n    return 'escrow'\n",
        status=PublicationStatus.PUBLISHED,
    )

    authenticated = login_user(
        session=session,
        email="admin@example.com",
        password="secret-password",
    )
    assert defi.id is not None
    assert utilities.id is not None
    return authenticated.session_token, defi.id, utilities.id


def test_category_workflows_refresh_search_documents_and_audit_logs() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token, defi_id, _utilities_id = _seed_admin_catalog(session)

        analytics = create_admin_category(
            session=session,
            session_token=admin_session_token,
            slug="analytics",
            name="Analytics",
            description="Telemetry and dashboards.",
            sort_order="30",
        )
        updated_category = update_admin_category(
            session=session,
            session_token=admin_session_token,
            category_id=defi_id,
            slug="treasury",
            name="Treasury",
            description="Treasury-oriented contract flows.",
            sort_order="15",
        )
        treasury_results = search_contract_catalog(
            session=session,
            query="treasury",
            include_unpublished=True,
        )
        legacy_results = search_contract_catalog(
            session=session,
            query="defi",
            include_unpublished=True,
        )

        assert analytics.slug == "analytics"
        assert updated_category.slug == "treasury"
        assert [result.contract.slug for result in treasury_results] == ["escrow"]
        assert legacy_results == []

        delete_admin_category(
            session=session,
            session_token=admin_session_token,
            category_id=analytics.id,
        )

        snapshot = load_admin_catalog_operations_snapshot(session=session)
        audit_actions = session.exec(
            select(AdminAuditLog.action, AdminAuditLog.summary).order_by(AdminAuditLog.id.asc())
        ).all()

        assert [category.slug for category in session.exec(select(Category)).all()] == [
            "treasury",
            "utilities",
        ]
        assert [entry.slug for entry in snapshot.categories] == ["treasury", "utilities"]
        assert snapshot.audit_logs[0].action == "delete_category"
        assert ("create_category", "Created category analytics.") in audit_actions
        assert ("update_category", "Updated category treasury.") in audit_actions
        assert ("delete_category", "Deleted category analytics.") in audit_actions


def test_featured_curation_updates_contract_flag_and_rejects_unsafe_changes() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token, defi_id, _utilities_id = _seed_admin_catalog(session)

        set_admin_contract_featured_state(
            session=session,
            session_token=admin_session_token,
            contract_slug="escrow",
            featured=True,
        )

        with pytest.raises(AdminCatalogOperationsError) as delete_error:
            delete_admin_category(
                session=session,
                session_token=admin_session_token,
                category_id=defi_id,
            )

        with pytest.raises(AdminCatalogOperationsError) as featured_error:
            set_admin_contract_featured_state(
                session=session,
                session_token=admin_session_token,
                contract_slug="draft-lab",
                featured=True,
            )

        featured_snapshot = load_admin_catalog_operations_snapshot(session=session)
        featured_contract = session.exec(select(Contract).where(Contract.slug == "escrow")).one()
        audit_log = session.exec(
            select(AdminAuditLog)
            .where(AdminAuditLog.action == "set_contract_featured_state")
            .order_by(AdminAuditLog.id.desc())
        ).one()

        assert featured_contract.featured is True
        assert (
            delete_error.value.code is AdminCatalogOperationsErrorCode.CATEGORY_DELETE_NOT_ALLOWED
        )
        assert (
            featured_error.value.code
            is AdminCatalogOperationsErrorCode.FEATURED_CONTRACT_NOT_ALLOWED
        )
        assert [entry.slug for entry in featured_snapshot.featured_contracts] == ["escrow"]
        assert featured_snapshot.featured_contracts[0].is_featured is True
        assert audit_log.summary == "Marked contract escrow as featured."
