from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import (
    Category,
    Contract,
    ContractCategoryLink,
    ContractNetwork,
    ContractVersion,
    Profile,
    PublicationStatus,
    Rating,
    Star,
    User,
)
from contracting_hub.services.contract_detail import load_public_contract_detail_snapshot


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


def test_load_public_contract_detail_snapshot_returns_header_ready_metadata() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        author = User(email="alice@example.com", password_hash="hashed-password")
        author.profile = Profile(
            username="alice",
            display_name="Alice Builder",
            bio="Builds escrow flows for treasury and settlement teams.",
            website_url="https://alice.dev",
            github_url="https://github.com/alice",
            xian_profile_url="https://xian.org/@alice",
        )
        reviewer = User(email="bob@example.com", password_hash="hashed-password")
        reviewer.profile = Profile(username="bob", display_name="Bob")
        operator = User(email="carol@example.com", password_hash="hashed-password")
        operator.profile = Profile(username="carol", display_name="Carol")

        defi = Category(slug="defi", name="DeFi", sort_order=10)
        treasury = Category(slug="treasury", name="Treasury", sort_order=20)

        contract = Contract(
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Curated escrow primitives for Xian treasury flows.",
            long_description=(
                "Protects multi-party settlements, staged claims, and time-boxed releases."
            ),
            author=author,
            status=PublicationStatus.PUBLISHED,
            featured=True,
            license_name="MIT",
            documentation_url="https://docs.example.com/escrow",
            source_repository_url="https://github.com/example/escrow",
            network=ContractNetwork.SANDBOX,
            tags=["escrow", "treasury"],
            created_at=_timestamp(1),
            updated_at=_timestamp(6),
        )
        published_version = ContractVersion(
            contract=contract,
            semantic_version="1.2.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'escrow'\n",
            source_hash_sha256="a" * 64,
            changelog="Add settlement timeouts.",
            published_at=_timestamp(5),
            created_at=_timestamp(5),
            updated_at=_timestamp(5),
        )
        deprecated_version = ContractVersion(
            contract=contract,
            semantic_version="1.1.0",
            status=PublicationStatus.DEPRECATED,
            source_code="def seed():\n    return 'legacy escrow'\n",
            source_hash_sha256="b" * 64,
            changelog="Legacy settlement release.",
            published_at=_timestamp(4),
            created_at=_timestamp(4),
            updated_at=_timestamp(4),
        )
        draft_version = ContractVersion(
            contract=contract,
            semantic_version="1.3.0",
            status=PublicationStatus.DRAFT,
            source_code="def seed():\n    return 'draft'\n",
            source_hash_sha256="c" * 64,
            changelog="Draft follow-up.",
            created_at=_timestamp(6),
            updated_at=_timestamp(6),
        )
        published_version.previous_version = deprecated_version
        draft_version.previous_version = published_version
        contract.latest_published_version = published_version

        session.add_all(
            [
                defi,
                treasury,
                author,
                reviewer,
                operator,
                contract,
                published_version,
                deprecated_version,
                draft_version,
                ContractCategoryLink(
                    contract=contract,
                    category=defi,
                    is_primary=True,
                    sort_order=0,
                ),
                ContractCategoryLink(
                    contract=contract,
                    category=treasury,
                    is_primary=False,
                    sort_order=1,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                Star(user=author, contract=contract),
                Star(user=reviewer, contract=contract),
                Star(user=operator, contract=contract),
                Rating(user=reviewer, contract=contract, score=5, note="Strong release."),
                Rating(user=operator, contract=contract, score=4, note="Clear API."),
            ]
        )
        session.commit()

        snapshot = load_public_contract_detail_snapshot(session=session, slug="escrow")

    assert snapshot.found is True
    assert snapshot.slug == "escrow"
    assert snapshot.display_name == "Escrow"
    assert snapshot.contract_name == "con_escrow"
    assert snapshot.contract_status is PublicationStatus.PUBLISHED
    assert snapshot.featured is True
    assert snapshot.network is ContractNetwork.SANDBOX
    assert snapshot.license_name == "MIT"
    assert snapshot.documentation_url == "https://docs.example.com/escrow"
    assert snapshot.source_repository_url == "https://github.com/example/escrow"
    assert snapshot.author.display_name == "Alice Builder"
    assert snapshot.author.username == "alice"
    assert snapshot.author.github_url == "https://github.com/alice"
    assert snapshot.primary_category_name == "DeFi"
    assert snapshot.category_names == ("DeFi", "Treasury")
    assert snapshot.tag_names == ("escrow", "treasury")
    assert snapshot.selected_version == "1.2.0"
    assert snapshot.selected_version_status is PublicationStatus.PUBLISHED
    assert snapshot.selected_version_source_code == "def seed():\n    return 'escrow'\n"
    assert snapshot.selected_version_changelog == "Add settlement timeouts."
    assert snapshot.selected_version_is_latest_public is True
    assert snapshot.selected_version_diff.from_version == "1.1.0"
    assert snapshot.selected_version_diff.to_version == "1.2.0"
    assert snapshot.selected_version_diff.has_previous_version is True
    assert snapshot.selected_version_diff.has_changes is True
    assert snapshot.selected_version_diff.unified_diff is not None
    assert "legacy escrow" in snapshot.selected_version_diff.unified_diff
    assert "escrow" in snapshot.selected_version_diff.unified_diff
    assert [version.semantic_version for version in snapshot.available_versions] == [
        "1.2.0",
        "1.1.0",
    ]
    assert snapshot.available_versions[0].is_latest_public is True
    assert snapshot.available_versions[1].status is PublicationStatus.DEPRECATED
    assert snapshot.star_count == 3
    assert snapshot.rating_count == 2
    assert snapshot.average_rating == pytest.approx(4.5)


def test_load_public_contract_detail_snapshot_selects_requested_visible_version() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = Contract(
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Curated escrow primitives for Xian treasury flows.",
            long_description="Protects multi-party settlements.",
            status=PublicationStatus.PUBLISHED,
            created_at=_timestamp(1),
            updated_at=_timestamp(6),
        )
        current_version = ContractVersion(
            contract=contract,
            semantic_version="1.2.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'escrow'\n",
            source_hash_sha256="d" * 64,
            changelog="Current public release.",
            published_at=_timestamp(5),
            created_at=_timestamp(5),
            updated_at=_timestamp(5),
        )
        previous_version = ContractVersion(
            contract=contract,
            semantic_version="1.1.0",
            status=PublicationStatus.DEPRECATED,
            source_code="def seed():\n    return 'legacy escrow'\n",
            source_hash_sha256="e" * 64,
            changelog="Legacy release.",
            published_at=_timestamp(4),
            created_at=_timestamp(4),
            updated_at=_timestamp(4),
        )
        draft_version = ContractVersion(
            contract=contract,
            semantic_version="1.3.0",
            status=PublicationStatus.DRAFT,
            source_code="def seed():\n    return 'draft escrow'\n",
            source_hash_sha256="f" * 64,
            changelog="Draft follow-up.",
            created_at=_timestamp(6),
            updated_at=_timestamp(6),
        )
        current_version.previous_version = previous_version
        draft_version.previous_version = current_version
        contract.latest_published_version = current_version

        session.add_all([contract, current_version, previous_version, draft_version])
        session.commit()

        snapshot = load_public_contract_detail_snapshot(
            session=session,
            slug="escrow",
            semantic_version="1.1.0",
        )

    assert snapshot.found is True
    assert snapshot.selected_version == "1.1.0"
    assert snapshot.selected_version_status is PublicationStatus.DEPRECATED
    assert snapshot.selected_version_source_code == "def seed():\n    return 'legacy escrow'\n"
    assert snapshot.selected_version_changelog == "Legacy release."
    assert snapshot.selected_version_is_latest_public is False
    assert [version.semantic_version for version in snapshot.available_versions] == [
        "1.2.0",
        "1.1.0",
    ]


def test_load_public_contract_detail_snapshot_builds_diff_from_previous_visible_release() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = Contract(
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Curated escrow primitives for Xian treasury flows.",
            long_description="Protects multi-party settlements.",
            status=PublicationStatus.PUBLISHED,
            created_at=_timestamp(1),
            updated_at=_timestamp(6),
        )
        first_release = ContractVersion(
            contract=contract,
            semantic_version="1.0.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'published'\n",
            source_hash_sha256="a" * 64,
            changelog="Initial public release.",
            published_at=_timestamp(2),
            created_at=_timestamp(2),
            updated_at=_timestamp(2),
        )
        draft_release = ContractVersion(
            contract=contract,
            semantic_version="1.1.0",
            status=PublicationStatus.DRAFT,
            source_code="def seed():\n    return 'draft'\n",
            source_hash_sha256="b" * 64,
            changelog="Draft follow-up.",
            created_at=_timestamp(4),
            updated_at=_timestamp(4),
        )
        current_release = ContractVersion(
            contract=contract,
            semantic_version="2.0.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'released'\n",
            source_hash_sha256="c" * 64,
            changelog="Current public release.",
            published_at=_timestamp(5),
            created_at=_timestamp(5),
            updated_at=_timestamp(5),
        )
        draft_release.previous_version = first_release
        current_release.previous_version = draft_release
        contract.latest_published_version = current_release

        session.add_all([contract, first_release, draft_release, current_release])
        session.commit()

        snapshot = load_public_contract_detail_snapshot(session=session, slug="escrow")

    assert snapshot.selected_version == "2.0.0"
    assert snapshot.selected_version_diff.from_version == "1.0.0"
    assert snapshot.selected_version_diff.to_version == "2.0.0"
    assert snapshot.selected_version_diff.has_previous_version is True
    assert snapshot.selected_version_diff.unified_diff is not None
    assert "draft" not in snapshot.selected_version_diff.unified_diff
    assert "published" in snapshot.selected_version_diff.unified_diff
    assert "released" in snapshot.selected_version_diff.unified_diff


def test_load_public_contract_detail_snapshot_hides_non_public_contracts() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = Contract(
            slug="draft-contract",
            contract_name="con_draft_contract",
            display_name="Draft Contract",
            short_summary="Hidden draft entry.",
            long_description="This should not appear publicly.",
            status=PublicationStatus.DRAFT,
            created_at=_timestamp(1),
            updated_at=_timestamp(1),
        )
        contract_version = ContractVersion(
            contract=contract,
            semantic_version="0.1.0",
            status=PublicationStatus.DRAFT,
            source_code="def seed():\n    return 'draft'\n",
            source_hash_sha256="c" * 64,
            created_at=_timestamp(1),
            updated_at=_timestamp(1),
        )
        session.add_all([contract, contract_version])
        session.commit()

        snapshot = load_public_contract_detail_snapshot(session=session, slug="draft-contract")

    assert snapshot.found is False
    assert snapshot.slug == "draft-contract"
