from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import Profile, User
from contracting_hub.services.developer_profiles import (
    _coerce_utc_datetime,
    build_empty_public_developer_profile_snapshot,
    load_public_developer_profile_snapshot,
    load_public_developer_profile_snapshot_safe,
    normalize_public_developer_username,
)
from contracting_hub.utils.meta import build_developer_profile_path

NOW = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def test_normalize_public_developer_username_accepts_handles_and_invalid_values() -> None:
    assert normalize_public_developer_username(None) is None
    assert normalize_public_developer_username("@Alice ") == "alice"
    assert normalize_public_developer_username("bad name!") is None


def test_build_empty_public_developer_profile_snapshot_normalizes_username_and_window() -> None:
    snapshot = build_empty_public_developer_profile_snapshot(
        username=" @Alice ",
        activity_window_days=7,
    )

    assert snapshot.found is False
    assert snapshot.username == "alice"
    assert snapshot.activity_window_days == 7
    assert snapshot.authored_contracts == ()


def test_load_public_developer_profile_snapshot_returns_empty_for_invalid_username() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        snapshot = load_public_developer_profile_snapshot(
            session=session,
            username="not valid!",
            activity_window_days=30,
            now=NOW,
        )

    assert snapshot.found is False
    assert snapshot.username is None


def test_load_public_developer_profile_snapshot_falls_back_to_zero_kpis(monkeypatch) -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = User(email="alice@example.com", password_hash="hashed-password")
        user.profile = Profile(
            username="alice",
            display_name="Alice Builder",
            avatar_path="avatars/alice.png",
        )
        session.add(user)
        session.commit()

        monkeypatch.setattr(
            "contracting_hub.services.developer_profiles.get_developer_kpi_snapshot",
            lambda **_kwargs: None,
        )

        snapshot = load_public_developer_profile_snapshot(
            session=session,
            username="alice",
            activity_window_days=14,
            now=NOW,
        )

    assert snapshot.found is True
    assert snapshot.username == "alice"
    assert snapshot.display_name == "Alice Builder"
    assert snapshot.avatar_path == "avatars/alice.png"
    assert snapshot.published_contract_count == 0
    assert snapshot.total_stars_received == 0
    assert snapshot.activity_window_days == 14
    assert snapshot.activity_since == datetime(2026, 2, 23, 12, 0, tzinfo=timezone.utc)


def test_load_public_developer_profile_snapshot_safe_returns_empty_when_db_lookup_fails(
    monkeypatch,
) -> None:
    @contextmanager
    def _failing_session_scope():
        raise sa.exc.OperationalError("SELECT 1", {}, None)
        yield

    monkeypatch.setattr(
        "contracting_hub.services.developer_profiles.session_scope",
        _failing_session_scope,
    )

    snapshot = load_public_developer_profile_snapshot_safe(
        username="@alice",
        activity_window_days=30,
        now=NOW,
    )

    assert snapshot.found is False
    assert snapshot.username == "alice"


def test_load_public_developer_profile_snapshot_safe_returns_loaded_snapshot_on_success(
    monkeypatch,
) -> None:
    expected_snapshot = build_empty_public_developer_profile_snapshot(username="alice")

    @contextmanager
    def _fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "contracting_hub.services.developer_profiles.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        "contracting_hub.services.developer_profiles.load_public_developer_profile_snapshot",
        lambda **_kwargs: expected_snapshot,
    )

    snapshot = load_public_developer_profile_snapshot_safe(
        username="alice",
        activity_window_days=30,
        now=NOW,
    )

    assert snapshot is expected_snapshot


def test_build_developer_profile_path_trims_and_normalizes_usernames() -> None:
    assert build_developer_profile_path(" Alice ") == "/developers/alice"
    assert build_developer_profile_path("@bob") == "/developers/bob"
    assert build_developer_profile_path(None) == "/developers"


def test_coerce_utc_datetime_converts_non_utc_offsets() -> None:
    berlin_time = datetime(
        2026,
        3,
        9,
        14,
        0,
        tzinfo=timezone(timedelta(hours=1)),
    )

    assert _coerce_utc_datetime(berlin_time) == datetime(2026, 3, 9, 13, 0, tzinfo=timezone.utc)
