from __future__ import annotations

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
from contracting_hub.services.admin_contracts import (
    AdminContractActionError,
    AdminContractActionErrorCode,
    AdminContractFeaturedFilter,
    AdminContractStatusFilter,
    archive_admin_contract,
    delete_admin_contract,
    load_admin_contract_index_snapshot,
    publish_admin_contract,
)
from contracting_hub.services.auth import hash_password, login_user
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


def _seed_admin_contract_catalog(session: Session) -> str:
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

    defi = Category(slug="defi", name="DeFi", sort_order=10)
    tooling = Category(slug="tooling", name="Tooling", sort_order=20)

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Public escrow flow.",
        long_description="Published escrow reference implementation.",
        author=alice,
        status=PublicationStatus.PUBLISHED,
        featured=True,
        tags=["escrow", "featured"],
    )
    vault = Contract(
        slug="vault",
        contract_name="con_vault",
        display_name="Vault",
        short_summary="Archived treasury helper.",
        long_description="Previously public treasury helper.",
        author=alice,
        status=PublicationStatus.ARCHIVED,
        tags=["treasury"],
    )
    draft_escrow = Contract(
        slug="draft-escrow",
        contract_name="con_draft_escrow",
        display_name="Draft Escrow",
        short_summary="Draft escrow canary.",
        long_description="Draft-only escrow entry for admin filtering.",
        author=alice,
        status=PublicationStatus.DRAFT,
        tags=["escrow", "draft"],
    )
    legacy = Contract(
        slug="legacy",
        contract_name="con_legacy",
        display_name="Legacy Contract",
        short_summary="Deprecated compatibility contract.",
        long_description="Deprecated contract kept reachable for older integrations.",
        author_label="Core Team",
        status=PublicationStatus.DEPRECATED,
        tags=["legacy"],
    )

    session.add_all(
        [
            admin,
            alice,
            defi,
            tooling,
            escrow,
            vault,
            draft_escrow,
            legacy,
            ContractCategoryLink(contract=escrow, category=defi, is_primary=True),
            ContractCategoryLink(contract=vault, category=tooling, is_primary=True),
            ContractCategoryLink(contract=draft_escrow, category=defi, is_primary=True),
        ]
    )
    session.commit()

    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="1.0.0",
        source_code="@export\ndef escrow_marker():\n    return 'escrow'\n",
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="vault",
        semantic_version="0.9.0",
        source_code="@export\ndef vault_marker():\n    return 'vault'\n",
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="draft-escrow",
        semantic_version="0.1.0",
        source_code="@export\ndef draft_marker():\n    return 'draft'\n",
        status=PublicationStatus.DRAFT,
    )
    create_contract_version(
        session=session,
        contract_slug="legacy",
        semantic_version="1.4.2",
        source_code="@export\ndef legacy_marker():\n    return 'legacy'\n",
        status=PublicationStatus.PUBLISHED,
    )
    session.refresh(vault)
    vault.status = PublicationStatus.ARCHIVED
    session.add(vault)
    session.commit()

    authenticated = login_user(
        session=session,
        email="admin@example.com",
        password="secret-password",
    )
    return authenticated.session_token


def test_admin_contract_index_snapshot_supports_query_tabs_and_featured_filter() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_admin_contract_catalog(session)

        snapshot = load_admin_contract_index_snapshot(session=session, query="escrow")
        draft_only_snapshot = load_admin_contract_index_snapshot(
            session=session,
            query="escrow",
            status_filter=AdminContractStatusFilter.DRAFT,
        )
        featured_snapshot = load_admin_contract_index_snapshot(
            session=session,
            featured_filter=AdminContractFeaturedFilter.FEATURED,
        )

        assert snapshot.total_results == 2
        assert [entry.slug for entry in snapshot.results] == ["escrow", "draft-escrow"]
        assert {tab.value: tab.count for tab in snapshot.status_tabs} == {
            AdminContractStatusFilter.ALL: 2,
            AdminContractStatusFilter.DRAFT: 1,
            AdminContractStatusFilter.PUBLISHED: 1,
            AdminContractStatusFilter.DEPRECATED: 0,
            AdminContractStatusFilter.ARCHIVED: 0,
        }

        assert [entry.slug for entry in draft_only_snapshot.results] == ["draft-escrow"]
        assert [entry.slug for entry in featured_snapshot.results] == ["escrow"]


def test_publish_admin_contract_restores_public_visibility_and_writes_audit_log() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token = _seed_admin_contract_catalog(session)

        publish_admin_contract(
            session=session,
            session_token=admin_session_token,
            contract_slug="vault",
        )

        vault = session.exec(select(Contract).where(Contract.slug == "vault")).one()
        audit_log = session.exec(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "contract")
            .where(AdminAuditLog.action == "publish_contract")
        ).one()

        assert vault.status is PublicationStatus.PUBLISHED
        assert audit_log.summary == "Published contract vault."
        assert audit_log.details["previous_status"] == PublicationStatus.ARCHIVED.value
        assert audit_log.details["next_status"] == PublicationStatus.PUBLISHED.value


def test_archive_and_delete_admin_contracts_update_catalog_state_and_audit_trail() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token = _seed_admin_contract_catalog(session)

        archive_admin_contract(
            session=session,
            session_token=admin_session_token,
            contract_slug="escrow",
        )
        delete_admin_contract(
            session=session,
            session_token=admin_session_token,
            contract_slug="draft-escrow",
        )

        archived_contract = session.exec(select(Contract).where(Contract.slug == "escrow")).one()
        deleted_contract = session.exec(
            select(Contract).where(Contract.slug == "draft-escrow")
        ).first()
        audit_actions = {
            (log.action, log.summary) for log in session.exec(select(AdminAuditLog)).all()
        }

        assert archived_contract.status is PublicationStatus.ARCHIVED
        assert deleted_contract is None
        assert ("archive_contract", "Archived contract escrow.") in audit_actions
        assert ("delete_contract", "Deleted contract draft-escrow.") in audit_actions


def test_delete_admin_contract_rejects_contracts_with_public_history() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token = _seed_admin_contract_catalog(session)

        try:
            delete_admin_contract(
                session=session,
                session_token=admin_session_token,
                contract_slug="escrow",
            )
        except AdminContractActionError as error:
            assert error.code is AdminContractActionErrorCode.DELETE_NOT_ALLOWED
            assert str(error) == (
                "Only draft or archived contracts without a public release can be deleted."
            )
        else:
            raise AssertionError("Expected deleting a public contract to fail.")
