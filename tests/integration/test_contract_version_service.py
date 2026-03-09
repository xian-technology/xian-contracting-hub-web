from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import Contract, ContractVersion, PublicationStatus
from contracting_hub.services import (
    ContractVersionServiceError,
    ContractVersionServiceErrorCode,
    create_contract_version,
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


def _create_contract(session: Session, slug: str = "escrow") -> Contract:
    contract = Contract(
        slug=slug,
        contract_name=f"con_{slug.replace('-', '_')}",
        display_name=slug.replace("-", " ").title(),
        short_summary="Contract summary.",
        long_description="Long-form contract description.",
        status=PublicationStatus.DRAFT,
    )
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract


def test_create_contract_version_persists_changelog_hash_and_public_pointer() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)

        version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.0.0",
            source_code="def seed():\n    return 'escrow'\n",
            changelog="  Initial release.  ",
            status=PublicationStatus.PUBLISHED,
        )

        stored_contract = session.exec(select(Contract).where(Contract.id == contract.id)).one()
        stored_version = session.exec(
            select(ContractVersion).where(ContractVersion.id == version.id)
        ).one()

        assert stored_version.semantic_version == "1.0.0"
        assert stored_version.changelog == "Initial release."
        assert stored_version.source_hash_sha256 == (
            "6587210b629c8a195d74ea4d4d70de6f4fc47165e9a29538c32cecfef5396544"
        )
        assert stored_version.previous_version_id is None
        assert stored_version.published_at is not None
        assert stored_contract.latest_published_version_id == stored_version.id


def test_create_contract_version_links_to_latest_existing_version_and_keeps_draft_private() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)
        published_version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.0.0",
            source_code="def seed():\n    return 'published'\n",
            status=PublicationStatus.PUBLISHED,
        )

        draft_version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.1.0",
            source_code="def seed():\n    return 'draft'\n",
            changelog="   ",
        )

        stored_contract = session.exec(select(Contract).where(Contract.id == contract.id)).one()

        assert draft_version.status is PublicationStatus.DRAFT
        assert draft_version.previous_version_id == published_version.id
        assert draft_version.changelog is None
        assert stored_contract.latest_published_version_id == published_version.id


def test_create_contract_version_allows_explicit_previous_version_selection() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)
        first_version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.0.0",
            source_code="def seed():\n    return 'one'\n",
            status=PublicationStatus.PUBLISHED,
            published_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        )
        create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.1.0",
            source_code="def seed():\n    return 'draft'\n",
        )

        published_release = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="2.0.0",
            source_code="def seed():\n    return 'two'\n",
            status=PublicationStatus.PUBLISHED,
            previous_version_semantic_version="1.0.0",
        )

        assert published_release.previous_version_id == first_version.id


def test_create_contract_version_rejects_duplicate_semantic_versions_without_overwrite() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)
        original_version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.0.0",
            source_code="def seed():\n    return 'original'\n",
            changelog="Original release.",
            status=PublicationStatus.PUBLISHED,
        )

        with pytest.raises(ContractVersionServiceError) as error:
            create_contract_version(
                session=session,
                contract_slug=contract.slug,
                semantic_version="1.0.0",
                source_code="def seed():\n    return 'replacement'\n",
                changelog="Replacement release.",
            )

        stored_versions = session.exec(
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract.id)
            .order_by(ContractVersion.id.asc())
        ).all()

        assert error.value.code is ContractVersionServiceErrorCode.DUPLICATE_VERSION
        assert len(stored_versions) == 1
        assert stored_versions[0].id == original_version.id
        assert stored_versions[0].source_code == "def seed():\n    return 'original'\n"
        assert stored_versions[0].changelog == "Original release."
