from datetime import datetime, timezone

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import (
    Category,
    Contract,
    ContractCategoryLink,
    ContractNetwork,
    ContractRelation,
    ContractRelationType,
    ContractVersion,
    Profile,
    PublicationStatus,
    User,
)
from contracting_hub.repositories import ContractRepository


def _timestamp(day: int) -> datetime:
    return datetime(2026, 1, day, 12, 0, tzinfo=timezone.utc)


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def _seed_contract_catalog(session: Session) -> None:
    author = User(email="alice@example.com", password_hash="hashed-password")
    author.profile = Profile(
        username="alice",
        display_name="Alice",
        github_url="https://github.com/alice",
    )

    defi = Category(
        slug="defi",
        name="DeFi",
        description="DeFi contract patterns.",
        sort_order=10,
    )
    utilities = Category(
        slug="utilities",
        name="Utilities",
        description="Utility contracts.",
        sort_order=20,
    )

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Curated escrow primitives.",
        long_description="Long-form escrow description.",
        author=author,
        status=PublicationStatus.PUBLISHED,
        featured=True,
        network=ContractNetwork.SANDBOX,
        tags=["escrow", "defi"],
        created_at=_timestamp(1),
        updated_at=_timestamp(5),
    )
    escrow_current = ContractVersion(
        contract=escrow,
        semantic_version="1.0.0",
        status=PublicationStatus.PUBLISHED,
        source_code="def seed():\n    return 'escrow'\n",
        source_hash_sha256="a" * 64,
        changelog="Current public release.",
        published_at=_timestamp(5),
        created_at=_timestamp(5),
        updated_at=_timestamp(5),
    )
    escrow_previous = ContractVersion(
        contract=escrow,
        semantic_version="0.9.0",
        status=PublicationStatus.DEPRECATED,
        source_code="def seed():\n    return 'legacy escrow'\n",
        source_hash_sha256="b" * 64,
        changelog="Legacy release.",
        published_at=_timestamp(3),
        created_at=_timestamp(3),
        updated_at=_timestamp(3),
    )
    escrow_draft = ContractVersion(
        contract=escrow,
        semantic_version="1.1.0",
        status=PublicationStatus.DRAFT,
        source_code="def seed():\n    return 'draft escrow'\n",
        source_hash_sha256="c" * 64,
        changelog="Draft follow-up.",
        created_at=_timestamp(6),
        updated_at=_timestamp(6),
    )
    escrow_current.previous_version = escrow_previous
    escrow_draft.previous_version = escrow_current
    escrow.latest_published_version = escrow_current

    vault = Contract(
        slug="vault",
        contract_name="con_vault",
        display_name="Vault",
        short_summary="Treasury vault reference.",
        long_description="Long-form vault description.",
        author_label="Core Team",
        status=PublicationStatus.DEPRECATED,
        tags=["vault"],
        created_at=_timestamp(2),
        updated_at=_timestamp(4),
    )
    vault_current = ContractVersion(
        contract=vault,
        semantic_version="2.0.0",
        status=PublicationStatus.PUBLISHED,
        source_code="def seed():\n    return 'vault'\n",
        source_hash_sha256="d" * 64,
        changelog="Vault release.",
        published_at=_timestamp(4),
        created_at=_timestamp(4),
        updated_at=_timestamp(4),
    )
    vault.latest_published_version = vault_current

    archived = Contract(
        slug="archive",
        contract_name="con_archive",
        display_name="Archived Contract",
        short_summary="Archived contract record.",
        long_description="Long-form archived description.",
        status=PublicationStatus.ARCHIVED,
        tags=["archive"],
        created_at=_timestamp(2),
        updated_at=_timestamp(2),
    )
    archived_current = ContractVersion(
        contract=archived,
        semantic_version="1.0.0",
        status=PublicationStatus.PUBLISHED,
        source_code="def seed():\n    return 'archive'\n",
        source_hash_sha256="e" * 64,
        published_at=_timestamp(2),
        created_at=_timestamp(2),
        updated_at=_timestamp(2),
    )
    archived.latest_published_version = archived_current

    draft = Contract(
        slug="draft",
        contract_name="con_draft",
        display_name="Draft Contract",
        short_summary="Draft contract record.",
        long_description="Long-form draft description.",
        status=PublicationStatus.DRAFT,
        tags=["draft"],
        created_at=_timestamp(3),
        updated_at=_timestamp(6),
    )
    draft_version = ContractVersion(
        contract=draft,
        semantic_version="0.1.0",
        status=PublicationStatus.DRAFT,
        source_code="def seed():\n    return 'draft'\n",
        source_hash_sha256="f" * 64,
        created_at=_timestamp(6),
        updated_at=_timestamp(6),
    )

    session.add_all(
        [
            defi,
            utilities,
            ContractCategoryLink(contract=escrow, category=defi, is_primary=True, sort_order=0),
            ContractCategoryLink(contract=vault, category=utilities, is_primary=True, sort_order=0),
            ContractRelation(
                source_contract=escrow,
                target_contract=vault,
                relation_type=ContractRelationType.DEPENDS_ON,
            ),
            ContractRelation(
                source_contract=escrow,
                target_contract=archived,
                relation_type=ContractRelationType.COMPANION,
            ),
            ContractRelation(
                source_contract=draft,
                target_contract=escrow,
                relation_type=ContractRelationType.EXAMPLE_FOR,
            ),
            author,
            escrow,
            escrow_current,
            escrow_previous,
            escrow_draft,
            vault,
            vault_current,
            archived,
            archived_current,
            draft,
            draft_version,
        ]
    )
    session.commit()


def test_contract_repository_lists_public_contracts_by_default() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_contract_catalog(session)
        repository = ContractRepository(session)

        contracts = repository.list_contracts()

        assert [contract.slug for contract in contracts] == ["escrow", "vault"]
        assert contracts[0].latest_published_version is not None
        assert contracts[0].latest_published_version.semantic_version == "1.0.0"
        assert contracts[0].author is not None
        assert contracts[0].author.profile is not None
        assert contracts[0].author.profile.username == "alice"
        assert [link.category.slug for link in contracts[0].category_links] == ["defi"]


def test_contract_repository_supports_admin_contract_listing_filters() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_contract_catalog(session)
        repository = ContractRepository(session)

        all_contracts = repository.list_contracts(include_unpublished=True)
        draft_contracts = repository.list_contracts(
            include_unpublished=True,
            statuses=[PublicationStatus.DRAFT],
        )

        assert {contract.slug for contract in all_contracts} == {
            "archive",
            "draft",
            "escrow",
            "vault",
        }
        assert [contract.slug for contract in draft_contracts] == ["draft"]


def test_contract_repository_loads_detail_with_visible_versions_only_for_public_reads() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_contract_catalog(session)
        repository = ContractRepository(session)

        detail = repository.get_contract_detail("escrow")
        admin_detail = repository.get_contract_detail("escrow", include_unpublished=True)

        assert detail is not None
        assert detail.contract.slug == "escrow"
        assert [version.semantic_version for version in detail.versions] == ["1.0.0", "0.9.0"]
        assert [relation.target_contract.slug for relation in detail.relations.outgoing] == [
            "vault"
        ]
        assert [relation.source_contract.slug for relation in detail.relations.incoming] == []

        assert admin_detail is not None
        assert [version.semantic_version for version in admin_detail.versions] == [
            "1.0.0",
            "0.9.0",
            "1.1.0",
        ]
        assert {relation.target_contract.slug for relation in admin_detail.relations.outgoing} == {
            "archive",
            "vault",
        }
        assert [relation.source_contract.slug for relation in admin_detail.relations.incoming] == [
            "draft"
        ]
        assert repository.get_contract_detail("archive") is None


def test_contract_repository_looks_up_publicly_visible_versions() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_contract_catalog(session)
        repository = ContractRepository(session)

        latest_version = repository.get_published_version("escrow")
        previous_version = repository.get_published_version(
            "escrow",
            semantic_version="0.9.0",
        )

        assert latest_version is not None
        assert latest_version.semantic_version == "1.0.0"
        assert previous_version is not None
        assert previous_version.semantic_version == "0.9.0"
        assert repository.get_published_version("escrow", semantic_version="1.1.0") is None
        assert repository.get_published_version("draft") is None


def test_contract_repository_traverses_relations_with_public_visibility_rules() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_contract_catalog(session)
        repository = ContractRepository(session)

        public_relations = repository.traverse_relations("escrow")
        admin_relations = repository.traverse_relations("escrow", include_unpublished=True)

        assert public_relations is not None
        assert [relation.target_contract.slug for relation in public_relations.outgoing] == [
            "vault"
        ]
        assert [relation.source_contract.slug for relation in public_relations.incoming] == []

        assert admin_relations is not None
        assert {relation.target_contract.slug for relation in admin_relations.outgoing} == {
            "archive",
            "vault",
        }
        assert [relation.source_contract.slug for relation in admin_relations.incoming] == ["draft"]
