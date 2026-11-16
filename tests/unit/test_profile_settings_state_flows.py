from __future__ import annotations

import io
from contextlib import contextmanager

import pytest
from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.models import Profile, User, UserRole, UserStatus
from contracting_hub.services.profile_settings import (
    PrivateProfileSettingsSnapshot,
)
from contracting_hub.services.profiles import (
    ProfileServiceError,
    ProfileServiceErrorCode,
)
from contracting_hub.states import ProfileSettingsState
from contracting_hub.utils.meta import PROFILE_SETTINGS_ROUTE


def _build_user() -> User:
    user = User(
        id=42,
        email="alice@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    user.profile = Profile(username="alice", display_name="Alice Validator")
    return user


def _set_route_context(state: ProfileSettingsState, path: str) -> None:
    router_data = {
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.HEADERS: {"origin": "http://localhost:3000"},
    }
    object.__setattr__(state, "router_data", router_data)
    object.__setattr__(state, "router", RouterData.from_router_data(router_data))


def _build_state(path: str) -> ProfileSettingsState:
    state = ProfileSettingsState(_reflex_internal_init=True)
    _set_route_context(state, path)
    return state


@contextmanager
def _fake_session_scope():
    yield object()


def _build_snapshot(
    *,
    username: str = "alice",
    display_name: str | None = "Alice Validator",
    avatar_path: str | None = None,
) -> PrivateProfileSettingsSnapshot:
    return PrivateProfileSettingsSnapshot(
        username=username,
        display_name=display_name,
        bio="Reusable treasury modules.",
        avatar_path=avatar_path,
        website_url="https://example.com/alice",
        github_url="https://github.com/alice",
        xian_profile_url="https://xian.org/u/alice",
    )


def test_load_page_without_authenticated_user_keeps_blank_snapshot(monkeypatch) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)

    monkeypatch.setattr(
        ProfileSettingsState,
        "_resolve_user_from_cookie",
        lambda self: None,
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.load_private_profile_settings_snapshot",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot loader should not run")),
    )

    event = state.load_page()

    assert event is None
    assert state.profile_username == ""


def test_load_page_populates_authenticated_profile_snapshot(monkeypatch) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)

    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        ProfileSettingsState,
        "_resolve_user_from_cookie",
        lambda self: _build_user(),
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.load_private_profile_settings_snapshot",
        lambda **_kwargs: _build_snapshot(),
    )

    event = state.load_page()

    assert event is None
    assert state.profile_username == "alice"
    assert state.profile_display_name == "Alice Validator"


def test_submit_profile_updates_current_identity_after_success(monkeypatch) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state._apply_user_snapshot(_build_user())

    def _fake_update_profile(*, session, user_id: int, username: str, **_kwargs) -> None:
        assert session is not None
        assert user_id == 42
        assert username == "alice_ops"

    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.update_profile",
        _fake_update_profile,
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.load_private_profile_settings_snapshot",
        lambda **_kwargs: _build_snapshot(username="alice_ops", display_name="Alice Ops"),
    )

    state.submit_profile(
        {
            "username": "alice_ops",
            "display_name": "Alice Ops",
            "bio": "Updated bio",
            "website_url": "https://example.com/alice",
            "github_url": "https://github.com/alice",
            "xian_profile_url": "https://xian.org/u/alice",
        }
    )

    assert state.profile_success_message == "Profile updated."
    assert state.current_username == "alice_ops"
    assert state.current_display_name == "Alice Ops"


def test_submit_profile_maps_username_errors(monkeypatch) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state._apply_user_snapshot(_build_user())

    def _fake_update_profile(**_kwargs) -> None:
        raise ProfileServiceError(
            ProfileServiceErrorCode.DUPLICATE_USERNAME,
            "This username is already in use.",
            field="username",
        )

    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.update_profile",
        _fake_update_profile,
    )

    state.submit_profile({"username": "alice"})

    assert state.profile_success_message == ""
    assert state.profile_username_error == "This username is already in use."


def test_upload_avatar_updates_state_and_returns_clear_selected_files(monkeypatch) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state._apply_user_snapshot(_build_user())

    captured: dict[str, object] = {}

    def _fake_replace_profile_avatar(
        *,
        session,
        user_id: int,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> None:
        assert session is not None
        captured.update(
            {
                "user_id": user_id,
                "filename": filename,
                "content": content,
                "content_type": content_type,
            }
        )

    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.replace_profile_avatar",
        _fake_replace_profile_avatar,
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.load_private_profile_settings_snapshot",
        lambda **_kwargs: _build_snapshot(avatar_path="avatars/profile-images/alice-avatar.png"),
    )

    upload = type(
        "FakeUpload",
        (),
        {
            "filename": "avatar.png",
            "name": "avatar.png",
            "file": io.BytesIO(b"avatar-bytes"),
            "content_type": "image/png",
        },
    )()

    event = state.upload_avatar([upload])

    assert captured == {
        "user_id": 42,
        "filename": "avatar.png",
        "content": b"avatar-bytes",
        "content_type": "image/png",
    }
    assert state.avatar_success_message == "Avatar updated."
    assert state.avatar_storage_key == "avatars/profile-images/alice-avatar.png"
    assert event is not None


def test_signed_out_profile_submission_preserves_form_and_shows_auth_error() -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state.profile_username = "pending_name"

    state.submit_profile({"username": "changed"})

    assert state.profile_username == "pending_name"
    assert state.profile_form_error == "Authentication is required to update your profile."
    assert state.profile_success_message == ""


@pytest.mark.parametrize(
    ("field", "state_field"),
    [
        ("display_name", "profile_display_name_error"),
        ("bio", "profile_bio_error"),
        ("website_url", "profile_website_url_error"),
        ("github_url", "profile_github_url_error"),
        ("xian_profile_url", "profile_xian_profile_url_error"),
        ("other", "profile_form_error"),
    ],
)
def test_profile_submission_displays_validation_error_at_its_field(
    monkeypatch, field, state_field
) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state._apply_user_snapshot(_build_user())

    def reject_profile(**_kwargs):
        raise ProfileServiceError(
            ProfileServiceErrorCode.DUPLICATE_USERNAME, "Rejected profile value.", field=field
        )

    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.session_scope", _fake_session_scope
    )
    monkeypatch.setattr("contracting_hub.states.profile_settings.update_profile", reject_profile)

    state.submit_profile({"username": "alice"})

    assert getattr(state, state_field) == "Rejected profile value."
    assert state.profile_success_message == ""


@pytest.mark.parametrize(
    ("display_name", "username", "email", "label", "secondary"),
    [
        ("Alice Ops", "alice", "alice@example.com", "Alice Ops", "@alice"),
        ("Alice Ops", None, "alice@example.com", "Alice Ops", "alice@example.com"),
        (None, "alice", "alice@example.com", "@alice", "alice@example.com"),
        (None, None, "alice@example.com", "alice@example.com", ""),
        (None, None, None, "Account", ""),
    ],
)
def test_account_navigation_uses_available_identity_fields(
    display_name, username, email, label, secondary
) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state.current_display_name = display_name
    state.current_username = username
    state.current_user_email = email

    assert state.current_identity_label == label
    assert state.current_identity_secondary == secondary
    assert state.has_current_identity_secondary == bool(secondary)


@pytest.mark.parametrize(
    ("display_name", "username", "email", "initials"),
    [
        ("Alice Validator", "alice", "alice@example.com", "AV"),
        ("", "alice_ops", "alice@example.com", "AO"),
        ("", "", "alice@example.com", "AE"),
        ("", "", "", "U"),
        ("   ", "alice", "alice@example.com", "UH"),
    ],
)
def test_avatar_placeholder_uses_current_profile_identity(
    display_name, username, email, initials
) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state.profile_display_name = display_name
    state.profile_username = username
    state.current_user_email = email

    assert state.avatar_fallback == initials


def test_avatar_removal_refreshes_profile_and_reports_success(monkeypatch) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state._apply_user_snapshot(_build_user())
    state.avatar_storage_key = "avatars/alice.png"
    deleted = []
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.session_scope", _fake_session_scope
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.remove_profile_avatar",
        lambda **kwargs: deleted.append(kwargs["user_id"]),
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.load_private_profile_settings_snapshot",
        lambda **_kwargs: _build_snapshot(),
    )

    state.remove_avatar()

    assert deleted == [42]
    assert state.avatar_storage_key == ""
    assert state.avatar_success_message == "Avatar removed."
    assert state.avatar_status_label == "No avatar uploaded yet"


@pytest.mark.parametrize(
    ("authenticated", "message"),
    [
        (False, "Authentication is required to remove your avatar."),
        (True, "No avatar is currently stored."),
    ],
)
def test_avatar_removal_requires_account_and_existing_avatar(authenticated, message) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    if authenticated:
        state._apply_user_snapshot(_build_user())

    state.remove_avatar()

    assert state.avatar_error_message == message
    assert state.avatar_success_message == ""


@pytest.mark.parametrize(
    ("authenticated", "message"),
    [
        (False, "Authentication is required to update your avatar."),
        (True, "Choose an avatar image to upload."),
    ],
)
def test_avatar_upload_requires_account_and_file(authenticated, message) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    if authenticated:
        state._apply_user_snapshot(_build_user())

    event = state.upload_avatar([])

    assert event is not None
    assert state.avatar_error_message == message
    assert state.avatar_success_message == ""
