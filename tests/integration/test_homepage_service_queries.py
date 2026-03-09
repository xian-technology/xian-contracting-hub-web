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
from contracting_hub.services.homepage import load_public_home_page_snapshot


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


def _seed_homepage_catalog(session: Session) -> None:
    alice = User(email="alice@example.com", password_hash="pw")
    alice.profile = Profile(username="alice", display_name="Alice")
    bob = User(email="bob@example.com", password_hash="pw")
    bob.profile = Profile(username="bob", display_name="Bob")
    carol = User(email="carol@example.com", password_hash="pw")
    carol.profile = Profile(username="carol", display_name="Carol")
    dan = User(email="dan@example.com", password_hash="pw")
    dan.profile = Profile(username="dan", display_name="Dan")

    security = Category(slug="security", name="Security", sort_order=10)
    treasury = Category(slug="treasury", name="Treasury", sort_order=20)
    governance = Category(slug="governance", name="Governance", sort_order=30)
    utilities = Category(slug="utilities", name="Utilities", sort_order=40)

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Escrow primitives for marketplace flows.",
        long_description="Escrow long description.",
        author=alice,
        status=PublicationStatus.PUBLISHED,
        featured=True,
        tags=["escrow", "marketplace"],
        created_at=_timestamp(1),
        updated_at=_timestamp(5),
    )
    escrow_v1 = ContractVersion(
        contract=escrow,
        semantic_version="1.0.0",
        status=PublicationStatus.PUBLISHED,
        source_code="def seed():\n    return 'escrow'\n",
        source_hash_sha256="a" * 64,
        published_at=_timestamp(5),
        created_at=_timestamp(5),
        updated_at=_timestamp(5),
    )
    escrow.latest_published_version = escrow_v1

    vault = Contract(
        slug="vault",
        contract_name="con_vault",
        display_name="Vault",
        short_summary="Treasury vault with multi-party controls.",
        long_description="Vault long description.",
        author=bob,
        status=PublicationStatus.PUBLISHED,
        featured=False,
        tags=["vault", "treasury"],
        created_at=_timestamp(2),
        updated_at=_timestamp(9),
    )
    vault_v2 = ContractVersion(
        contract=vault,
        semantic_version="2.1.0",
        status=PublicationStatus.PUBLISHED,
        source_code="def seed():\n    return 'vault'\n",
        source_hash_sha256="b" * 64,
        published_at=_timestamp(9),
        created_at=_timestamp(9),
        updated_at=_timestamp(9),
    )
    vault.latest_published_version = vault_v2

    oracle = Contract(
        slug="oracle",
        contract_name="con_oracle",
        display_name="Oracle",
        short_summary="Off-chain oracle ingress for curated feeds.",
        long_description="Oracle long description.",
        author_label="Core Team",
        status=PublicationStatus.PUBLISHED,
        featured=True,
        tags=["oracle", "feeds"],
        created_at=_timestamp(3),
        updated_at=_timestamp(7),
    )
    oracle_v1 = ContractVersion(
        contract=oracle,
        semantic_version="1.4.0",
        status=PublicationStatus.PUBLISHED,
        source_code="def seed():\n    return 'oracle'\n",
        source_hash_sha256="c" * 64,
        published_at=_timestamp(7),
        created_at=_timestamp(7),
        updated_at=_timestamp(7),
    )
    oracle.latest_published_version = oracle_v1

    utility = Contract(
        slug="utility",
        contract_name="con_utility",
        display_name="Utility",
        short_summary="Shared helper utilities for companion contracts.",
        long_description="Utility long description.",
        author=carol,
        status=PublicationStatus.DEPRECATED,
        featured=False,
        tags=["helpers"],
        created_at=_timestamp(4),
        updated_at=_timestamp(8),
    )
    utility_v1 = ContractVersion(
        contract=utility,
        semantic_version="0.9.0",
        status=PublicationStatus.DEPRECATED,
        source_code="def seed():\n    return 'utility'\n",
        source_hash_sha256="d" * 64,
        published_at=_timestamp(8),
        created_at=_timestamp(8),
        updated_at=_timestamp(8),
    )
    utility.latest_published_version = utility_v1

    hidden = Contract(
        slug="hidden-draft",
        contract_name="con_hidden_draft",
        display_name="Hidden Draft",
        short_summary="Draft contract that must stay private.",
        long_description="Hidden draft long description.",
        author=dan,
        status=PublicationStatus.DRAFT,
        featured=True,
        tags=["draft"],
        created_at=_timestamp(5),
        updated_at=_timestamp(12),
    )
    hidden_v1 = ContractVersion(
        contract=hidden,
        semantic_version="0.1.0",
        status=PublicationStatus.DRAFT,
        source_code="def seed():\n    return 'hidden'\n",
        source_hash_sha256="e" * 64,
        created_at=_timestamp(12),
        updated_at=_timestamp(12),
    )

    viewers = [
        User(email=f"viewer{index}@example.com", password_hash="pw") for index in range(1, 6)
    ]
    for index, viewer in enumerate(viewers, start=1):
        viewer.profile = Profile(username=f"viewer{index}", display_name=f"Viewer {index}")

    session.add_all(
        [
            alice,
            bob,
            carol,
            dan,
            *viewers,
            security,
            treasury,
            governance,
            utilities,
            ContractCategoryLink(contract=escrow, category=security, is_primary=True),
            ContractCategoryLink(contract=vault, category=treasury, is_primary=True),
            ContractCategoryLink(contract=oracle, category=governance, is_primary=True),
            ContractCategoryLink(contract=utility, category=utilities, is_primary=True),
            ContractCategoryLink(contract=hidden, category=security, is_primary=True),
            escrow,
            escrow_v1,
            vault,
            vault_v2,
            oracle,
            oracle_v1,
            utility,
            utility_v1,
            hidden,
            hidden_v1,
        ]
    )
    session.flush()

    session.add_all(
        [
            Star(
                user=viewers[0],
                contract=vault,
                created_at=_timestamp(9),
                updated_at=_timestamp(9),
            ),
            Star(
                user=viewers[1],
                contract=vault,
                created_at=_timestamp(9),
                updated_at=_timestamp(9),
            ),
            Star(
                user=viewers[2],
                contract=vault,
                created_at=_timestamp(9),
                updated_at=_timestamp(9),
            ),
            Star(
                user=viewers[0],
                contract=oracle,
                created_at=_timestamp(7),
                updated_at=_timestamp(7),
            ),
            Star(
                user=viewers[1],
                contract=oracle,
                created_at=_timestamp(7),
                updated_at=_timestamp(7),
            ),
            Star(
                user=viewers[2],
                contract=utility,
                created_at=_timestamp(8),
                updated_at=_timestamp(8),
            ),
            Star(
                user=viewers[3],
                contract=utility,
                created_at=_timestamp(8),
                updated_at=_timestamp(8),
            ),
            Star(
                user=viewers[4],
                contract=escrow,
                created_at=_timestamp(5),
                updated_at=_timestamp(5),
            ),
            Star(
                user=viewers[0],
                contract=hidden,
                created_at=_timestamp(12),
                updated_at=_timestamp(12),
            ),
            Rating(user=viewers[0], contract=vault, score=4, updated_at=_timestamp(9)),
            Rating(user=viewers[1], contract=vault, score=5, updated_at=_timestamp(9)),
            Rating(user=viewers[0], contract=oracle, score=5, updated_at=_timestamp(7)),
            Rating(user=viewers[2], contract=utility, score=4, updated_at=_timestamp(8)),
            Rating(user=viewers[3], contract=hidden, score=5, updated_at=_timestamp(12)),
            DeploymentHistory(
                user=viewers[0],
                contract_version=vault_v2,
                playground_id="vault-prod",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.HTTP,
                request_payload={"slug": "vault"},
                response_payload={"ok": True},
                initiated_at=_timestamp(10),
                completed_at=_timestamp(10),
            ),
            DeploymentHistory(
                user=viewers[1],
                contract_version=vault_v2,
                playground_id="vault-failed",
                status=DeploymentStatus.FAILED,
                transport=DeploymentTransport.HTTP,
                request_payload={"slug": "vault"},
                error_payload={"ok": False},
                initiated_at=_timestamp(11),
                completed_at=_timestamp(11),
            ),
            DeploymentHistory(
                user=viewers[2],
                contract_version=oracle_v1,
                playground_id="oracle-live",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.DEEP_LINK,
                request_payload={"slug": "oracle"},
                response_payload={"ok": True},
                initiated_at=_timestamp(8),
                completed_at=_timestamp(8),
            ),
            DeploymentHistory(
                user=viewers[3],
                contract_version=utility_v1,
                playground_id="utility-live",
                status=DeploymentStatus.REDIRECT_REQUIRED,
                transport=DeploymentTransport.DEEP_LINK,
                request_payload={"slug": "utility"},
                response_payload={"ok": True},
                initiated_at=_timestamp(6),
                completed_at=_timestamp(6),
            ),
            DeploymentHistory(
                user=viewers[4],
                contract_version=hidden_v1,
                playground_id="hidden-live",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.HTTP,
                request_payload={"slug": "hidden"},
                response_payload={"ok": True},
                initiated_at=_timestamp(12),
                completed_at=_timestamp(12),
            ),
        ]
    )
    session.commit()


def test_load_public_home_page_snapshot_returns_visible_sections_in_expected_order() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_homepage_catalog(session)

        snapshot = load_public_home_page_snapshot(session=session)

        assert [summary.slug for summary in snapshot.featured_contracts] == ["oracle", "escrow"]
        assert [summary.slug for summary in snapshot.trending_contracts] == [
            "vault",
            "oracle",
            "utility",
            "escrow",
        ]
        assert [summary.slug for summary in snapshot.recently_updated_contracts] == [
            "vault",
            "utility",
            "oracle",
            "escrow",
        ]
        assert [summary.slug for summary in snapshot.recently_deployed_contracts] == [
            "vault",
            "oracle",
            "utility",
        ]

        oracle = snapshot.featured_contracts[0]
        vault = snapshot.trending_contracts[0]

        assert oracle.author_name == "Core Team"
        assert oracle.primary_category_name == "Governance"
        assert oracle.semantic_version == "1.4.0"
        assert oracle.deployment_count == 1
        assert vault.author_name == "Bob"
        assert vault.star_count == 3
        assert vault.rating_count == 2
        assert vault.average_rating == 4.5
        assert vault.latest_deployment_at == _timestamp(10)
