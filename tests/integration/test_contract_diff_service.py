from __future__ import annotations

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import Contract, ContractVersion, PublicationStatus
from contracting_hub.services import create_contract_version, get_contract_version_diff


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
        status=PublicationStatus.PUBLISHED,
    )
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract


def test_get_contract_version_diff_uses_visible_history_for_public_reads() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)
        create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.0.0",
            source_code="def seed():\n    return 'published'\n",
            status=PublicationStatus.PUBLISHED,
        )
        create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.1.0",
            source_code="def seed():\n    return 'draft'\n",
            status=PublicationStatus.DRAFT,
        )
        current_release = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="2.0.0",
            source_code="def seed():\n    return 'released'\n",
            status=PublicationStatus.PUBLISHED,
        )

        public_diff = get_contract_version_diff(
            session=session,
            contract_slug=contract.slug,
            semantic_version=current_release.semantic_version,
        )
        admin_diff = get_contract_version_diff(
            session=session,
            contract_slug=contract.slug,
            semantic_version=current_release.semantic_version,
            include_unpublished=True,
        )
        stored_version = session.exec(
            select(ContractVersion).where(ContractVersion.id == current_release.id)
        ).one()

        assert public_diff.previous_version is not None
        assert public_diff.previous_version.semantic_version == "1.0.0"
        assert public_diff.summary["from_version"] == "1.0.0"
        assert public_diff.unified_diff is not None
        assert "draft" not in public_diff.unified_diff
        assert "published" in public_diff.unified_diff
        assert "released" in public_diff.unified_diff

        assert admin_diff.previous_version is not None
        assert admin_diff.previous_version.semantic_version == "1.1.0"
        assert admin_diff.summary["from_version"] == "1.1.0"
        assert admin_diff.unified_diff is not None
        assert "draft" in admin_diff.unified_diff

        assert stored_version.diff_summary is not None
        assert stored_version.diff_summary["from_version"] == "1.1.0"
