from pathlib import Path

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.config import load_settings
from contracting_hub.models import Category, Profile, User, UserRole
from contracting_hub.services.bootstrap import (
    DEFAULT_CATEGORY_TAXONOMY,
    seed_local_development_data,
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


def test_seed_local_development_data_creates_categories_and_bootstrap_admin(
    tmp_path: Path,
) -> None:
    settings = load_settings(project_root=tmp_path, environ={}, env_file=tmp_path / ".env")
    engine = _build_engine()

    with Session(engine) as session:
        first_report = seed_local_development_data(settings=settings, session=session)
        second_report = seed_local_development_data(settings=settings, session=session)

        stored_categories = session.exec(select(Category).order_by(Category.sort_order)).all()
        stored_users = session.exec(select(User)).all()
        stored_profiles = session.exec(select(Profile)).all()

    assert first_report.schema_ready is True
    assert first_report.categories_created == len(DEFAULT_CATEGORY_TAXONOMY)
    assert first_report.admin_created is True
    assert first_report.admin_promoted is False
    assert first_report.profile_created is True
    assert not first_report.warnings

    assert second_report.schema_ready is True
    assert second_report.categories_created == 0
    assert second_report.admin_created is False
    assert second_report.admin_promoted is False
    assert second_report.profile_created is False

    assert [category.slug for category in stored_categories] == [
        definition.slug for definition in DEFAULT_CATEGORY_TAXONOMY
    ]
    assert len(stored_users) == 1
    assert stored_users[0].email == "admin@contractinghub.local"
    assert stored_users[0].role == UserRole.ADMIN
    assert len(stored_profiles) == 1
    assert stored_profiles[0].username == "admin"


def test_seed_local_development_data_promotes_existing_bootstrap_user(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path, environ={}, env_file=tmp_path / ".env")
    engine = _build_engine()

    with Session(engine) as session:
        session.add(
            User(
                email="admin@contractinghub.local",
                password_hash="existing-hash",
                role=UserRole.USER,
            )
        )
        session.commit()

        report = seed_local_development_data(settings=settings, session=session)
        user = session.exec(select(User).where(User.email == "admin@contractinghub.local")).one()
        profile = session.exec(select(Profile).where(Profile.user_id == user.id)).one()

    assert report.schema_ready is True
    assert report.admin_created is False
    assert report.admin_promoted is True
    assert report.profile_created is True
    assert user.role == UserRole.ADMIN
    assert profile.username == "admin"


def test_seed_local_development_data_skips_when_schema_is_not_ready(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path, environ={}, env_file=tmp_path / ".env")
    engine = sa.create_engine("sqlite:///:memory:")

    with Session(engine) as session:
        report = seed_local_development_data(settings=settings, session=session)

    assert report.schema_ready is False
    assert report.categories_created == 0
    assert report.admin_created is False
    assert report.warnings == (
        "Local bootstrap skipped because the schema has not been migrated yet.",
    )
