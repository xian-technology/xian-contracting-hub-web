from pathlib import Path

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.config import load_settings
from contracting_hub.models import Profile, User
from contracting_hub.services.auth import (
    hash_password,
    login_user,
    register_user,
    resolve_current_user,
)
from contracting_hub.services.profiles import (
    ProfileServiceError,
    ProfileServiceErrorCode,
    remove_profile_avatar,
    replace_profile_avatar,
    update_profile,
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


def test_update_profile_normalizes_fields_and_keeps_auth_session_valid() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
            display_name="Alice",
        )
        authenticated_session = login_user(
            session=session,
            email="alice@example.com",
            password="correct horse battery staple",
        )

        profile = update_profile(
            session=session,
            user_id=user.id,
            username=" Alice_New ",
            display_name="  Alice Validator  ",
            bio="  Building reusable Xian modules.  ",
            website_url=" https://example.com/alice ",
            github_url=" https://github.com/alice ",
            xian_profile_url=" https://xian.org/u/alice ",
        )
        stored_profile = session.exec(select(Profile).where(Profile.user_id == user.id)).one()
        resolved_user = resolve_current_user(
            session=session,
            session_token=authenticated_session.session_token,
        )

    assert profile.id == stored_profile.id
    assert stored_profile.username == "alice_new"
    assert stored_profile.display_name == "Alice Validator"
    assert stored_profile.bio == "Building reusable Xian modules."
    assert stored_profile.website_url == "https://example.com/alice"
    assert stored_profile.github_url == "https://github.com/alice"
    assert stored_profile.xian_profile_url == "https://xian.org/u/alice"
    assert resolved_user is not None
    assert resolved_user.id == user.id
    assert resolved_user.profile is not None
    assert resolved_user.profile.username == "alice_new"


def test_update_profile_creates_missing_profile_rows_for_existing_users() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = User(
            email="builder@example.com",
            password_hash=hash_password("correct horse battery staple"),
        )
        session.add(user)
        session.commit()

        profile = update_profile(
            session=session,
            user_id=user.id,
            username=" Builder_One ",
            display_name=" Builder One ",
        )
        stored_profile = session.exec(select(Profile).where(Profile.user_id == user.id)).one()

    assert profile.id == stored_profile.id
    assert stored_profile.username == "builder_one"
    assert stored_profile.display_name == "Builder One"


def test_update_profile_rejects_duplicate_username_for_another_user() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        register_user(
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

        with pytest.raises(ProfileServiceError) as error:
            update_profile(
                session=session,
                user_id=bob.id,
                username=" ALICE ",
            )

    assert error.value.code is ProfileServiceErrorCode.DUPLICATE_USERNAME
    assert error.value.field == "username"


def test_replace_and_remove_profile_avatar_manage_files_and_profile_state(
    tmp_path: Path,
) -> None:
    settings = load_settings(project_root=tmp_path, environ={}, env_file=tmp_path / ".env")
    engine = _build_engine()

    with Session(engine) as session:
        user = register_user(
            session=session,
            email="alice@example.com",
            username="alice",
            password="correct horse battery staple",
        )

        first_profile = replace_profile_avatar(
            session=session,
            user_id=user.id,
            filename="Alice Portrait.png",
            content=b"first-avatar",
            content_type="image/png",
            settings=settings,
        )
        first_avatar_path = settings.uploads_dir / first_profile.avatar_path
        assert first_avatar_path.is_file()
        assert first_avatar_path.read_bytes() == b"first-avatar"

        second_profile = replace_profile_avatar(
            session=session,
            user_id=user.id,
            filename="Alice Portrait 2.png",
            content=b"second-avatar",
            content_type="image/png",
            settings=settings,
        )
        second_avatar_path = settings.uploads_dir / second_profile.avatar_path

        assert second_avatar_path.is_file()
        assert second_avatar_path.read_bytes() == b"second-avatar"
        assert not first_avatar_path.exists()

        cleared_profile = remove_profile_avatar(
            session=session,
            user_id=user.id,
            settings=settings,
        )

    assert cleared_profile.avatar_path is None
    assert not second_avatar_path.exists()
