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
    ContractRelation,
    ContractRelationType,
    ContractVersion,
    LintStatus,
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
            lint_status=LintStatus.WARN,
            lint_summary={
                "status": "warn",
                "issue_count": 2,
                "error_count": 0,
                "warning_count": 1,
                "info_count": 1,
            },
            lint_results=[
                {
                    "message": "Prefer explicit timeout docs for claim paths.",
                    "severity": "warning",
                    "position": {"line": 12, "column": 4},
                },
                {
                    "message": "Generated metadata was normalized for display.",
                    "severity": "info",
                },
            ],
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
    assert snapshot.selected_version_lint.status is LintStatus.WARN
    assert snapshot.selected_version_lint.issue_count == 2
    assert snapshot.selected_version_lint.warning_count == 1
    assert snapshot.selected_version_lint.info_count == 1
    assert snapshot.selected_version_lint.findings[0].message == (
        "Prefer explicit timeout docs for claim paths."
    )
    assert snapshot.selected_version_lint.findings[0].line == 12
    assert snapshot.selected_version_lint.findings[0].column == 4
    assert snapshot.selected_version_lint.findings[1].severity == "info"
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
            lint_status=LintStatus.PASS,
            lint_summary={
                "status": "pass",
                "issue_count": 0,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0,
            },
            lint_results=[],
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
            lint_status=LintStatus.FAIL,
            lint_summary={
                "status": "fail",
                "issue_count": 1,
                "error_count": 1,
                "warning_count": 0,
                "info_count": 0,
            },
            lint_results=[
                {
                    "message": "Missing required decorator for historical release.",
                    "severity": "error",
                    "position": {"line": 1, "column": 1},
                }
            ],
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
    assert snapshot.selected_version_lint.status is LintStatus.FAIL
    assert snapshot.selected_version_lint.error_count == 1
    assert snapshot.selected_version_lint.findings[0].message == (
        "Missing required decorator for historical release."
    )
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


def test_load_public_contract_detail_snapshot_includes_visible_related_contracts_only() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        author = User(email="alice@example.com", password_hash="hashed-password")
        author.profile = Profile(username="alice", display_name="Alice Builder")
        example_author = User(email="bob@example.com", password_hash="hashed-password")
        example_author.profile = Profile(username="bob", display_name="Bob Example")
        draft_author = User(email="carol@example.com", password_hash="hashed-password")
        draft_author.profile = Profile(username="carol", display_name="Carol Draft")

        treasury = Category(slug="treasury", name="Treasury", sort_order=10)
        guides = Category(slug="guides", name="Guides", sort_order=20)

        contract = Contract(
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Curated escrow primitives for Xian treasury flows.",
            long_description="Protects multi-party settlements.",
            author=author,
            status=PublicationStatus.PUBLISHED,
            created_at=_timestamp(1),
            updated_at=_timestamp(6),
        )
        contract_release = ContractVersion(
            contract=contract,
            semantic_version="1.2.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'escrow'\n",
            source_hash_sha256="1" * 64,
            published_at=_timestamp(5),
            created_at=_timestamp(5),
            updated_at=_timestamp(5),
        )
        contract.latest_published_version = contract_release

        companion = Contract(
            slug="vault",
            contract_name="con_vault",
            display_name="Vault",
            short_summary="Shared treasury settlement helpers.",
            long_description="Supports treasury release flows.",
            author_label="Treasury Team",
            status=PublicationStatus.PUBLISHED,
            created_at=_timestamp(2),
            updated_at=_timestamp(5),
        )
        companion_release = ContractVersion(
            contract=companion,
            semantic_version="0.8.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'vault'\n",
            source_hash_sha256="2" * 64,
            published_at=_timestamp(4),
            created_at=_timestamp(4),
            updated_at=_timestamp(4),
        )
        companion.latest_published_version = companion_release

        example = Contract(
            slug="escrow-example",
            contract_name="con_escrow_example",
            display_name="Escrow Example",
            short_summary="Reference walkthrough for escrow consumers.",
            long_description="Shows one end-to-end escrow integration.",
            author=example_author,
            status=PublicationStatus.PUBLISHED,
            created_at=_timestamp(3),
            updated_at=_timestamp(6),
        )
        example_release = ContractVersion(
            contract=example,
            semantic_version="0.3.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'example'\n",
            source_hash_sha256="3" * 64,
            published_at=_timestamp(5),
            created_at=_timestamp(5),
            updated_at=_timestamp(5),
        )
        example.latest_published_version = example_release

        hidden_outgoing = Contract(
            slug="draft-helper",
            contract_name="con_draft_helper",
            display_name="Draft Helper",
            short_summary="Hidden draft dependency.",
            long_description="This draft relation should not leak publicly.",
            author=draft_author,
            status=PublicationStatus.DRAFT,
            created_at=_timestamp(4),
            updated_at=_timestamp(6),
        )
        hidden_outgoing_release = ContractVersion(
            contract=hidden_outgoing,
            semantic_version="0.1.0",
            status=PublicationStatus.DRAFT,
            source_code="def seed():\n    return 'draft helper'\n",
            source_hash_sha256="4" * 64,
            created_at=_timestamp(6),
            updated_at=_timestamp(6),
        )

        hidden_incoming = Contract(
            slug="draft-example",
            contract_name="con_draft_example",
            display_name="Draft Example",
            short_summary="Hidden draft incoming reference.",
            long_description="This draft incoming relation should not leak publicly.",
            status=PublicationStatus.DRAFT,
            created_at=_timestamp(4),
            updated_at=_timestamp(6),
        )
        hidden_incoming_release = ContractVersion(
            contract=hidden_incoming,
            semantic_version="0.2.0",
            status=PublicationStatus.DRAFT,
            source_code="def seed():\n    return 'draft example'\n",
            source_hash_sha256="5" * 64,
            created_at=_timestamp(6),
            updated_at=_timestamp(6),
        )

        session.add_all(
            [
                treasury,
                guides,
                author,
                example_author,
                draft_author,
                contract,
                contract_release,
                companion,
                companion_release,
                example,
                example_release,
                hidden_outgoing,
                hidden_outgoing_release,
                hidden_incoming,
                hidden_incoming_release,
                ContractCategoryLink(
                    contract=contract,
                    category=treasury,
                    is_primary=True,
                    sort_order=0,
                ),
                ContractCategoryLink(
                    contract=companion,
                    category=treasury,
                    is_primary=True,
                    sort_order=0,
                ),
                ContractCategoryLink(
                    contract=example,
                    category=guides,
                    is_primary=True,
                    sort_order=0,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                ContractRelation(
                    source_contract=contract,
                    target_contract=companion,
                    relation_type=ContractRelationType.COMPANION,
                ),
                ContractRelation(
                    source_contract=contract,
                    target_contract=hidden_outgoing,
                    relation_type=ContractRelationType.DEPENDS_ON,
                ),
                ContractRelation(
                    source_contract=example,
                    target_contract=contract,
                    relation_type=ContractRelationType.EXAMPLE_FOR,
                ),
                ContractRelation(
                    source_contract=hidden_incoming,
                    target_contract=contract,
                    relation_type=ContractRelationType.SUPERSEDES,
                ),
            ]
        )
        session.commit()

        snapshot = load_public_contract_detail_snapshot(session=session, slug="escrow")

    assert [relation.slug for relation in snapshot.outgoing_related_contracts] == ["vault"]
    assert snapshot.outgoing_related_contracts[0].relation_type is ContractRelationType.COMPANION
    assert snapshot.outgoing_related_contracts[0].relation_label == "Companion"
    assert snapshot.outgoing_related_contracts[0].contract_name == "con_vault"
    assert snapshot.outgoing_related_contracts[0].author_name == "Treasury Team"
    assert snapshot.outgoing_related_contracts[0].primary_category_name == "Treasury"
    assert snapshot.outgoing_related_contracts[0].latest_version_label == "Latest 0.8.0"

    assert [relation.slug for relation in snapshot.incoming_related_contracts] == ["escrow-example"]
    assert snapshot.incoming_related_contracts[0].relation_type is (
        ContractRelationType.EXAMPLE_FOR
    )
    assert snapshot.incoming_related_contracts[0].relation_label == "Example for"
    assert snapshot.incoming_related_contracts[0].display_name == "Escrow Example"
    assert snapshot.incoming_related_contracts[0].author_name == "Bob Example"
    assert snapshot.incoming_related_contracts[0].primary_category_name == "Guides"
    assert snapshot.incoming_related_contracts[0].latest_version_label == "Latest 0.3.0"


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
