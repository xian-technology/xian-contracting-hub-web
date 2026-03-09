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
    Rating,
    Star,
    User,
)
from contracting_hub.services import (
    ContractBrowseSort,
    create_contract_version,
    load_public_contract_browse_snapshot,
)


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


def _seed_browse_catalog(session: Session) -> None:
    alice = User(email="alice@example.com", password_hash="hashed-password")
    alice.profile = Profile(username="alice", display_name="Alice Validator")
    bob = User(email="bob@example.com", password_hash="hashed-password")
    bob.profile = Profile(username="bob", display_name="Bob Review")
    charlie = User(email="charlie@example.com", password_hash="hashed-password")
    charlie.profile = Profile(username="charlie", display_name="Charlie Curator")
    dana = User(email="dana@example.com", password_hash="hashed-password")
    dana.profile = Profile(username="dana", display_name="Dana Ops")

    defi = Category(slug="defi", name="DeFi", sort_order=10)
    security = Category(slug="security", name="Security", sort_order=20)
    tooling = Category(slug="tooling", name="Tooling", sort_order=30)

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Curated escrow settlement primitives.",
        long_description="Detailed escrow flows for reusable marketplace settlement.",
        author=alice,
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
        author=bob,
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
        tags=["treasury", "security"],
        updated_at=_timestamp(7),
    )
    draft_escrow = Contract(
        slug="draft-escrow",
        contract_name="con_draft_escrow",
        display_name="Draft Escrow",
        short_summary="Draft canary for browse visibility coverage.",
        long_description="Draft-only entry that should never appear publicly.",
        status=PublicationStatus.DRAFT,
        tags=["escrow", "draft"],
        updated_at=_timestamp(8),
    )

    session.add_all(
        [
            alice,
            bob,
            charlie,
            dana,
            defi,
            security,
            tooling,
            escrow,
            escrow_tools,
            vault,
            draft_escrow,
            ContractCategoryLink(contract=escrow, category=defi, is_primary=True),
            ContractCategoryLink(contract=escrow_tools, category=tooling, is_primary=True),
            ContractCategoryLink(contract=vault, category=security, is_primary=True),
            ContractCategoryLink(contract=draft_escrow, category=defi, is_primary=True),
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
    create_contract_version(
        session=session,
        contract_slug="draft-escrow",
        semantic_version="0.1.0",
        source_code="@export\ndef hidden_draft_canary():\n    return 'draft'\n",
        status=PublicationStatus.DRAFT,
    )

    session.add_all(
        [
            Star(user_id=bob.id, contract_id=escrow.id),
            Star(user_id=charlie.id, contract_id=escrow.id),
            Star(user_id=charlie.id, contract_id=escrow_tools.id),
            Star(user_id=alice.id, contract_id=vault.id),
            Star(user_id=bob.id, contract_id=vault.id),
            Star(user_id=charlie.id, contract_id=vault.id),
            Star(user_id=dana.id, contract_id=vault.id),
            Rating(user_id=bob.id, contract_id=escrow.id, score=5),
            Rating(user_id=charlie.id, contract_id=escrow.id, score=4),
            Rating(user_id=alice.id, contract_id=vault.id, score=5),
        ]
    )
    session.commit()


def test_browse_snapshot_uses_relevance_for_search_without_leaking_drafts() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_browse_catalog(session)

        snapshot = load_public_contract_browse_snapshot(session=session, query="  escrow  ")

        assert snapshot.query == "escrow"
        assert snapshot.sort is ContractBrowseSort.RELEVANCE
        assert [summary.slug for summary in snapshot.results] == ["escrow", "escrow-tools"]
        assert "draft-escrow" not in [summary.slug for summary in snapshot.results]


def test_browse_snapshot_supports_filters_sort_and_pagination() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_browse_catalog(session)

        filtered_snapshot = load_public_contract_browse_snapshot(
            session=session,
            category_slug="tooling",
            tag="utilities",
            sort="alphabetical",
        )
        paged_snapshot = load_public_contract_browse_snapshot(
            session=session,
            sort="most_starred",
            page=2,
            page_size=1,
        )

        assert [summary.slug for summary in filtered_snapshot.results] == ["escrow-tools"]
        assert paged_snapshot.sort is ContractBrowseSort.MOST_STARRED
        assert paged_snapshot.total_results == 3
        assert paged_snapshot.total_pages == 3
        assert paged_snapshot.current_page == 2
        assert [summary.slug for summary in paged_snapshot.results] == ["escrow"]
        assert [option.value for option in paged_snapshot.available_categories] == [
            "defi",
            "security",
            "tooling",
        ]
        assert paged_snapshot.available_tags[0].value == "escrow"
