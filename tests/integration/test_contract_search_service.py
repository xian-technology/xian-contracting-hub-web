from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import (
    Category,
    Contract,
    ContractCategoryLink,
    Profile,
    PublicationStatus,
    User,
)
from contracting_hub.services import create_contract_version, search_contract_catalog


def _timestamp(day: int) -> datetime:
    return datetime(2026, 2, day, 12, 0, tzinfo=timezone.utc)


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def _seed_search_catalog(session: Session) -> None:
    author = User(email="alice@example.com", password_hash="hashed-password")
    author.profile = Profile(username="alice", display_name="Alice Validator")
    reviewer = User(email="bob@example.com", password_hash="hashed-password")
    reviewer.profile = Profile(username="bob", display_name="Bob Review")

    defi = Category(slug="defi", name="DeFi", sort_order=10)
    security = Category(slug="security", name="Security", sort_order=20)

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Curated escrow settlement primitives.",
        long_description="Detailed escrow flows for reusable marketplace settlement.",
        author=author,
        status=PublicationStatus.PUBLISHED,
        featured=True,
        tags=["escrow", "settlement"],
        updated_at=_timestamp(4),
    )
    escrow_tools = Contract(
        slug="escrow-tools",
        contract_name="con_escrow_tools",
        display_name="Escrow Toolkit",
        short_summary="Tooling for escrow audits.",
        long_description="Support utilities for inspecting escrow state transitions.",
        author=reviewer,
        status=PublicationStatus.PUBLISHED,
        tags=["escrow", "utilities"],
        updated_at=_timestamp(6),
    )
    vault = Contract(
        slug="vault",
        contract_name="con_vault",
        display_name="Vault",
        short_summary="Treasury vault reference.",
        long_description="Security-focused custody contract.",
        author_label="Core Team",
        status=PublicationStatus.PUBLISHED,
        tags=["treasury"],
        updated_at=_timestamp(5),
    )

    session.add_all(
        [
            defi,
            security,
            ContractCategoryLink(contract=escrow, category=defi, is_primary=True),
            ContractCategoryLink(contract=vault, category=security, is_primary=True),
            escrow,
            escrow_tools,
            vault,
        ]
    )
    session.commit()

    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="1.0.0",
        source_code="@export\ndef settle_release_path():\n    return 'escrow'\n",
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="escrow-tools",
        semantic_version="1.0.0",
        source_code="@export\ndef inspect_escrow_state():\n    return 'tools'\n",
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="vault",
        semantic_version="1.0.0",
        source_code="@export\ndef treasury_guard_marker():\n    return 'vault'\n",
        status=PublicationStatus.PUBLISHED,
    )


def test_search_contract_catalog_matches_ranked_metadata_fields() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_search_catalog(session)

        escrow_results = search_contract_catalog(session=session, query="escrow")
        author_results = search_contract_catalog(session=session, query="alice")
        category_results = search_contract_catalog(session=session, query="defi")
        tag_results = search_contract_catalog(session=session, query="settlement")
        source_results = search_contract_catalog(session=session, query="treasury_guard_marker")

        assert [result.contract.slug for result in escrow_results[:2]] == [
            "escrow",
            "escrow-tools",
        ]
        assert [result.contract.slug for result in author_results] == ["escrow"]
        assert [result.contract.slug for result in category_results] == ["escrow"]
        assert [result.contract.slug for result in tag_results] == ["escrow"]
        assert [result.contract.slug for result in source_results] == ["vault"]


def test_create_contract_version_rebuilds_index_without_leaking_draft_source() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = Contract(
            slug="timelock",
            contract_name="con_timelock",
            display_name="Timelock",
            short_summary="Delayed execution contract.",
            long_description="Time-based execution guard.",
            status=PublicationStatus.PUBLISHED,
            tags=["governance"],
        )
        session.add(contract)
        session.commit()

        initial_results = search_contract_catalog(session=session, query="released_route_marker")
        assert initial_results == []

        create_contract_version(
            session=session,
            contract_slug="timelock",
            semantic_version="1.0.0",
            source_code="@export\ndef released_route_marker():\n    return 'timelock'\n",
            status=PublicationStatus.PUBLISHED,
        )

        published_results = search_contract_catalog(session=session, query="released_route_marker")

        create_contract_version(
            session=session,
            contract_slug="timelock",
            semantic_version="1.1.0",
            source_code="@export\ndef draft_only_route_marker():\n    return 'draft'\n",
            status=PublicationStatus.DRAFT,
        )

        draft_results = search_contract_catalog(session=session, query="draft_only_route_marker")
        refreshed_published_results = search_contract_catalog(
            session=session,
            query="released_route_marker",
        )

        assert [result.contract.slug for result in published_results] == ["timelock"]
        assert draft_results == []
        assert [result.contract.slug for result in refreshed_published_results] == ["timelock"]
