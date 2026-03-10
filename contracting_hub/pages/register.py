"""Anonymous registration page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import app_shell, page_section
from contracting_hub.states import AuthState
from contracting_hub.utils.meta import LOGIN_ROUTE, REGISTER_ROUTE

ROUTE = REGISTER_ROUTE
ON_LOAD = AuthState.load_registration_page


def _field(
    *,
    label: str,
    name: str,
    placeholder: str,
    error_message,
    input_type: str = "text",
    required: bool = True,
    helper_text: str | None = None,
) -> rx.Component:
    field_id = f"register-{name}"
    helper_id = f"{field_id}-helper"
    error_id = f"{field_id}-error"
    described_by = " ".join(
        value for value in (helper_id if helper_text is not None else "", error_id) if value
    )
    props: dict[str, object] = {
        "id": field_id,
        "name": name,
        "type": input_type,
        "placeholder": placeholder,
        "size": "3",
        "variant": "surface",
        "width": "100%",
        "required": required,
        "custom_attrs": {
            "aria-describedby": described_by,
            "aria-invalid": error_message != "",
        },
    }

    children: list[rx.Component] = [
        rx.el.label(
            label,
            html_for=field_id,
            font_size="0.78rem",
            font_weight="600",
            text_transform="uppercase",
            letter_spacing="0.08em",
            color="var(--hub-color-text-muted)",
        ),
        rx.input(**props),
    ]
    if helper_text is not None:
        children.append(
            rx.text(
                helper_text,
                id=helper_id,
                font_size="0.9rem",
                color="var(--hub-color-text-muted)",
            )
        )
    children.append(
        rx.cond(
            error_message != "",
            rx.text(
                error_message,
                id=error_id,
                color="tomato",
                font_size="0.9rem",
                custom_attrs={"role": "alert"},
            ),
        )
    )

    return rx.vstack(
        *children,
        align="start",
        gap="var(--hub-space-2)",
        width="100%",
    )


def _error_banner(message) -> rx.Component:
    return rx.cond(
        message != "",
        rx.box(
            rx.text(
                message,
                color="tomato",
                font_weight="600",
            ),
            width="100%",
            padding="0.9rem 1rem",
            border="1px solid rgba(191, 61, 48, 0.22)",
            border_radius="var(--hub-radius-md)",
            background="rgba(255, 244, 242, 0.95)",
            custom_attrs={"role": "alert"},
        ),
    )


def _identity_panel() -> rx.Component:
    return rx.vstack(
        rx.badge(
            "Create identity",
            radius="full",
            variant="soft",
            color_scheme="bronze",
            width="fit-content",
        ),
        rx.heading(
            "Register once, then keep your Xian workflow connected.",
            size="6",
            font_family="var(--hub-font-display)",
            letter_spacing="-0.05em",
            color="var(--hub-color-text)",
        ),
        rx.text(
            (
                "Each account gets a public developer profile and a private session "
                "for contract engagement, saved playground targets, and later admin promotion."
            ),
            color="var(--hub-color-text-muted)",
            max_width="32rem",
        ),
        rx.vstack(
            rx.text(
                "What you set here",
                font_size="0.78rem",
                text_transform="uppercase",
                letter_spacing="0.08em",
                color="var(--hub-color-text-muted)",
            ),
            rx.text("A unique username for your public author identity."),
            rx.text("An email/password pair for secure cookie-backed sessions."),
            rx.text("An optional display name shown across public contract pages."),
            align="start",
            gap="var(--hub-space-2)",
            width="100%",
            padding="1rem",
            border="1px solid var(--hub-color-line)",
            border_radius="var(--hub-radius-md)",
            background="rgba(255, 249, 239, 0.82)",
        ),
        align="start",
        gap="var(--hub-space-4)",
        width="100%",
    )


def _registration_form() -> rx.Component:
    fieldset_style = {
        "border": "none",
        "margin": "0",
        "padding": "0",
        "minWidth": "0",
        "width": "100%",
    }
    return rx.box(
        rx.vstack(
            rx.heading(
                "Create your account",
                size="5",
                font_family="var(--hub-font-display)",
                letter_spacing="-0.05em",
                color="var(--hub-color-text)",
                id="register-form-title",
            ),
            rx.text(
                "Registration signs you in immediately so the authenticated shell is ready.",
                color="var(--hub-color-text-muted)",
            ),
            _error_banner(AuthState.register_form_error),
            rx.form(
                rx.el.fieldset(
                    rx.el.legend("Registration details", class_name="hub-visually-hidden"),
                    rx.vstack(
                        _field(
                            label="Username",
                            name="username",
                            placeholder="alice_validator",
                            error_message=AuthState.register_username_error,
                            helper_text="Use lowercase letters, numbers, or underscores.",
                        ),
                        _field(
                            label="Email",
                            name="email",
                            placeholder="alice@example.com",
                            error_message=AuthState.register_email_error,
                            input_type="email",
                        ),
                        _field(
                            label="Display name",
                            name="display_name",
                            placeholder="Alice Validator",
                            error_message="",
                            required=False,
                            helper_text=(
                                "Optional, but useful when you publish public author metadata."
                            ),
                        ),
                        _field(
                            label="Password",
                            name="password",
                            placeholder="Choose a secure password",
                            error_message=AuthState.register_password_error,
                            input_type="password",
                            helper_text="Must be at least 8 characters long.",
                        ),
                        rx.button(
                            "Create account",
                            type="submit",
                            size="3",
                            width="100%",
                        ),
                        rx.text(
                            "Already registered?",
                            color="var(--hub-color-text-muted)",
                        ),
                        rx.link(
                            "Log in",
                            href=LOGIN_ROUTE,
                            color="var(--hub-color-accent-strong)",
                            text_decoration="underline",
                        ),
                        align="start",
                        gap="var(--hub-space-4)",
                        width="100%",
                    ),
                    style=fieldset_style,
                ),
                on_submit=AuthState.submit_registration,
                width="100%",
                custom_attrs={
                    "aria-labelledby": "register-form-title",
                    "data-testid": "register-form",
                },
            ),
            align="start",
            gap="var(--hub-space-4)",
            width="100%",
        ),
        width="100%",
        padding="var(--hub-space-6)",
        border="1px solid var(--hub-color-line)",
        border_radius="var(--hub-radius-lg)",
        background="rgba(255, 252, 246, 0.97)",
        box_shadow="var(--hub-shadow-panel)",
    )


def index() -> rx.Component:
    """Render the public registration page."""
    return app_shell(
        page_section(
            rx.grid(
                _identity_panel(),
                _registration_form(),
                columns=rx.breakpoints(initial="1", lg="2"),
                gap="var(--hub-space-6)",
                width="100%",
                align_items="start",
            ),
            custom_attrs={"data-testid": "register-page"},
        ),
        page_title="Create account",
        page_intro=(
            "Register a developer identity for personalized catalog actions and "
            "cookie-backed session access."
        ),
        page_kicker="Developer registration",
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
