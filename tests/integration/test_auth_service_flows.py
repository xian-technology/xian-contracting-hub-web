from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.models import AuthSession, Profile, User, UserRole, UserStatus
from contracting_hub.services.auth import (
    AuthServiceError,
    AuthServiceErrorCode,
    build_session_token_hash,
    login_user,
    logout_user,
    register_user,
    resolve_current_user,
    verify_password,
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


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def test_register_user_creates_hashed_active_account_with_profile() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="  Alice@Example.com ",
            username=" Alice_Validator ",
            password="correct horse battery staple",
            display_name="Alice Validator",
        )

        stored_user = session.exec(select(User).where(User.id == user.id)).one()
        stored_profile = session.exec(select(Profile).where(Profile.user_id == user.id)).one()

    assert stored_user.email == "alice@example.com"
    assert stored_user.role is UserRole.USER
    assert stored_user.status is UserStatus.ACTIVE
    assert stored_user.password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", stored_user.password_hash) is True
    assert stored_profile.username == "alice_validator"
    assert stored_profile.display_name == "Alice Validator"


def test_register_user_returns_field_errors_for_duplicate_email_and_username() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )

        with pytest.raises(AuthServiceError) as duplicate_email_error:
            register_user(
                session=session,
                email="ALICE@example.com",
                username="alice_2",
                password="correct horse battery staple",
            )

        with pytest.raises(AuthServiceError) as duplicate_username_error:
            register_user(
                session=session,
                email="alice-2@example.com",
                username="ALICE",
                password="correct horse battery staple",
            )

    assert duplicate_email_error.value.code is AuthServiceErrorCode.DUPLICATE_EMAIL
    assert duplicate_email_error.value.field == "email"
    assert duplicate_username_error.value.code is AuthServiceErrorCode.DUPLICATE_USERNAME
    assert duplicate_username_error.value.field == "username"


def test_login_persists_hashed_session_and_updates_last_login_at() -> None:
    engine = _build_engine()
    fixed_now = datetime(2026, 3, 9, 12, 30, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )

        authenticated_session = login_user(
            session=session,
            email="alice@example.com",
            password="correct horse battery staple",
            session_ttl=timedelta(hours=2),
            now=fixed_now,
        )

        stored_user = session.exec(select(User).where(User.id == user.id)).one()
        stored_auth_session = session.exec(select(AuthSession)).one()
        resolved_user = resolve_current_user(
            session=session,
            session_token=authenticated_session.session_token,
            now=fixed_now + timedelta(minutes=5),
        )

    assert stored_auth_session.session_token_hash != authenticated_session.session_token
    assert stored_auth_session.session_token_hash == build_session_token_hash(
        authenticated_session.session_token
    )
    assert _coerce_utc(stored_auth_session.expires_at) == fixed_now + timedelta(hours=2)
    assert _coerce_utc(stored_user.last_login_at) == fixed_now
    assert resolved_user is not None
    assert resolved_user.id == user.id


def test_logout_invalidates_the_session_immediately() -> None:
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

        assert (
            logout_user(
                session=session,
                session_token=authenticated_session.session_token,
            )
            is True
        )
        assert (
            logout_user(
                session=session,
                session_token=authenticated_session.session_token,
            )
            is False
        )
        assert (
            resolve_current_user(
                session=session,
                session_token=authenticated_session.session_token,
            )
            is None
        )
        assert session.exec(select(sa.func.count()).select_from(AuthSession)).one() == 0


def test_expired_and_disabled_sessions_are_not_resolved() -> None:
    engine = _build_engine()
    fixed_now = datetime(2026, 3, 9, 18, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )
        expired_session = login_user(
            session=session,
            email="alice@example.com",
            password="correct horse battery staple",
            session_ttl=timedelta(minutes=30),
            now=fixed_now,
        )

        assert (
            resolve_current_user(
                session=session,
                session_token=expired_session.session_token,
                now=fixed_now + timedelta(minutes=31),
            )
            is None
        )
        assert session.exec(select(sa.func.count()).select_from(AuthSession)).one() == 0

        disabled_session = login_user(
            session=session,
            email="alice@example.com",
            password="correct horse battery staple",
            now=fixed_now + timedelta(hours=1),
        )

        disabled_user = session.exec(select(User).where(User.email == "alice@example.com")).one()
        disabled_user.status = UserStatus.DISABLED
        session.commit()

        assert (
            resolve_current_user(
                session=session,
                session_token=disabled_session.session_token,
                now=fixed_now + timedelta(hours=1, minutes=1),
            )
            is None
        )
        assert session.exec(select(sa.func.count()).select_from(AuthSession)).one() == 0


def test_login_rejects_invalid_credentials_and_disabled_accounts() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )

        with pytest.raises(AuthServiceError) as invalid_credentials_error:
            login_user(
                session=session,
                email="alice@example.com",
                password="not the right password",
            )

        user = session.exec(select(User).where(User.email == "alice@example.com")).one()
        user.status = UserStatus.DISABLED
        session.commit()

        with pytest.raises(AuthServiceError) as disabled_error:
            login_user(
                session=session,
                email="alice@example.com",
                password="correct horse battery staple",
            )

    assert invalid_credentials_error.value.code is AuthServiceErrorCode.INVALID_CREDENTIALS
    assert disabled_error.value.code is AuthServiceErrorCode.ACCOUNT_DISABLED
