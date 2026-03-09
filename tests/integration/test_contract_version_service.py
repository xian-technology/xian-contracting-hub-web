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


def _valid_source(label: str) -> str:
    return f"@export\ndef seed():\n    return {label!r}\n"


def test_create_contract_version_persists_changelog_hash_and_public_pointer() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)

        version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.0.0",
            source_code=_valid_source("escrow"),
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
            "18c680b9ee66461afbc9f45ea4aeaca83889006193ccfb2ddd7c7a240bee9547"
        )
        assert stored_version.previous_version_id is None
        assert stored_version.lint_status.value == "pass"
        assert stored_version.lint_summary == {
            "status": "pass",
            "issue_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
        }
        assert stored_version.lint_results == []
        assert stored_version.diff_summary == {
            "from_version": None,
            "to_version": "1.0.0",
            "has_previous_version": False,
            "has_changes": False,
            "added_lines": 0,
            "removed_lines": 0,
            "line_delta": 3,
            "from_line_count": 0,
            "to_line_count": 3,
            "hunk_count": 0,
            "context_lines": 3,
        }
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
            source_code=_valid_source("published"),
            status=PublicationStatus.PUBLISHED,
        )

        draft_version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.1.0",
            source_code=_valid_source("draft"),
            changelog="   ",
        )

        stored_contract = session.exec(select(Contract).where(Contract.id == contract.id)).one()

        assert draft_version.status is PublicationStatus.DRAFT
        assert draft_version.previous_version_id == published_version.id
        assert draft_version.diff_summary == {
            "from_version": "1.0.0",
            "to_version": "1.1.0",
            "has_previous_version": True,
            "has_changes": True,
            "added_lines": 1,
            "removed_lines": 1,
            "line_delta": 0,
            "from_line_count": 3,
            "to_line_count": 3,
            "hunk_count": 1,
            "context_lines": 3,
        }
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
            source_code=_valid_source("one"),
            status=PublicationStatus.PUBLISHED,
            published_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        )
        create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.1.0",
            source_code=_valid_source("draft"),
        )

        published_release = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="2.0.0",
            source_code=_valid_source("two"),
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
            source_code=_valid_source("original"),
            changelog="Original release.",
            status=PublicationStatus.PUBLISHED,
        )

        with pytest.raises(ContractVersionServiceError) as error:
            create_contract_version(
                session=session,
                contract_slug=contract.slug,
                semantic_version="1.0.0",
                source_code=_valid_source("replacement"),
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
        assert stored_versions[0].source_code == _valid_source("original")
        assert stored_versions[0].changelog == "Original release."


def test_create_contract_version_persists_failing_lint_results_for_draft_versions() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)

        draft_version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="1.0.0",
            source_code="def seed():\n    return 'draft'\n",
        )

        stored_version = session.exec(
            select(ContractVersion).where(ContractVersion.id == draft_version.id)
        ).one()

        assert stored_version.lint_status.value == "fail"
        assert stored_version.lint_summary == {
            "status": "fail",
            "issue_count": 1,
            "error_count": 1,
            "warning_count": 0,
            "info_count": 0,
        }
        assert stored_version.lint_results == [
            {
                "message": "S13- No valid contracting decorator found",
                "severity": "error",
                "position": {"line": 0, "column": 0},
            }
        ]


def test_create_contract_version_rejects_publishing_invalid_lint_results() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)

        with pytest.raises(ContractVersionServiceError) as error:
            create_contract_version(
                session=session,
                contract_slug=contract.slug,
                semantic_version="1.0.0",
                source_code="def seed():\n    return 'draft'\n",
                status=PublicationStatus.PUBLISHED,
            )

        stored_versions = session.exec(
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract.id)
            .order_by(ContractVersion.id.asc())
        ).all()

        assert error.value.code is ContractVersionServiceErrorCode.LINT_FAILURE
        assert error.value.field == "source_code"
        assert error.value.details["lint_status"] == "fail"
        assert error.value.details["lint_summary"]["error_count"] == 1
        assert stored_versions == []
