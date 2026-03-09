from __future__ import annotations

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import Contract, PublicationStatus, Rating, Star
from contracting_hub.services import register_user
from contracting_hub.services.contract_detail import (
    build_empty_contract_detail_engagement_snapshot,
    load_contract_detail_engagement_snapshot,
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


def _create_contract(
    session: Session,
    *,
    slug: str,
    status: PublicationStatus = PublicationStatus.PUBLISHED,
) -> Contract:
    contract = Contract(
        slug=slug,
        contract_name=f"con_{slug.replace('-', '_')}",
        display_name=slug.replace("-", " ").title(),
        short_summary=f"{slug} summary.",
        long_description=f"Long-form description for the {slug} contract.",
        status=status,
    )
    session.add(contract)
    session.commit()
    return contract


def test_load_contract_detail_engagement_snapshot_returns_user_specific_star_and_rating() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        alice = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        bob = register_user(
            session=session,
            email="bob@example.com",
            username="bob",
            password="correct horse battery staple",
        )
        escrow = _create_contract(session, slug="escrow")
        draft_contract = _create_contract(
            session,
            slug="draft-escrow",
            status=PublicationStatus.DRAFT,
        )

        assert alice.id is not None
        assert bob.id is not None
        assert escrow.id is not None
        assert draft_contract.id is not None

        session.add_all(
            [
                Star(user_id=alice.id, contract_id=escrow.id),
                Star(user_id=bob.id, contract_id=escrow.id),
                Rating(user_id=alice.id, contract_id=escrow.id, score=4),
                Rating(user_id=bob.id, contract_id=escrow.id, score=2),
            ]
        )
        session.commit()

        snapshot = load_contract_detail_engagement_snapshot(
            session=session,
            user_id=alice.id,
            slug="escrow",
        )
        hidden_snapshot = load_contract_detail_engagement_snapshot(
            session=session,
            user_id=alice.id,
            slug="draft-escrow",
        )
        missing_snapshot = load_contract_detail_engagement_snapshot(
            session=session,
            user_id=alice.id,
            slug="missing-contract",
        )

    assert snapshot.starred_by_user is True
    assert snapshot.current_user_rating_score == 4
    assert hidden_snapshot == build_empty_contract_detail_engagement_snapshot()
    assert missing_snapshot == build_empty_contract_detail_engagement_snapshot()
