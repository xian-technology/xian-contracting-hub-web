from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import (
    Category,
    Contract,
    ContractCategoryLink,
    ContractVersion,
    DeploymentHistory,
    DeploymentStatus,
    DeploymentTransport,
    Profile,
    PublicationStatus,
    Rating,
    Star,
    User,
)
from contracting_hub.services.developer_profiles import load_public_developer_profile_snapshot

NOW = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)


def _timestamp(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 12, 0, tzinfo=timezone.utc)


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def test_load_public_developer_profile_snapshot_returns_public_identity_metrics_and_contracts() -> (
    None
):
    engine = _build_engine()

    with Session(engine) as session:
        alice = User(email="alice@example.com", password_hash="hashed-password")
        alice.profile = Profile(
            username="alice",
            display_name="Alice Builder",
            bio="Builds treasury-safe Xian modules.",
            website_url="https://alice.dev",
            github_url="https://github.com/alice",
            xian_profile_url="https://xian.org/@alice",
        )
        viewer_one = User(email="viewer1@example.com", password_hash="hashed-password")
        viewer_one.profile = Profile(username="viewer1", display_name="Viewer One")
        viewer_two = User(email="viewer2@example.com", password_hash="hashed-password")
        viewer_two.profile = Profile(username="viewer2", display_name="Viewer Two")

        treasury = Category(slug="treasury", name="Treasury", sort_order=10)
        utilities = Category(slug="utilities", name="Utilities", sort_order=20)

        escrow = Contract(
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Escrow settlement primitives.",
            long_description="Escrow long description.",
            author=alice,
            status=PublicationStatus.PUBLISHED,
            featured=True,
            tags=["escrow", "treasury"],
            created_at=_timestamp(2, 1),
            updated_at=_timestamp(2, 20),
        )
        escrow_v1 = ContractVersion(
            contract=escrow,
            semantic_version="1.2.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def escrow():\n    return 'escrow'\n",
            source_hash_sha256="a" * 64,
            published_at=_timestamp(2, 20),
            created_at=_timestamp(2, 20),
            updated_at=_timestamp(2, 20),
        )
        escrow.latest_published_version = escrow_v1

        legacy = Contract(
            slug="legacy-vault",
            contract_name="con_legacy_vault",
            display_name="Legacy Vault",
            short_summary="Deprecated treasury vault release.",
            long_description="Legacy vault long description.",
            author=alice,
            status=PublicationStatus.DEPRECATED,
            featured=False,
            tags=["vault"],
            created_at=_timestamp(3, 1),
            updated_at=_timestamp(3, 2),
        )
        legacy_v1 = ContractVersion(
            contract=legacy,
            semantic_version="0.9.0",
            status=PublicationStatus.DEPRECATED,
            source_code="def legacy_vault():\n    return 'legacy'\n",
            source_hash_sha256="b" * 64,
            published_at=_timestamp(3, 2),
            created_at=_timestamp(3, 2),
            updated_at=_timestamp(3, 2),
        )
        legacy.latest_published_version = legacy_v1

        hidden = Contract(
            slug="hidden-draft",
            contract_name="con_hidden_draft",
            display_name="Hidden Draft",
            short_summary="Draft contract that must stay private.",
            long_description="Hidden draft long description.",
            author=alice,
            status=PublicationStatus.DRAFT,
            featured=False,
            tags=["draft"],
            created_at=_timestamp(3, 4),
            updated_at=_timestamp(3, 4),
        )
        hidden_v1 = ContractVersion(
            contract=hidden,
            semantic_version="0.1.0",
            status=PublicationStatus.DRAFT,
            source_code="def hidden():\n    return 'draft'\n",
            source_hash_sha256="c" * 64,
            created_at=_timestamp(3, 4),
            updated_at=_timestamp(3, 4),
        )

        session.add_all(
            [
                alice,
                viewer_one,
                viewer_two,
                treasury,
                utilities,
                escrow,
                escrow_v1,
                legacy,
                legacy_v1,
                hidden,
                hidden_v1,
                ContractCategoryLink(contract=escrow, category=treasury, is_primary=True),
                ContractCategoryLink(contract=legacy, category=utilities, is_primary=True),
                ContractCategoryLink(contract=hidden, category=treasury, is_primary=True),
            ]
        )
        session.flush()
        session.add_all(
            [
                Star(user=viewer_one, contract=escrow, created_at=_timestamp(2, 22)),
                Star(user=viewer_two, contract=escrow, created_at=_timestamp(2, 23)),
                Star(user=viewer_one, contract=legacy, created_at=_timestamp(3, 3)),
                Rating(user=viewer_one, contract=escrow, score=5, updated_at=_timestamp(2, 22)),
                Rating(user=viewer_two, contract=escrow, score=4, updated_at=_timestamp(2, 23)),
                Rating(user=viewer_one, contract=legacy, score=1, updated_at=_timestamp(3, 3)),
                DeploymentHistory(
                    user=viewer_one,
                    contract_version=escrow_v1,
                    playground_id="escrow-target",
                    status=DeploymentStatus.ACCEPTED,
                    transport=DeploymentTransport.DEEP_LINK,
                    initiated_at=_timestamp(2, 24),
                    completed_at=_timestamp(2, 24),
                    created_at=_timestamp(2, 24),
                    updated_at=_timestamp(2, 24),
                ),
                DeploymentHistory(
                    user=viewer_two,
                    contract_version=legacy_v1,
                    playground_id="legacy-target",
                    status=DeploymentStatus.ACCEPTED,
                    transport=DeploymentTransport.HTTP,
                    initiated_at=_timestamp(3, 3),
                    completed_at=_timestamp(3, 3),
                    created_at=_timestamp(3, 3),
                    updated_at=_timestamp(3, 3),
                ),
            ]
        )
        session.commit()

        snapshot = load_public_developer_profile_snapshot(
            session=session,
            username=" Alice ",
            activity_window_days=30,
            now=NOW,
        )

    assert snapshot.found is True
    assert snapshot.username == "alice"
    assert snapshot.display_name == "Alice Builder"
    assert snapshot.bio == "Builds treasury-safe Xian modules."
    assert snapshot.website_url == "https://alice.dev"
    assert snapshot.github_url == "https://github.com/alice"
    assert snapshot.xian_profile_url == "https://xian.org/@alice"
    assert snapshot.published_contract_count == 1
    assert snapshot.total_stars_received == 2
    assert snapshot.weighted_average_rating == 4.5
    assert snapshot.total_rating_count == 2
    assert snapshot.total_deployment_count == 1
    assert snapshot.recent_activity_count == 6
    assert [contract.slug for contract in snapshot.authored_contracts] == [
        "legacy-vault",
        "escrow",
    ]
    assert snapshot.authored_contracts[0].status is PublicationStatus.DEPRECATED
    assert snapshot.authored_contracts[1].primary_category_name == "Treasury"


def test_load_public_developer_profile_snapshot_returns_missing_for_unknown_username() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        snapshot = load_public_developer_profile_snapshot(
            session=session,
            username="missing",
            activity_window_days=30,
            now=NOW,
        )

    assert snapshot.found is False
    assert snapshot.username == "missing"
    assert snapshot.authored_contracts == ()
