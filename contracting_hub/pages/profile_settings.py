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


def _field_label(label: str) -> rx.Component:
    return rx.text(
        label,
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
        "padding": "0.85rem 1rem",
        "border": "1px solid var(--hub-color-line)",
        "borderRadius": "var(--hub-radius-md)",
        "background": "rgba(255, 252, 246, 0.98)",
        "color": "var(--hub-color-text)",
        "fontFamily": "var(--hub-font-body)",
        "fontSize": "0.98rem",
        "outline": "none",
        "boxShadow": "inset 0 1px 0 rgba(255, 255, 255, 0.75)",
    }


def _text_area_style() -> dict[str, str]:
    return {
        **_select_style(),
        "minHeight": "8rem",
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
        ),
    )


def _field_error(message) -> rx.Component:
    return rx.cond(
        message != "",
        rx.text(
            message,
            color="tomato",
            font_size="0.9rem",
        ),
    )


def _profile_field(
    *,
    label: str,
    control: rx.Component,
    error_message,
    helper_text: str | None = None,
) -> rx.Component:
    children: list[rx.Component] = [_field_label(label), control]
    if helper_text is not None:
        children.append(
            rx.text(
                helper_text,
                font_size="0.9rem",
                color="var(--hub-color-text-muted)",
            )
        )
    children.append(_field_error(error_message))
    return rx.vstack(
        *children,
        align="start",
        gap="var(--hub-space-2)",
        width="100%",
    )


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
                custom_attrs={"data-testid": "avatar-upload"},
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
                    control=_surface_input(
                        name="username",
                        value=ProfileSettingsState.profile_username,
                        on_change=ProfileSettingsState.set_profile_username,
                        placeholder="alice_validator",
                        required=True,
                    ),
                    error_message=ProfileSettingsState.profile_username_error,
                    helper_text="Use lowercase letters, numbers, or underscores.",
                ),
                _profile_field(
                    label="Display name",
                    control=_surface_input(
                        name="display_name",
                        value=ProfileSettingsState.profile_display_name,
                        on_change=ProfileSettingsState.set_profile_display_name,
                        placeholder="Alice Validator",
                    ),
                    error_message=ProfileSettingsState.profile_display_name_error,
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            _profile_field(
                label="Bio",
                control=_surface_text_area(
                    name="bio",
                    value=ProfileSettingsState.profile_bio,
                    on_change=ProfileSettingsState.set_profile_bio,
                    placeholder="Tell developers what you build on Xian.",
                    rows="5",
                ),
                error_message=ProfileSettingsState.profile_bio_error,
            ),
            rx.grid(
                _profile_field(
                    label="Website URL",
                    control=_surface_input(
                        name="website_url",
                        type="url",
                        value=ProfileSettingsState.profile_website_url,
                        on_change=ProfileSettingsState.set_profile_website_url,
                        placeholder="https://example.com",
                    ),
                    error_message=ProfileSettingsState.profile_website_url_error,
                ),
                _profile_field(
                    label="GitHub URL",
                    control=_surface_input(
                        name="github_url",
                        type="url",
                        value=ProfileSettingsState.profile_github_url,
                        on_change=ProfileSettingsState.set_profile_github_url,
                        placeholder="https://github.com/alice",
                    ),
                    error_message=ProfileSettingsState.profile_github_url_error,
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                gap="var(--hub-space-4)",
                width="100%",
            ),
            _profile_field(
                label="Xian profile URL",
                control=_surface_input(
                    name="xian_profile_url",
                    type="url",
                    value=ProfileSettingsState.profile_xian_profile_url,
                    on_change=ProfileSettingsState.set_profile_xian_profile_url,
                    placeholder="https://xian.org/u/alice",
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


def _saved_target_row(target) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.flex(
                        rx.text(
                            target["label"],
                            font_size="1rem",
                            font_weight="600",
                            color="var(--hub-color-text)",
                        ),
                        rx.cond(
                            target["is_default"],
                            rx.badge(
                                target["default_badge_label"],
                                radius="full",
                                variant="soft",
                                color_scheme="bronze",
                            ),
                        ),
                        wrap="wrap",
                        gap="var(--hub-space-2)",
                        align="center",
                    ),
                    rx.text(
                        target["playground_id"],
                        font_family="var(--hub-font-mono)",
                        font_size="0.95rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    rx.text(
                        "Last used: ",
                        target["last_used_label"],
                        font_size="0.9rem",
                        color="var(--hub-color-text-muted)",
                    ),
                    align="start",
                    gap="var(--hub-space-1)",
                    width="100%",
                ),
                rx.flex(
                    rx.button(
                        "Edit",
                        type="button",
                        size="2",
                        variant="soft",
                        on_click=ProfileSettingsState.edit_playground_target(target["id"]),
                    ),
                    rx.button(
                        "Delete",
                        type="button",
                        size="2",
                        variant="soft",
                        color_scheme="tomato",
                        on_click=ProfileSettingsState.delete_playground_target(target["id"]),
                    ),
                    direction=rx.breakpoints(initial="column", sm="row"),
                    gap="var(--hub-space-2)",
                    width=rx.breakpoints(initial="100%", md="auto"),
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-4)",
                width="100%",
            ),
            align="start",
            gap="var(--hub-space-3)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-4)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-md)",
        background="rgba(255, 250, 242, 0.8)",
        custom_attrs={"data-testid": "playground-target-row"},
    )


def _saved_targets_list() -> rx.Component:
    return rx.cond(
        ProfileSettingsState.has_playground_targets,
        rx.vstack(
            rx.foreach(ProfileSettingsState.playground_targets, _saved_target_row),
            width="100%",
            gap="var(--hub-space-3)",
        ),
        rx.box(
            rx.vstack(
                rx.heading(
                    "No saved playground targets yet.",
                    size="3",
                    font_family="var(--hub-font-display)",
                    color="var(--hub-color-text)",
                ),
                rx.text(
                    "Add a playground ID here so deployment flows can reuse it later.",
                    color="var(--hub-color-text-muted)",
                ),
                align="start",
                gap="var(--hub-space-2)",
            ),
            width="100%",
            padding="var(--hub-space-5)",
            border="1px dashed var(--hub-color-line)",
            border_radius="var(--hub-radius-md)",
            background="rgba(255, 250, 242, 0.6)",
        ),
    )


def _playground_targets_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.badge(
                "Deploy faster",
                radius="full",
                variant="soft",
                color_scheme="bronze",
                width="fit-content",
            ),
            rx.heading(
                "Saved playground targets",
                size="5",
                font_family="var(--hub-font-display)",
                letter_spacing="-0.05em",
                color="var(--hub-color-text)",
            ),
            rx.text(
                (
                    "Save reusable playground IDs for future deployment flows, keep one default "
                    "target selected, and update or remove old entries without "
                    "touching your account."
                ),
                color="var(--hub-color-text-muted)",
            ),
            rx.text(
                ProfileSettingsState.playground_target_count_label,
                font_size="0.9rem",
                color="var(--hub-color-text-muted)",
            ),
            _message_banner(ProfileSettingsState.playground_target_success_message, tone="success"),
            _message_banner(ProfileSettingsState.playground_target_form_error, tone="error"),
            rx.box(
                rx.vstack(
                    rx.heading(
                        ProfileSettingsState.playground_target_form_title,
                        size="4",
                        font_family="var(--hub-font-display)",
                        letter_spacing="-0.04em",
                        color="var(--hub-color-text)",
                    ),
                    rx.form(
                        rx.vstack(
                            _profile_field(
                                label="Label",
                                control=_surface_input(
                                    name="label",
                                    value=ProfileSettingsState.playground_target_label,
                                    on_change=ProfileSettingsState.set_playground_target_label,
                                    placeholder="Sandbox primary",
                                    required=True,
                                ),
                                error_message=ProfileSettingsState.playground_target_label_error,
                            ),
                            _profile_field(
                                label="Playground ID",
                                control=_surface_input(
                                    name="playground_id",
                                    value=ProfileSettingsState.playground_target_playground_id,
                                    on_change=ProfileSettingsState.set_playground_target_playground_id,
                                    placeholder="sandbox-alpha",
                                    required=True,
                                ),
                                error_message=(
                                    ProfileSettingsState.playground_target_playground_id_error
                                ),
                            ),
                            _profile_field(
                                label="Default target",
                                control=rx.el.select(
                                    rx.el.option("No", value="no"),
                                    rx.el.option("Yes", value="yes"),
                                    name="is_default",
                                    value=ProfileSettingsState.playground_target_default_choice,
                                    on_change=ProfileSettingsState.set_playground_target_default_choice,
                                    style=_select_style(),
                                ),
                                error_message="",
                            ),
                            rx.flex(
                                rx.button(
                                    ProfileSettingsState.playground_target_submit_label,
                                    type="submit",
                                    size="3",
                                    width=rx.breakpoints(initial="100%", sm="auto"),
                                ),
                                rx.cond(
                                    ProfileSettingsState.is_editing_playground_target,
                                    rx.button(
                                        "Cancel",
                                        type="button",
                                        size="3",
                                        variant="soft",
                                        on_click=ProfileSettingsState.reset_playground_target_form,
                                        width=rx.breakpoints(initial="100%", sm="auto"),
                                    ),
                                ),
                                direction=rx.breakpoints(initial="column", sm="row"),
                                gap="var(--hub-space-3)",
                                width="100%",
                            ),
                            align="start",
                            gap="var(--hub-space-4)",
                            width="100%",
                        ),
                        on_submit=ProfileSettingsState.submit_playground_target,
                        width="100%",
                        custom_attrs={"data-testid": "playground-target-form"},
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
            ),
            _saved_targets_list(),
            align="start",
            gap="var(--hub-space-5)",
            width="100%",
        ),
        width="100%",
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
                    body="Preparing your editable profile details and saved playground targets.",
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
                            _playground_targets_panel(),
                            columns=rx.breakpoints(initial="1", xl="2"),
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
            "Manage your public developer identity, avatar, and saved playground targets "
            "from one authenticated workspace."
        ),
        page_kicker="Authenticated account",
        auth_state=ProfileSettingsState,
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
