"""Authenticated profile settings page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import app_shell, page_error_state, page_loading_state, page_section
from contracting_hub.config import get_settings
from contracting_hub.states import PROFILE_AVATAR_UPLOAD_ID, AuthState, ProfileSettingsState
from contracting_hub.utils.meta import PROFILE_SETTINGS_ROUTE

ROUTE = PROFILE_SETTINGS_ROUTE
ON_LOAD = [AuthState.guard_authenticated_route, ProfileSettingsState.load_page]
_SETTINGS = get_settings()

AVATAR_ACCEPT = {
    "image/gif": [".gif"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
}


def _field_label(label: str, *, field_id: str) -> rx.Component:
    return rx.el.label(
        label,
        html_for=field_id,
        font_size="0.78rem",
        font_weight="600",
        text_transform="uppercase",
        letter_spacing="0.08em",
        color="var(--hub-color-text-muted)",
    )


def _surface_input(**props: object) -> rx.Component:
    return rx.input(
        size="3",
        variant="surface",
        width="100%",
        **props,
    )


def _surface_text_area(**props: object) -> rx.Component:
    return rx.el.textarea(
        style=_text_area_style(),
        **props,
    )


def _select_style() -> dict[str, str]:
    return {
        "width": "100%",
        "padding": "0.7rem 0.85rem",
        "border": "1px solid var(--hub-color-line)",
        "borderRadius": "var(--hub-radius-sm)",
        "background": "rgba(255, 253, 248, 0.98)",
        "color": "var(--hub-color-text)",
        "fontFamily": "var(--hub-font-body)",
        "fontSize": "0.92rem",
        "outline": "none",
    }


def _text_area_style() -> dict[str, str]:
    return {
        **_select_style(),
        "minHeight": "7rem",
        "resize": "vertical",
        "lineHeight": "1.5",
    }


def _message_banner(message, *, tone: str) -> rx.Component:
    color = "tomato" if tone == "error" else "var(--hub-color-accent-strong)"
    border = (
        "1px solid rgba(191, 61, 48, 0.22)"
        if tone == "error"
        else "1px solid rgba(142, 89, 30, 0.22)"
    )
    background = "rgba(255, 244, 242, 0.95)" if tone == "error" else "rgba(255, 249, 239, 0.96)"
    return rx.cond(
        message != "",
        rx.box(
            rx.text(
                message,
                color=color,
                font_weight="600",
            ),
            width="100%",
            padding="0.9rem 1rem",
            border=border,
            border_radius="var(--hub-radius-md)",
            background=background,
            custom_attrs={
                "aria-live": "polite" if tone == "success" else "assertive",
                "role": "status" if tone == "success" else "alert",
            },
        ),
    )


def _field_error(message, *, error_id: str) -> rx.Component:
    return rx.cond(
        message != "",
        rx.text(
            message,
            id=error_id,
            color="tomato",
            font_size="0.9rem",
            custom_attrs={"role": "alert"},
        ),
    )


def _profile_field(
    *,
    label: str,
    field_id: str,
    control: rx.Component,
    error_message,
    helper_text: str | None = None,
) -> rx.Component:
    helper_id = f"{field_id}-helper"
    error_id = f"{field_id}-error"
    children: list[rx.Component] = [_field_label(label, field_id=field_id), control]
    if helper_text is not None:
        children.append(
            rx.text(
                helper_text,
                id=helper_id,
                font_size="0.9rem",
                color="var(--hub-color-text-muted)",
            )
        )
    children.append(_field_error(error_message, error_id=error_id))
    return rx.vstack(
        *children,
        align="start",
        gap="var(--hub-space-2)",
        width="100%",
    )


def _field_described_by(*ids: str) -> str:
    return " ".join(value for value in ids if value)


def _avatar_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.avatar(
                    fallback=ProfileSettingsState.avatar_fallback,
                    size="6",
                    radius="full",
                    color_scheme="bronze",
                    variant="soft",
                ),
                rx.vstack(
                    rx.text(
                        "Avatar",
                        font_size="1rem",
                        font_weight="600",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        ProfileSettingsState.avatar_status_label,
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.text(
                        ProfileSettingsState.avatar_filename_label,
                        font_size="0.9rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-1)",
                ),
                direction=rx.breakpoints(initial="column", sm="row"),
                align=rx.breakpoints(initial="start", sm="center"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            _message_banner(ProfileSettingsState.avatar_success_message, tone="success"),
            _message_banner(ProfileSettingsState.avatar_error_message, tone="error"),
            rx.upload(
                rx.vstack(
                    rx.badge(
                        "Upload avatar",
                        radius="full",
                        variant="soft",
                        color_scheme="bronze",
                        width="fit-content",
                    ),
                    rx.heading(
                        "Keep your public author identity recognizable.",
                        size="4",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.04em",
                        color="var(--hub-color-text)",
                    ),
                    rx.text(
                        ProfileSettingsState.avatar_upload_help_text,
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-3)",
                    width="100%",
                ),
                id=PROFILE_AVATAR_UPLOAD_ID,
                max_files=1,
                multiple=False,
                max_size=_SETTINGS.avatar_upload_max_bytes,
                accept=AVATAR_ACCEPT,
                on_drop=ProfileSettingsState.upload_avatar,
                width="100%",
                padding="var(--hub-space-5)",
                border="1px dashed var(--hub-color-line)",
                border_radius="var(--hub-radius-md)",
                background="rgba(255, 249, 239, 0.74)",
                cursor="pointer",
                custom_attrs={
                    "aria-label": "Upload profile avatar",
                    "data-testid": "avatar-upload",
                },
            ),
            rx.cond(
                ProfileSettingsState.has_avatar,
                rx.button(
                    "Remove avatar",
                    type="button",
                    size="3",
                    variant="soft",
                    on_click=ProfileSettingsState.remove_avatar,
                ),
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-5)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.8)",
    )


def _profile_form() -> rx.Component:
    return rx.form(
        rx.vstack(
            _message_banner(ProfileSettingsState.profile_success_message, tone="success"),
            _message_banner(ProfileSettingsState.profile_form_error, tone="error"),
            _avatar_card(),
            rx.grid(
                _profile_field(
                    label="Username",
                    field_id="profile-username",
                    control=_surface_input(
                        id="profile-username",
                        name="username",
                        value=ProfileSettingsState.profile_username,
                        on_change=ProfileSettingsState.set_profile_username,
                        placeholder="alice_validator",
                        required=True,
                        custom_attrs={
                            "aria-describedby": _field_described_by(
                                "profile-username-helper",
                                "profile-username-error",
                            ),
                            "aria-invalid": ProfileSettingsState.profile_username_error != "",
                        },
                    ),
                    error_message=ProfileSettingsState.profile_username_error,
                    helper_text="Use lowercase letters, numbers, or underscores.",
                ),
                _profile_field(
                    label="Display name",
                    field_id="profile-display-name",
                    control=_surface_input(
                        id="profile-display-name",
                        name="display_name",
                        value=ProfileSettingsState.profile_display_name,
                        on_change=ProfileSettingsState.set_profile_display_name,
                        placeholder="Alice Validator",
                        custom_attrs={
                            "aria-describedby": "profile-display-name-error",
                            "aria-invalid": ProfileSettingsState.profile_display_name_error != "",
                        },
                    ),
                    error_message=ProfileSettingsState.profile_display_name_error,
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            _profile_field(
                label="Bio",
                field_id="profile-bio",
                control=_surface_text_area(
                    id="profile-bio",
                    name="bio",
                    value=ProfileSettingsState.profile_bio,
                    on_change=ProfileSettingsState.set_profile_bio,
                    placeholder="Tell developers what you build on Xian.",
                    rows="5",
                    custom_attrs={
                        "aria-describedby": "profile-bio-error",
                        "aria-invalid": ProfileSettingsState.profile_bio_error != "",
                    },
                ),
                error_message=ProfileSettingsState.profile_bio_error,
            ),
            rx.grid(
                _profile_field(
                    label="Website URL",
                    field_id="profile-website-url",
                    control=_surface_input(
                        id="profile-website-url",
                        name="website_url",
                        type="url",
                        value=ProfileSettingsState.profile_website_url,
                        on_change=ProfileSettingsState.set_profile_website_url,
                        placeholder="https://example.com",
                        custom_attrs={
                            "aria-describedby": "profile-website-url-error",
                            "aria-invalid": ProfileSettingsState.profile_website_url_error != "",
                        },
                    ),
                    error_message=ProfileSettingsState.profile_website_url_error,
                ),
                _profile_field(
                    label="GitHub URL",
                    field_id="profile-github-url",
                    control=_surface_input(
                        id="profile-github-url",
                        name="github_url",
                        type="url",
                        value=ProfileSettingsState.profile_github_url,
                        on_change=ProfileSettingsState.set_profile_github_url,
                        placeholder="https://github.com/alice",
                        custom_attrs={
                            "aria-describedby": "profile-github-url-error",
                            "aria-invalid": ProfileSettingsState.profile_github_url_error != "",
                        },
                    ),
                    error_message=ProfileSettingsState.profile_github_url_error,
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            _profile_field(
                label="Xian profile URL",
                field_id="profile-xian-profile-url",
                control=_surface_input(
                    id="profile-xian-profile-url",
                    name="xian_profile_url",
                    type="url",
                    value=ProfileSettingsState.profile_xian_profile_url,
                    on_change=ProfileSettingsState.set_profile_xian_profile_url,
                    placeholder="https://xian.org/u/alice",
                    custom_attrs={
                        "aria-describedby": "profile-xian-profile-url-error",
                        "aria-invalid": ProfileSettingsState.profile_xian_profile_url_error != "",
                    },
                ),
                error_message=ProfileSettingsState.profile_xian_profile_url_error,
            ),
            rx.button(
                "Save profile",
                type="submit",
                size="3",
                width=rx.breakpoints(initial="100%", sm="auto"),
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        on_submit=ProfileSettingsState.submit_profile,
        width="100%",
        custom_attrs={"data-testid": "profile-settings-form"},
    )


def _profile_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.badge(
                "Public identity",
                radius="full",
                variant="soft",
                color_scheme="bronze",
                width="fit-content",
            ),
            rx.heading(
                "Profile settings",
                size="5",
                font_family="var(--hub-font-display)",
                letter_spacing="-0.05em",
                color="var(--hub-color-text)",
            ),
            rx.text(
                (
                    "Update the author identity shown across contract detail pages without "
                    "changing your active session or account credentials."
                ),
                color="var(--hub-color-text-muted)",
            ),
            _profile_form(),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        width="100%",
    )


def index() -> rx.Component:
    """Render the authenticated profile settings page."""
    return app_shell(
        rx.box(
            rx.cond(
                ProfileSettingsState.is_loading,
                page_loading_state(
                    title="Loading profile settings",
                    body="Preparing your editable profile details.",
                    test_id="profile-settings-loading",
                ),
                rx.cond(
                    ProfileSettingsState.has_load_error,
                    page_error_state(
                        title="Profile settings could not be loaded",
                        body=ProfileSettingsState.load_error_message,
                        test_id="profile-settings-error",
                        action=rx.link(
                            rx.button("Retry settings load", size="3", variant="soft"),
                            href=PROFILE_SETTINGS_ROUTE,
                            text_decoration="none",
                        ),
                    ),
                    page_section(
                        rx.grid(
                            _profile_panel(),
                            columns="1",
                            gap="var(--hub-space-6)",
                            width="100%",
                            align_items="start",
                        ),
                    ),
                ),
            ),
            width="100%",
            custom_attrs={"data-testid": "profile-settings-page"},
        ),
        page_title="Profile settings",
        page_intro=(
            "Manage your public developer identity and avatar from one authenticated workspace."
        ),
        page_kicker="Authenticated account",
        auth_state=ProfileSettingsState,
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
