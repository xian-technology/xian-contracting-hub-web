from __future__ import annotations

import io
from contextlib import contextmanager

from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.models import Profile, User, UserRole, UserStatus
from contracting_hub.services.playground_targets import (
    PlaygroundTargetServiceError,
    PlaygroundTargetServiceErrorCode,
)
from contracting_hub.services.profile_settings import (
    PrivatePlaygroundTargetSnapshot,
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
    targets: tuple[PrivatePlaygroundTargetSnapshot, ...] = (),
) -> PrivateProfileSettingsSnapshot:
    return PrivateProfileSettingsSnapshot(
        username=username,
        display_name=display_name,
        bio="Reusable treasury modules.",
        avatar_path=avatar_path,
        website_url="https://example.com/alice",
        github_url="https://github.com/alice",
        xian_profile_url="https://xian.org/u/alice",
        playground_targets=targets,
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
    target_snapshot = PrivatePlaygroundTargetSnapshot(
        id=7,
        label="Sandbox primary",
        playground_id="sandbox-main",
        is_default=True,
        last_used_at=None,
    )

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
        lambda **_kwargs: _build_snapshot(targets=(target_snapshot,)),
    )

    event = state.load_page()

    assert event is None
    assert state.profile_username == "alice"
    assert state.profile_display_name == "Alice Validator"
    assert state.playground_target_count_label == "1 saved target"
    assert state.playground_targets[0]["playground_id"] == "sandbox-main"
    assert state.playground_target_default_choice == "no"


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


def test_submit_playground_target_maps_field_errors(monkeypatch) -> None:
    state = _build_state(PROFILE_SETTINGS_ROUTE)
    state._apply_user_snapshot(_build_user())

    def _fake_create_playground_target(**_kwargs) -> None:
        raise PlaygroundTargetServiceError(
            PlaygroundTargetServiceErrorCode.INVALID_PLAYGROUND_ID,
            "Playground ID is invalid.",
            field="playground_id",
        )

    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.session_scope",
        _fake_session_scope,
    )
    monkeypatch.setattr(
        "contracting_hub.states.profile_settings.create_playground_target",
        _fake_create_playground_target,
    )

    state.submit_playground_target(
        {
            "label": "Sandbox primary",
            "playground_id": "  ",
            "is_default": "yes",
        }
    )

    assert state.playground_target_playground_id_error == "Playground ID is invalid."
    assert state.playground_target_success_message == ""
