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
from contracting_hub.services.admin_contract_versions import (
    create_admin_contract_version,
    load_admin_contract_version_manager_snapshot,
    preview_admin_contract_version,
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


def _valid_source(label: str) -> str:
    return f"@export\ndef contract_entrypoint():\n    return {label!r}\n"


def _seed_admin_version_catalog(session: Session) -> str:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("secret-password"),
        role=UserRole.ADMIN,
    )
    admin.profile = Profile(username="admin", display_name="Catalog Admin")
    author = User(
        email="author@example.com",
        password_hash=hash_password("author-password"),
    )
    author.profile = Profile(username="author", display_name="Author One")

    utilities = Category(slug="utilities", name="Utilities", sort_order=10)

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Escrow workflow.",
        long_description="Published escrow contract.",
        author=author,
        status=PublicationStatus.PUBLISHED,
    )
    vault = Contract(
        slug="vault",
        contract_name="con_vault",
        display_name="Vault",
        short_summary="Vault workflow.",
        long_description="Draft vault contract.",
        author=author,
        status=PublicationStatus.DRAFT,
    )
    drafts = Contract(
        slug="drafts",
        contract_name="con_drafts",
        display_name="Drafts",
        short_summary="Draft-only workflow.",
        long_description="Draft-only contract.",
        author=author,
        status=PublicationStatus.DRAFT,
    )

    session.add_all(
        [
            admin,
            author,
            utilities,
            escrow,
            vault,
            drafts,
            ContractCategoryLink(
                contract=escrow,
                category=utilities,
                is_primary=True,
                sort_order=0,
            ),
            ContractCategoryLink(
                contract=vault,
                category=utilities,
                is_primary=True,
                sort_order=0,
            ),
            ContractCategoryLink(
                contract=drafts,
                category=utilities,
                is_primary=True,
                sort_order=0,
            ),
        ]
    )
    session.commit()

    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="1.0.0",
        source_code=_valid_source("published"),
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="1.1.0",
        source_code=_valid_source("draft"),
        changelog="Draft release candidate.",
    )

    authenticated = login_user(
        session=session,
        email="admin@example.com",
        password="secret-password",
    )
    return authenticated.session_token


def test_load_admin_contract_version_manager_snapshot_includes_drafts_and_public_links() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_admin_version_catalog(session)

        snapshot = load_admin_contract_version_manager_snapshot(
            session=session,
            contract_slug="escrow",
        )

        assert snapshot.slug == "escrow"
        assert snapshot.latest_public_version == "1.0.0"
        assert snapshot.latest_saved_version == "1.1.0"
        assert [entry.semantic_version for entry in snapshot.version_history] == [
            "1.1.0",
            "1.0.0",
        ]
        assert snapshot.version_history[0].previous_version == "1.0.0"
        assert snapshot.version_history[0].public_detail_href is None
        assert snapshot.version_history[1].public_detail_href == "/contracts/escrow"


def test_preview_admin_contract_version_uses_latest_saved_version_as_diff_baseline() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token = _seed_admin_version_catalog(session)

        preview = preview_admin_contract_version(
            session=session,
            session_token=admin_session_token,
            contract_slug="escrow",
            semantic_version="1.2.0",
            source_code=_valid_source("preview"),
            changelog="Preview release.",
        )

        assert preview.semantic_version == "1.2.0"
        assert preview.previous_version == "1.1.0"
        assert preview.diff_summary["from_version"] == "1.1.0"
        assert preview.diff_summary["to_version"] == "1.2.0"
        assert preview.diff_summary["has_previous_version"] is True
        assert preview.can_publish is True
        assert preview.lint_summary == {
            "status": "pass",
            "issue_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
        }


def test_create_admin_contract_version_saves_draft_without_publishing_contract() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token = _seed_admin_version_catalog(session)

        version = create_admin_contract_version(
            session=session,
            session_token=admin_session_token,
            contract_slug="drafts",
            semantic_version="0.1.0",
            source_code=_valid_source("draft-only"),
            changelog="Initial draft.",
            publish_now=False,
        )

        contract = session.exec(select(Contract).where(Contract.slug == "drafts")).one()
        audit_log = session.exec(
            select(AdminAuditLog).where(AdminAuditLog.action == "create_contract_version")
        ).all()[-1]

        assert version.status is PublicationStatus.DRAFT
        assert contract.status is PublicationStatus.DRAFT
        assert contract.latest_published_version is None
        assert audit_log.summary == "Created draft version 0.1.0 for drafts."


def test_create_admin_contract_version_publishes_contract_and_writes_audit_log() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token = _seed_admin_version_catalog(session)

        version = create_admin_contract_version(
            session=session,
            session_token=admin_session_token,
            contract_slug="vault",
            semantic_version="1.0.0",
            source_code=_valid_source("vault"),
            changelog="First public release.",
            publish_now=True,
        )

        contract = session.exec(select(Contract).where(Contract.slug == "vault")).one()
        audit_log = session.exec(
            select(AdminAuditLog).where(AdminAuditLog.action == "publish_contract_version")
        ).all()[-1]
        public_results = search_contract_catalog(
            session=session,
            query="vault",
            include_unpublished=False,
        )

        assert version.status is PublicationStatus.PUBLISHED
        assert contract.status is PublicationStatus.PUBLISHED
        assert contract.latest_published_version is not None
        assert contract.latest_published_version.semantic_version == "1.0.0"
        assert audit_log.summary == "Published version 1.0.0 for vault."
        assert [result.contract.slug for result in public_results] == ["vault"]
