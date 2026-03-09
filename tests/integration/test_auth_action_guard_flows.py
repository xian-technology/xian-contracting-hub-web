from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import AuthSession, User, UserRole, UserStatus
from contracting_hub.services.auth import (
    AuthServiceError,
    AuthServiceErrorCode,
    login_user,
    register_user,
    require_admin_user,
    require_authenticated_user,
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


def test_require_authenticated_user_returns_the_active_session_user() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        created_user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        authenticated_session = login_user(
            session=session,
            email="alice@example.com",
            password="correct horse battery staple",
        )

        guarded_user = require_authenticated_user(
            session=session,
            session_token=authenticated_session.session_token,
        )

    assert guarded_user.id == created_user.id
    assert guarded_user.profile is not None
    assert guarded_user.profile.username == "alice"


def test_require_authenticated_user_rejects_expired_and_disabled_sessions() -> None:
    engine = _build_engine()
    fixed_now = datetime(2026, 3, 9, 19, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        expiring_session = login_user(
            session=session,
            email="alice@example.com",
            password="correct horse battery staple",
            session_ttl=timedelta(minutes=30),
            now=fixed_now,
        )

        with pytest.raises(AuthServiceError) as expired_error:
            require_authenticated_user(
                session=session,
                session_token=expiring_session.session_token,
                now=fixed_now + timedelta(minutes=31),
            )

        assert expired_error.value.code is AuthServiceErrorCode.AUTHENTICATION_REQUIRED
        assert expired_error.value.details == {"expired": True}
        assert session.exec(select(sa.func.count()).select_from(AuthSession)).one() == 0

        disabled_session = login_user(
            session=session,
            email="alice@example.com",
            password="correct horse battery staple",
            now=fixed_now + timedelta(hours=1),
        )
        user = session.exec(select(User).where(User.email == "alice@example.com")).one()
        user.status = UserStatus.DISABLED
        session.commit()

        with pytest.raises(AuthServiceError) as disabled_error:
            require_authenticated_user(
                session=session,
                session_token=disabled_session.session_token,
                now=fixed_now + timedelta(hours=1, minutes=1),
            )

        assert disabled_error.value.code is AuthServiceErrorCode.ACCOUNT_DISABLED
        assert session.exec(select(sa.func.count()).select_from(AuthSession)).one() == 0


def test_require_admin_user_rejects_standard_users_and_allows_admins() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        authenticated_session = login_user(
            session=session,
            email="alice@example.com",
            password="correct horse battery staple",
        )

        with pytest.raises(AuthServiceError) as insufficient_role_error:
            require_admin_user(
                session=session,
                session_token=authenticated_session.session_token,
            )

        assert insufficient_role_error.value.code is AuthServiceErrorCode.INSUFFICIENT_ROLE

        stored_user = session.exec(select(User).where(User.email == "alice@example.com")).one()
        stored_user.role = UserRole.ADMIN
        session.commit()

        admin_user = require_admin_user(
            session=session,
            session_token=authenticated_session.session_token,
        )

    assert admin_user.role is UserRole.ADMIN
