from __future__ import annotations

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import (
    AdminAuditLog,
    Contract,
    ContractRelation,
    ContractRelationType,
    Profile,
    PublicationStatus,
    User,
    UserRole,
)
from contracting_hub.services.admin_contract_relations import (
    AdminContractRelationManagerServiceError,
    create_admin_contract_relation,
    delete_admin_contract_relation,
    load_admin_contract_relation_manager_snapshot,
    update_admin_contract_relation,
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


def _valid_source(label: str) -> str:
    return f"@export\ndef contract_entrypoint():\n    return {label!r}\n"


def _seed_admin_relation_catalog(session: Session) -> tuple[str, dict[str, int]]:
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
        long_description="Published vault contract.",
        author=author,
        status=PublicationStatus.PUBLISHED,
    )
    example = Contract(
        slug="escrow-example",
        contract_name="con_escrow_example",
        display_name="Escrow Example",
        short_summary="Example workflow.",
        long_description="Published example contract.",
        author=author,
        status=PublicationStatus.PUBLISHED,
    )
    draft = Contract(
        slug="draft-helper",
        contract_name="con_draft_helper",
        display_name="Draft Helper",
        short_summary="Draft workflow.",
        long_description="Draft helper contract.",
        author=author,
        status=PublicationStatus.DRAFT,
    )

    session.add_all([admin, author, escrow, vault, example, draft])
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
        contract_slug="vault",
        semantic_version="1.0.0",
        source_code=_valid_source("vault"),
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="escrow-example",
        semantic_version="0.3.0",
        source_code=_valid_source("example"),
        status=PublicationStatus.PUBLISHED,
    )

    session.add_all(
        [
            ContractRelation(
                source_contract_id=escrow.id,
                target_contract_id=vault.id,
                relation_type=ContractRelationType.DEPENDS_ON,
                note="Primary treasury dependency.",
            ),
            ContractRelation(
                source_contract_id=example.id,
                target_contract_id=escrow.id,
                relation_type=ContractRelationType.EXAMPLE_FOR,
            ),
        ]
    )
    session.commit()

    authenticated = login_user(
        session=session,
        email="admin@example.com",
        password="secret-password",
    )
    contract_ids = {
        "escrow": escrow.id,
        "vault": vault.id,
        "example": example.id,
        "draft": draft.id,
    }
    return authenticated.session_token, {key: int(value) for key, value in contract_ids.items()}


def test_load_admin_contract_relation_manager_snapshot_includes_directional_relations() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_admin_relation_catalog(session)

        snapshot = load_admin_contract_relation_manager_snapshot(
            session=session,
            contract_slug="escrow",
        )

        assert snapshot.slug == "escrow"
        assert snapshot.latest_public_version == "1.0.0"
        assert snapshot.public_detail_href == "/contracts/escrow"
        assert [entry.counterpart_slug for entry in snapshot.outgoing_relations] == ["vault"]
        assert snapshot.outgoing_relations[0].relation_label == "Depends on"
        assert snapshot.outgoing_relations[0].public_detail_href == "/contracts/vault"
        assert [entry.counterpart_slug for entry in snapshot.incoming_relations] == [
            "escrow-example"
        ]
        assert snapshot.incoming_relations[0].relation_label == "Example for"
        assert [option.slug for option in snapshot.target_options] == [
            "draft-helper",
            "escrow-example",
            "vault",
        ]


def test_create_update_and_delete_admin_contract_relation_persists_changes_and_audit_logs() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token, contract_ids = _seed_admin_relation_catalog(session)

        created = create_admin_contract_relation(
            session=session,
            session_token=admin_session_token,
            contract_slug="escrow",
            target_contract_id=contract_ids["draft"],
            relation_type=ContractRelationType.COMPANION,
            note="  Draft rollout partner  ",
        )

        stored = session.exec(
            select(ContractRelation).where(ContractRelation.id == created.id)
        ).one()
        assert stored.note == "Draft rollout partner"
        assert stored.relation_type is ContractRelationType.COMPANION

        updated = update_admin_contract_relation(
            session=session,
            session_token=admin_session_token,
            contract_slug="escrow",
            relation_id=created.id,
            target_contract_id=contract_ids["example"],
            relation_type=ContractRelationType.SUPERSEDES,
            note="  Public replacement path  ",
        )

        refreshed = session.exec(
            select(ContractRelation).where(ContractRelation.id == updated.id)
        ).one()
        assert refreshed.target_contract_id == contract_ids["example"]
        assert refreshed.relation_type is ContractRelationType.SUPERSEDES
        assert refreshed.note == "Public replacement path"

        delete_admin_contract_relation(
            session=session,
            session_token=admin_session_token,
            contract_slug="escrow",
            relation_id=updated.id,
        )

        deleted = session.exec(
            select(ContractRelation).where(ContractRelation.id == updated.id)
        ).first()
        audit_actions = session.exec(
            select(AdminAuditLog.action).order_by(AdminAuditLog.id.asc())
        ).all()

        assert deleted is None
        assert audit_actions[-3:] == [
            "create_contract_relation",
            "update_contract_relation",
            "delete_contract_relation",
        ]


def test_create_admin_contract_relation_rejects_duplicate_and_self_relations() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token, contract_ids = _seed_admin_relation_catalog(session)

        try:
            create_admin_contract_relation(
                session=session,
                session_token=admin_session_token,
                contract_slug="escrow",
                target_contract_id=contract_ids["vault"],
                relation_type=ContractRelationType.DEPENDS_ON,
            )
        except AdminContractRelationManagerServiceError as error:
            assert error.field == "relation_type"
        else:
            raise AssertionError("Expected duplicate relation creation to fail")

        try:
            create_admin_contract_relation(
                session=session,
                session_token=admin_session_token,
                contract_slug="escrow",
                target_contract_id=contract_ids["escrow"],
                relation_type=ContractRelationType.COMPANION,
            )
        except AdminContractRelationManagerServiceError as error:
            assert error.field == "target_contract_id"
            assert "cannot be related to themselves" in str(error)
        else:
            raise AssertionError("Expected self-referential relation creation to fail")
