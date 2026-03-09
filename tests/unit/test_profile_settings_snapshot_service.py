from __future__ import annotations

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import User
from contracting_hub.services.profile_settings import load_private_profile_settings_snapshot
from contracting_hub.services.profiles import ProfileServiceError, ProfileServiceErrorCode


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def test_load_private_profile_settings_snapshot_raises_for_unknown_user() -> None:
    engine = _build_engine()

    with Session(engine) as session, pytest.raises(ProfileServiceError) as error:
        load_private_profile_settings_snapshot(session=session, user_id=999)

    assert error.value.code is ProfileServiceErrorCode.USER_NOT_FOUND
    assert error.value.field == "user_id"


def test_load_private_profile_settings_snapshot_returns_blank_profile_when_missing() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = User(email="alice@example.com", password_hash="hashed-password")
        session.add(user)
        session.commit()

        snapshot = load_private_profile_settings_snapshot(session=session, user_id=user.id)

    assert snapshot.username == ""
    assert snapshot.display_name is None
    assert snapshot.playground_targets == ()
