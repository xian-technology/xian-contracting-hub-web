import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import Contract, PublicationStatus, Star, User, UserStatus
from contracting_hub.services import register_user
from contracting_hub.services.stars import (
    ContractStarServiceError,
    ContractStarServiceErrorCode,
    toggle_contract_star,
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


def test_toggle_contract_star_adds_and_removes_one_favorite_record() -> None:
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

        first_toggle = toggle_contract_star(
            session=session,
            user_id=user_id,
            contract_slug=contract.slug,
        )
        stored_star = session.exec(select(Star)).one()

        second_toggle = toggle_contract_star(
            session=session,
            user_id=user_id,
            contract_slug=contract.slug,
        )

    assert first_toggle.contract_slug == "escrow"
    assert first_toggle.starred_by_user is True
    assert first_toggle.star_count == 1
    assert stored_star.user_id == user_id
    assert second_toggle.starred_by_user is False
    assert second_toggle.star_count == 0


def test_toggle_contract_star_updates_counts_across_multiple_users() -> None:
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
        alice_id = alice.id
        bob_id = bob.id

        alice_toggle = toggle_contract_star(
            session=session,
            user_id=alice_id,
            contract_slug=contract.slug,
        )
        bob_toggle = toggle_contract_star(
            session=session,
            user_id=bob_id,
            contract_slug=contract.slug,
        )
        alice_untoggle = toggle_contract_star(
            session=session,
            user_id=alice_id,
            contract_slug=contract.slug,
        )
        remaining_star = session.exec(select(Star)).one()

    assert alice_toggle.star_count == 1
    assert bob_toggle.star_count == 2
    assert alice_untoggle.star_count == 1
    assert alice_untoggle.starred_by_user is False
    assert remaining_star.user_id == bob_id


@pytest.mark.parametrize(
    "status",
    [PublicationStatus.DRAFT, PublicationStatus.ARCHIVED],
)
def test_toggle_contract_star_rejects_non_public_contracts(status: PublicationStatus) -> None:
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

        with pytest.raises(ContractStarServiceError) as error:
            toggle_contract_star(
                session=session,
                user_id=user.id,
                contract_slug=contract.slug,
            )

        star_count = session.exec(select(sa.func.count()).select_from(Star)).one()

    assert error.value.code is ContractStarServiceErrorCode.CONTRACT_NOT_STARABLE
    assert error.value.details["status"] == status.value
    assert star_count == 0


def test_toggle_contract_star_rejects_missing_contract_and_inactive_users() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        _create_contract(session, slug="rateable")

        assert user.id is not None

        with pytest.raises(ContractStarServiceError) as missing_contract_error:
            toggle_contract_star(
                session=session,
                user_id=user.id,
                contract_slug="missing-contract",
            )

        stored_user = session.exec(select(User).where(User.id == user.id)).one()
        stored_user.status = UserStatus.DISABLED
        session.commit()

        with pytest.raises(ContractStarServiceError) as disabled_user_error:
            toggle_contract_star(
                session=session,
                user_id=user.id,
                contract_slug="rateable",
            )

        with pytest.raises(ContractStarServiceError) as missing_user_error:
            toggle_contract_star(
                session=session,
                user_id=9999,
                contract_slug="rateable",
            )

    assert missing_contract_error.value.code is ContractStarServiceErrorCode.CONTRACT_NOT_FOUND
    assert disabled_user_error.value.code is ContractStarServiceErrorCode.USER_DISABLED
    assert missing_user_error.value.code is ContractStarServiceErrorCode.USER_NOT_FOUND
