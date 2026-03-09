import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import Contract, PublicationStatus, Rating, User, UserStatus
from contracting_hub.services import register_user
from contracting_hub.services.ratings import (
    ContractRatingServiceError,
    ContractRatingServiceErrorCode,
    submit_contract_rating,
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


def test_submit_contract_rating_creates_and_updates_a_single_user_rating() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        contract = _create_contract(session, slug="escrow")

        assert user.id is not None
        user_id = user.id

        first_submission = submit_contract_rating(
            session=session,
            user_id=user_id,
            contract_slug=contract.slug,
            score=" 4 ",
            note="  Helpful baseline.  ",
        )
        stored_rating = session.exec(select(Rating)).one()
        stored_rating_id = stored_rating.id

        second_submission = submit_contract_rating(
            session=session,
            user_id=user_id,
            contract_slug=contract.slug,
            score=5,
            note="   ",
        )
        updated_rating = session.exec(select(Rating)).one()

    assert first_submission.contract_slug == "escrow"
    assert first_submission.score == 4
    assert first_submission.note == "Helpful baseline."
    assert first_submission.rating_count == 1
    assert first_submission.average_score == pytest.approx(4.0)
    assert first_submission.updated_existing is False
    assert second_submission.score == 5
    assert second_submission.note is None
    assert second_submission.rating_count == 1
    assert second_submission.average_score == pytest.approx(5.0)
    assert second_submission.updated_existing is True
    assert updated_rating.id == stored_rating_id
    assert updated_rating.score == 5
    assert updated_rating.note is None


def test_submit_contract_rating_recalculates_aggregates_across_multiple_users() -> None:
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
        contract = _create_contract(session, slug="vault")

        assert alice.id is not None
        assert bob.id is not None

        alice_submission = submit_contract_rating(
            session=session,
            user_id=alice.id,
            contract_slug=contract.slug,
            score=4,
        )
        bob_submission = submit_contract_rating(
            session=session,
            user_id=bob.id,
            contract_slug=contract.slug,
            score=2,
        )
        alice_update = submit_contract_rating(
            session=session,
            user_id=alice.id,
            contract_slug=contract.slug,
            score=5,
        )
        rating_count = session.exec(select(sa.func.count()).select_from(Rating)).one()

    assert alice_submission.rating_count == 1
    assert alice_submission.average_score == pytest.approx(4.0)
    assert bob_submission.rating_count == 2
    assert bob_submission.average_score == pytest.approx(3.0)
    assert alice_update.rating_count == 2
    assert alice_update.average_score == pytest.approx(3.5)
    assert rating_count == 2


@pytest.mark.parametrize(
    "status",
    [PublicationStatus.DRAFT, PublicationStatus.ARCHIVED],
)
def test_submit_contract_rating_rejects_non_public_contracts(status: PublicationStatus) -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        contract = _create_contract(session, slug=f"{status.value}-only", status=status)

        assert user.id is not None

        with pytest.raises(ContractRatingServiceError) as error:
            submit_contract_rating(
                session=session,
                user_id=user.id,
                contract_slug=contract.slug,
                score=4,
            )

        rating_count = session.exec(select(sa.func.count()).select_from(Rating)).one()

    assert error.value.code is ContractRatingServiceErrorCode.CONTRACT_NOT_RATEABLE
    assert error.value.details["status"] == status.value
    assert rating_count == 0


def test_submit_contract_rating_rejects_missing_contract_users_and_invalid_score() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        active_user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        disabled_user = register_user(
            session=session,
            email="bob@example.com",
            username="bob",
            password="correct horse battery staple",
        )
        _create_contract(session, slug="rateable")

        assert active_user.id is not None
        assert disabled_user.id is not None

        with pytest.raises(ContractRatingServiceError) as missing_contract_error:
            submit_contract_rating(
                session=session,
                user_id=active_user.id,
                contract_slug="missing-contract",
                score=4,
            )

        stored_disabled_user = session.exec(select(User).where(User.id == disabled_user.id)).one()
        stored_disabled_user.status = UserStatus.DISABLED
        session.commit()

        with pytest.raises(ContractRatingServiceError) as disabled_user_error:
            submit_contract_rating(
                session=session,
                user_id=disabled_user.id,
                contract_slug="rateable",
                score=4,
            )

        with pytest.raises(ContractRatingServiceError) as missing_user_error:
            submit_contract_rating(
                session=session,
                user_id=9999,
                contract_slug="rateable",
                score=4,
            )

        with pytest.raises(ContractRatingServiceError) as invalid_score_error:
            submit_contract_rating(
                session=session,
                user_id=active_user.id,
                contract_slug="rateable",
                score=8,
            )

    assert missing_contract_error.value.code is ContractRatingServiceErrorCode.CONTRACT_NOT_FOUND
    assert disabled_user_error.value.code is ContractRatingServiceErrorCode.USER_DISABLED
    assert missing_user_error.value.code is ContractRatingServiceErrorCode.USER_NOT_FOUND
    assert invalid_score_error.value.code is ContractRatingServiceErrorCode.INVALID_SCORE
