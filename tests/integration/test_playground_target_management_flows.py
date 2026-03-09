import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import PlaygroundTarget, User, UserStatus
from contracting_hub.services import register_user
from contracting_hub.services.playground_targets import (
    PlaygroundTargetServiceError,
    PlaygroundTargetServiceErrorCode,
    create_playground_target,
    delete_playground_target,
    list_playground_targets,
    update_playground_target,
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


def test_create_and_list_playground_targets_keep_a_single_default() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        assert user.id is not None

        first_target = create_playground_target(
            session=session,
            user_id=user.id,
            label="  Sandbox  ",
            playground_id=" target-123 ",
        )
        second_target = create_playground_target(
            session=session,
            user_id=user.id,
            label="Team Playground",
            playground_id="team-456",
            is_default=True,
        )
        stored_targets = list_playground_targets(session=session, user_id=user.id)

    assert first_target.label == "Sandbox"
    assert first_target.playground_id == "target-123"
    assert first_target.is_default is False
    assert second_target.is_default is True
    assert [target.playground_id for target in stored_targets] == ["team-456", "target-123"]
    assert [target.is_default for target in stored_targets] == [True, False]


def test_update_playground_target_changes_fields_and_default_selection() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        assert user.id is not None

        first_target = create_playground_target(
            session=session,
            user_id=user.id,
            label="Sandbox",
            playground_id="target-123",
        )
        second_target = create_playground_target(
            session=session,
            user_id=user.id,
            label="Backup",
            playground_id="backup-456",
        )
        assert second_target.id is not None

        updated_target = update_playground_target(
            session=session,
            user_id=user.id,
            target_id=second_target.id,
            label="  Team Sandbox  ",
            playground_id="team-789",
            is_default=True,
        )
        stored_targets = list_playground_targets(session=session, user_id=user.id)

    assert updated_target.label == "Team Sandbox"
    assert updated_target.playground_id == "team-789"
    assert updated_target.is_default is True
    assert first_target.is_default is False
    assert [target.playground_id for target in stored_targets] == ["team-789", "target-123"]
    assert [target.is_default for target in stored_targets] == [True, False]


def test_update_playground_target_promotes_another_target_when_default_is_unset() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        assert user.id is not None

        first_target = create_playground_target(
            session=session,
            user_id=user.id,
            label="Sandbox",
            playground_id="target-123",
        )
        second_target = create_playground_target(
            session=session,
            user_id=user.id,
            label="Backup",
            playground_id="backup-456",
        )
        assert first_target.id is not None
        assert second_target.id is not None

        updated_target = update_playground_target(
            session=session,
            user_id=user.id,
            target_id=first_target.id,
            label="Sandbox",
            playground_id="target-123",
            is_default=False,
        )
        stored_targets = list_playground_targets(session=session, user_id=user.id)

    assert updated_target.is_default is False
    assert [target.playground_id for target in stored_targets] == ["backup-456", "target-123"]
    assert [target.is_default for target in stored_targets] == [True, False]


def test_delete_playground_target_promotes_another_saved_target() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        assert user.id is not None

        fallback_target = create_playground_target(
            session=session,
            user_id=user.id,
            label="Sandbox",
            playground_id="target-123",
        )
        default_target = create_playground_target(
            session=session,
            user_id=user.id,
            label="Primary",
            playground_id="primary-456",
            is_default=True,
        )
        assert default_target.id is not None
        assert fallback_target.id is not None

        deletion_result = delete_playground_target(
            session=session,
            user_id=user.id,
            target_id=default_target.id,
        )
        remaining_targets = list_playground_targets(session=session, user_id=user.id)
        stored_target_count = session.exec(
            select(sa.func.count()).select_from(PlaygroundTarget)
        ).one()

    assert deletion_result.deleted_target_id == default_target.id
    assert deletion_result.promoted_default_target_id == fallback_target.id
    assert stored_target_count == 1
    assert [target.playground_id for target in remaining_targets] == ["target-123"]
    assert remaining_targets[0].is_default is True


def test_playground_target_service_rejects_duplicates_invalid_ids_and_disabled_users() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        assert user.id is not None

        create_playground_target(
            session=session,
            user_id=user.id,
            label="Sandbox",
            playground_id="target-123",
        )

        with pytest.raises(PlaygroundTargetServiceError) as duplicate_error:
            create_playground_target(
                session=session,
                user_id=user.id,
                label="Another Sandbox",
                playground_id="target-123",
            )

        with pytest.raises(PlaygroundTargetServiceError) as invalid_id_error:
            create_playground_target(
                session=session,
                user_id=user.id,
                label="Bad ID",
                playground_id="target 123",
            )

        with pytest.raises(PlaygroundTargetServiceError) as missing_target_error:
            update_playground_target(
                session=session,
                user_id=user.id,
                target_id=9999,
                label="Missing",
                playground_id="missing-9999",
            )

        stored_user = session.exec(select(User).where(User.id == user.id)).one()
        stored_user.status = UserStatus.DISABLED
        session.commit()

        with pytest.raises(PlaygroundTargetServiceError) as disabled_user_error:
            list_playground_targets(
                session=session,
                user_id=user.id,
            )

    assert duplicate_error.value.code is PlaygroundTargetServiceErrorCode.DUPLICATE_PLAYGROUND_ID
    assert invalid_id_error.value.code is PlaygroundTargetServiceErrorCode.INVALID_PLAYGROUND_ID
    assert (
        missing_target_error.value.code
        is PlaygroundTargetServiceErrorCode.PLAYGROUND_TARGET_NOT_FOUND
    )
    assert disabled_user_error.value.code is PlaygroundTargetServiceErrorCode.USER_DISABLED
