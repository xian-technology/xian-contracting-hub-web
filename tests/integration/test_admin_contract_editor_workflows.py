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
from contracting_hub.services.admin_contract_editor import (
    AdminContractEditorMode,
    create_admin_contract_metadata,
    load_admin_contract_editor_snapshot,
    update_admin_contract_metadata,
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


def _seed_admin_editor_catalog(session: Session) -> str:
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
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("author-password"),
    )
    bob.profile = Profile(username="bob", display_name="Bob Builder")

    defi = Category(slug="defi", name="DeFi", sort_order=10)
    utilities = Category(slug="utilities", name="Utilities", sort_order=20)
    examples = Category(slug="examples", name="Examples", sort_order=30)

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Published escrow helper.",
        long_description="Published escrow reference implementation.",
        author=alice,
        status=PublicationStatus.PUBLISHED,
        featured=True,
        tags=["escrow", "settlement"],
        license_name="MIT",
        documentation_url="https://docs.example.com/escrow",
        source_repository_url="https://github.com/example/escrow",
    )

    session.add_all(
        [
            admin,
            alice,
            bob,
            defi,
            utilities,
            examples,
            escrow,
            ContractCategoryLink(contract=escrow, category=defi, is_primary=True, sort_order=0),
            ContractCategoryLink(
                contract=escrow,
                category=examples,
                is_primary=False,
                sort_order=1,
            ),
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

    authenticated = login_user(
        session=session,
        email="admin@example.com",
        password="secret-password",
    )
    return authenticated.session_token


def test_load_admin_contract_editor_snapshot_returns_existing_metadata_and_options() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_admin_editor_catalog(session)

        snapshot = load_admin_contract_editor_snapshot(session=session, contract_slug="escrow")

        assert snapshot.mode is AdminContractEditorMode.EDIT
        assert snapshot.slug == "escrow"
        assert snapshot.contract_name == "con_escrow"
        assert snapshot.author_user_id is not None
        assert snapshot.primary_category_id is not None
        assert snapshot.secondary_category_ids
        assert snapshot.latest_public_version == "1.0.0"
        assert snapshot.public_detail_href == "/contracts/escrow"
        assert [option.name for option in snapshot.category_options] == [
            "DeFi",
            "Utilities",
            "Examples",
        ]
        assert [option.display_label for option in snapshot.author_options] == [
            "Alice Curator",
            "Bob Builder",
            "Catalog Admin",
        ]


def test_create_admin_contract_metadata_persists_metadata_audit_log_and_search_document() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token = _seed_admin_editor_catalog(session)
        categories = session.exec(select(Category).order_by(Category.sort_order.asc())).all()

        created = create_admin_contract_metadata(
            session=session,
            session_token=admin_session_token,
            slug="vault-manager",
            contract_name="con_vault_manager",
            display_name="Vault Manager",
            short_summary="Operational vault controls.",
            long_description="Curated vault management metadata.",
            author_label="Core Team",
            featured="yes",
            license_name="Apache-2.0",
            documentation_url="https://docs.example.com/vault-manager",
            source_repository_url="https://github.com/example/vault-manager",
            primary_category_id=categories[1].id,
            secondary_category_ids=[categories[0].id],
            tags_text="vault, treasury, vault",
        )

        stored = session.exec(select(Contract).where(Contract.slug == "vault-manager")).one()
        audit_log = session.exec(
            select(AdminAuditLog).where(AdminAuditLog.action == "create_contract")
        ).all()[-1]
        search_results = search_contract_catalog(
            session=session,
            query="treasury",
            include_unpublished=True,
        )

        assert created.slug == "vault-manager"
        assert stored.status is PublicationStatus.DRAFT
        assert stored.featured is True
        assert stored.author_user_id is None
        assert stored.author_label == "Core Team"
        assert stored.tags == ["vault", "treasury"]
        assert [link.category.name for link in stored.category_links] == ["Utilities", "DeFi"]
        assert audit_log.summary == "Created contract vault-manager."
        assert [result.contract.slug for result in search_results] == ["vault-manager"]


def test_update_admin_contract_metadata_reassigns_author_taxonomy_and_search_document() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        admin_session_token = _seed_admin_editor_catalog(session)
        categories = session.exec(select(Category).order_by(Category.sort_order.asc())).all()
        bob = session.exec(select(User).where(User.email == "bob@example.com")).one()

        updated = update_admin_contract_metadata(
            session=session,
            session_token=admin_session_token,
            contract_slug="escrow",
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Updated escrow summary.",
            long_description="Updated long-form curator notes.",
            author_user_id=bob.id,
            featured="no",
            primary_category_id=categories[2].id,
            secondary_category_ids=[categories[1].id],
            tags_text="examples, tutorial",
        )

        refreshed = session.exec(select(Contract).where(Contract.slug == "escrow")).one()
        audit_log = session.exec(
            select(AdminAuditLog).where(AdminAuditLog.action == "update_contract_metadata")
        ).all()[-1]
        example_results = search_contract_catalog(
            session=session,
            query="tutorial",
            include_unpublished=True,
        )
        legacy_results = search_contract_catalog(
            session=session,
            query="settlement",
            include_unpublished=True,
        )

        assert updated.slug == "escrow"
        assert refreshed.author_user_id == bob.id
        assert refreshed.author_label is None
        assert refreshed.featured is False
        assert refreshed.tags == ["examples", "tutorial"]
        assert [link.category.name for link in refreshed.category_links] == [
            "Examples",
            "Utilities",
        ]
        assert audit_log.summary == "Updated contract escrow."
        assert [result.contract.slug for result in example_results] == ["escrow"]
        assert legacy_results == []
