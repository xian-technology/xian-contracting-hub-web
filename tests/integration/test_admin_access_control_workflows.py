from __future__ import annotations

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import (
    AdminAuditLog,
    Category,
    Contract,
    ContractRelation,
    ContractRelationType,
    ContractVersion,
    Profile,
    PublicationStatus,
    User,
    UserRole,
)
from contracting_hub.services.admin_contract_editor import create_admin_contract_metadata
from contracting_hub.services.admin_contract_relations import create_admin_contract_relation
from contracting_hub.services.admin_contract_versions import create_admin_contract_version
from contracting_hub.services.admin_contracts import publish_admin_contract
from contracting_hub.services.auth import (
    AuthServiceError,
    AuthServiceErrorCode,
    hash_password,
    login_user,
)
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


def _seed_admin_access_catalog(session: Session) -> tuple[str, int, int]:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("secret-password"),
        role=UserRole.ADMIN,
    )
    admin.profile = Profile(username="admin", display_name="Catalog Admin")

    member = User(
        email="member@example.com",
        password_hash=hash_password("member-password"),
    )
    member.profile = Profile(username="member", display_name="Member User")

    curator = User(
        email="curator@example.com",
        password_hash=hash_password("curator-password"),
    )
    curator.profile = Profile(username="curator", display_name="Curator One")

    category = Category(slug="defi", name="DeFi", sort_order=10)
    draft_lab = Contract(
        slug="draft-lab",
        contract_name="con_draft_lab",
        display_name="Draft Lab",
        short_summary="Draft-only admin workflow target.",
        long_description="Draft contract used for access-control coverage.",
        author=curator,
        status=PublicationStatus.DRAFT,
    )
    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Published escrow reference.",
        long_description="Published contract for relation targeting.",
        author=curator,
        status=PublicationStatus.PUBLISHED,
    )
    archived_vault = Contract(
        slug="archived-vault",
        contract_name="con_archived_vault",
        display_name="Archived Vault",
        short_summary="Previously public vault helper.",
        long_description="Archived contract kept for publish quick-action coverage.",
        author=curator,
        status=PublicationStatus.DRAFT,
    )

    session.add_all([admin, member, curator, category, draft_lab, escrow, archived_vault])
    session.commit()

    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="1.0.0",
        source_code=_valid_source("escrow"),
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="archived-vault",
        semantic_version="0.9.0",
        source_code=_valid_source("vault"),
        status=PublicationStatus.PUBLISHED,
    )

    archived_vault = session.exec(select(Contract).where(Contract.slug == "archived-vault")).one()
    archived_vault.status = PublicationStatus.ARCHIVED
    session.add(archived_vault)
    session.commit()

    authenticated = login_user(
        session=session,
        email="member@example.com",
        password="member-password",
    )
    assert category.id is not None
    assert escrow.id is not None
    return authenticated.session_token, int(category.id), int(escrow.id)


def test_non_admin_sessions_cannot_mutate_admin_workspace_data() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        member_session_token, category_id, escrow_id = _seed_admin_access_catalog(session)

        with pytest.raises(AuthServiceError) as create_error:
            create_admin_contract_metadata(
                session=session,
                session_token=member_session_token,
                slug="ops-console",
                contract_name="con_ops_console",
                display_name="Ops Console",
                short_summary="Operational admin dashboard metadata.",
                long_description="Draft contract metadata that should stay admin-only.",
                author_label="Ops Team",
                primary_category_id=category_id,
            )

        assert create_error.value.code is AuthServiceErrorCode.INSUFFICIENT_ROLE
        assert session.exec(select(Contract).where(Contract.slug == "ops-console")).first() is None

        with pytest.raises(AuthServiceError) as version_error:
            create_admin_contract_version(
                session=session,
                session_token=member_session_token,
                contract_slug="draft-lab",
                semantic_version="0.1.0",
                source_code=_valid_source("draft"),
                changelog="Initial draft release.",
                publish_now=False,
            )

        assert version_error.value.code is AuthServiceErrorCode.INSUFFICIENT_ROLE
        draft_lab = session.exec(select(Contract).where(Contract.slug == "draft-lab")).one()
        assert (
            session.exec(
                select(ContractVersion).where(ContractVersion.contract_id == draft_lab.id)
            ).all()
            == []
        )

        with pytest.raises(AuthServiceError) as relation_error:
            create_admin_contract_relation(
                session=session,
                session_token=member_session_token,
                contract_slug="draft-lab",
                target_contract_id=escrow_id,
                relation_type=ContractRelationType.COMPANION,
                note="Blocked by access control.",
            )

        assert relation_error.value.code is AuthServiceErrorCode.INSUFFICIENT_ROLE
        assert session.exec(select(ContractRelation)).all() == []

        with pytest.raises(AuthServiceError) as publish_error:
            publish_admin_contract(
                session=session,
                session_token=member_session_token,
                contract_slug="archived-vault",
            )

        assert publish_error.value.code is AuthServiceErrorCode.INSUFFICIENT_ROLE
        archived_vault = session.exec(
            select(Contract).where(Contract.slug == "archived-vault")
        ).one()
        assert archived_vault.status is PublicationStatus.ARCHIVED
        assert session.exec(select(AdminAuditLog)).all() == []
