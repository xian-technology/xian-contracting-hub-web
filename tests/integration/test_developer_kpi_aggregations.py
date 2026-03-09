from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import (
    Contract,
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
from contracting_hub.services.developer_kpis import (
    DeveloperLeaderboardSort,
    DeveloperLeaderboardTimeframe,
    get_developer_kpi_snapshot,
    list_developer_leaderboard,
)

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


def _user(username: str) -> User:
    user = User(
        email=f"{username}@example.com",
        password_hash="hashed-password",
    )
    user.profile = Profile(
        username=username,
        display_name=username.title(),
    )
    return user


def _contract(
    *,
    author: User,
    slug: str,
    status: PublicationStatus,
    published_at: datetime,
) -> tuple[Contract, ContractVersion]:
    contract = Contract(
        slug=slug,
        contract_name=f"con_{slug.replace('-', '_')}",
        display_name=slug.replace("-", " ").title(),
        short_summary=f"{slug} summary.",
        long_description=f"Long-form description for the {slug} contract.",
        author=author,
        status=status,
        created_at=published_at,
        updated_at=published_at,
    )
    version = ContractVersion(
        contract=contract,
        semantic_version="1.0.0",
        status=PublicationStatus.PUBLISHED,
        source_code=f"def {slug.replace('-', '_')}():\n    return '{slug}'\n",
        source_hash_sha256=(slug[0] * 64)[:64],
        changelog=f"Initial {slug} release.",
        published_at=published_at,
        created_at=published_at,
        updated_at=published_at,
    )
    contract.latest_published_version = version
    return contract, version


def _seed_developer_metrics(session: Session) -> None:
    alice = _user("alice")
    bob = _user("bob")
    carol = _user("carol")
    dana = _user("dana")
    eric = _user("eric")
    frank = _user("frank")

    escrow, escrow_v1 = _contract(
        author=alice,
        slug="escrow",
        status=PublicationStatus.PUBLISHED,
        published_at=_timestamp(2, 20),
    )
    vault, vault_v1 = _contract(
        author=alice,
        slug="vault",
        status=PublicationStatus.PUBLISHED,
        published_at=_timestamp(1, 5),
    )
    legacy, legacy_v1 = _contract(
        author=alice,
        slug="legacy",
        status=PublicationStatus.DEPRECATED,
        published_at=_timestamp(3, 1),
    )
    oracle, oracle_v1 = _contract(
        author=bob,
        slug="oracle",
        status=PublicationStatus.PUBLISHED,
        published_at=_timestamp(2, 18),
    )
    market, market_v1 = _contract(
        author=carol,
        slug="market",
        status=PublicationStatus.PUBLISHED,
        published_at=_timestamp(1, 1),
    )

    session.add_all(
        [
            alice,
            bob,
            carol,
            dana,
            eric,
            frank,
            escrow,
            escrow_v1,
            vault,
            vault_v1,
            legacy,
            legacy_v1,
            oracle,
            oracle_v1,
            market,
            market_v1,
            Star(
                user=dana,
                contract=escrow,
                created_at=_timestamp(2, 25),
                updated_at=_timestamp(2, 25),
            ),
            Star(
                user=eric,
                contract=escrow,
                created_at=_timestamp(2, 26),
                updated_at=_timestamp(2, 26),
            ),
            Star(
                user=frank, contract=vault, created_at=_timestamp(1, 5), updated_at=_timestamp(1, 5)
            ),
            Star(
                user=dana,
                contract=oracle,
                created_at=_timestamp(2, 20),
                updated_at=_timestamp(2, 20),
            ),
            Star(
                user=eric, contract=oracle, created_at=_timestamp(1, 2), updated_at=_timestamp(1, 2)
            ),
            Star(
                user=dana, contract=market, created_at=_timestamp(1, 1), updated_at=_timestamp(1, 1)
            ),
            Star(
                user=eric, contract=market, created_at=_timestamp(1, 2), updated_at=_timestamp(1, 2)
            ),
            Star(
                user=frank,
                contract=legacy,
                created_at=_timestamp(3, 1),
                updated_at=_timestamp(3, 1),
            ),
            Rating(
                user=dana,
                contract=escrow,
                score=5,
                created_at=_timestamp(2, 25),
                updated_at=_timestamp(2, 25),
            ),
            Rating(
                user=eric,
                contract=escrow,
                score=3,
                created_at=_timestamp(1, 5),
                updated_at=_timestamp(1, 5),
            ),
            Rating(
                user=frank,
                contract=vault,
                score=4,
                created_at=_timestamp(2, 10),
                updated_at=_timestamp(2, 10),
            ),
            Rating(
                user=dana,
                contract=oracle,
                score=5,
                created_at=_timestamp(2, 20),
                updated_at=_timestamp(2, 20),
            ),
            Rating(
                user=eric,
                contract=market,
                score=5,
                created_at=_timestamp(1, 5),
                updated_at=_timestamp(1, 5),
            ),
            Rating(
                user=frank,
                contract=legacy,
                score=1,
                created_at=_timestamp(3, 1),
                updated_at=_timestamp(3, 1),
            ),
            DeploymentHistory(
                user=dana,
                contract_version=escrow_v1,
                playground_id="escrow-recent",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.DEEP_LINK,
                created_at=_timestamp(2, 28),
                updated_at=_timestamp(2, 28),
                initiated_at=_timestamp(2, 28),
                completed_at=_timestamp(2, 28),
            ),
            DeploymentHistory(
                user=eric,
                contract_version=escrow_v1,
                playground_id="escrow-old",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.DEEP_LINK,
                created_at=_timestamp(1, 20),
                updated_at=_timestamp(1, 20),
                initiated_at=_timestamp(1, 20),
                completed_at=_timestamp(1, 20),
            ),
            DeploymentHistory(
                user=frank,
                contract_version=vault_v1,
                playground_id="vault-recent",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.HTTP,
                created_at=_timestamp(2, 15),
                updated_at=_timestamp(2, 15),
                initiated_at=_timestamp(2, 15),
                completed_at=_timestamp(2, 15),
            ),
            DeploymentHistory(
                user=dana,
                contract_version=oracle_v1,
                playground_id="oracle-recent",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.HTTP,
                created_at=_timestamp(2, 21),
                updated_at=_timestamp(2, 21),
                initiated_at=_timestamp(2, 21),
                completed_at=_timestamp(2, 21),
            ),
            DeploymentHistory(
                user=dana,
                contract_version=market_v1,
                playground_id="market-old",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.HTTP,
                created_at=_timestamp(1, 3),
                updated_at=_timestamp(1, 3),
                initiated_at=_timestamp(1, 3),
                completed_at=_timestamp(1, 3),
            ),
            DeploymentHistory(
                user=eric,
                contract_version=legacy_v1,
                playground_id="legacy-recent",
                status=DeploymentStatus.ACCEPTED,
                transport=DeploymentTransport.HYBRID,
                created_at=_timestamp(3, 1),
                updated_at=_timestamp(3, 1),
                initiated_at=_timestamp(3, 1),
                completed_at=_timestamp(3, 1),
            ),
        ]
    )
    session.commit()


def test_get_developer_kpi_snapshot_aggregates_published_contract_metrics() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_developer_metrics(session)

        snapshot = get_developer_kpi_snapshot(
            session=session,
            username=" Alice ",
            activity_window_days=30,
            now=NOW,
        )

    assert snapshot is not None
    assert snapshot.username == "alice"
    assert snapshot.published_contract_count == 2
    assert snapshot.total_stars_received == 3
    assert snapshot.weighted_average_rating == pytest.approx(4.0)
    assert snapshot.total_rating_count == 3
    assert snapshot.total_deployment_count == 3
    assert snapshot.recent_published_contract_count == 1
    assert snapshot.recent_publish_count == 1
    assert snapshot.recent_stars_received == 2
    assert snapshot.recent_weighted_average_rating == pytest.approx(4.5)
    assert snapshot.recent_rating_count == 2
    assert snapshot.recent_deployment_count == 2
    assert snapshot.recent_activity_count == 7


def test_list_developer_leaderboard_uses_deterministic_all_time_tiebreaks() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_developer_metrics(session)

        leaderboard = list_developer_leaderboard(
            session=session,
            sort=DeveloperLeaderboardSort.WEIGHTED_RATING,
            activity_window_days=30,
            limit=None,
            now=NOW,
        )

    assert [entry.username for entry in leaderboard] == ["bob", "carol", "alice"]


def test_list_developer_leaderboard_recent_timeframe_filters_to_recent_activity() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_developer_metrics(session)

        leaderboard = list_developer_leaderboard(
            session=session,
            sort=DeveloperLeaderboardSort.STAR_TOTAL,
            timeframe=DeveloperLeaderboardTimeframe.RECENT,
            activity_window_days=30,
            limit=None,
            now=NOW,
        )

    assert [entry.username for entry in leaderboard] == ["alice", "bob"]
