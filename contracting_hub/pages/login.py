"""Anonymous login page."""

from __future__ import annotations

import reflex as rx

from contracting_hub.components import app_shell, page_section
from contracting_hub.states import AuthState
from contracting_hub.utils.meta import LOGIN_ROUTE, REGISTER_ROUTE

ROUTE = LOGIN_ROUTE
ON_LOAD = AuthState.load_login_page


def _field(
    *,
    label: str,
    name: str,
    placeholder: str,
    error_message,
    input_type: str = "text",
) -> rx.Component:
    field_id = f"login-{name}"
    error_id = f"{field_id}-error"
    props: dict[str, object] = {
        "id": field_id,
        "name": name,
        "type": input_type,
        "placeholder": placeholder,
        "size": "3",
        "variant": "surface",
        "width": "100%",
        "required": True,
        "custom_attrs": {
            "aria-describedby": error_id,
            "aria-invalid": error_message != "",
        },
    }

    return rx.vstack(
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
        rx.cond(
            error_message != "",
            rx.text(
                error_message,
                id=error_id,
                color="tomato",
                font_size="0.9rem",
                custom_attrs={"role": "alert"},
            ),
        ),
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


def _benefits_panel() -> rx.Component:
    return rx.vstack(
        rx.badge(
            "Developer access",
            radius="full",
            variant="soft",
            color_scheme="bronze",
            width="fit-content",
        ),
        rx.heading(
            "Sign in to keep contract research moving.",
            size="6",
            font_family="var(--hub-font-display)",
            letter_spacing="-0.05em",
            color="var(--hub-color-text)",
        ),
        rx.text(
            (
                "Authenticated sessions unlock stars, ratings, saved playground IDs, "
                "and deployment actions without changing the public browse experience."
            ),
            color="var(--hub-color-text-muted)",
            max_width="32rem",
        ),
        rx.grid(
            rx.box(
                rx.text(
                    "Engage",
                    font_size="0.78rem",
                    text_transform="uppercase",
                    letter_spacing="0.08em",
                    color="var(--hub-color-text-muted)",
                ),
                rx.text(
                    "Star releases and rate curated contracts from the detail page.",
                    color="var(--hub-color-text)",
                ),
                padding="1rem",
                border="1px solid var(--hub-color-line)",
                border_radius="var(--hub-radius-md)",
                background="rgba(255, 249, 239, 0.82)",
            ),
            rx.box(
                rx.text(
                    "Deploy",
                    font_size="0.78rem",
                    text_transform="uppercase",
                    letter_spacing="0.08em",
                    color="var(--hub-color-text-muted)",
                ),
                rx.text(
                    "Reuse saved playground targets when you send a version to Xian.",
                    color="var(--hub-color-text)",
                ),
                padding="1rem",
                border="1px solid var(--hub-color-line)",
                border_radius="var(--hub-radius-md)",
                background="rgba(255, 249, 239, 0.82)",
            ),
            columns=rx.breakpoints(initial="1", sm="2"),
            gap="var(--hub-space-3)",
            width="100%",
        ),
        align="start",
        gap="var(--hub-space-4)",
        width="100%",
    )


def _login_form() -> rx.Component:
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
                "Welcome back",
                size="5",
                font_family="var(--hub-font-display)",
                letter_spacing="-0.05em",
                color="var(--hub-color-text)",
                id="login-form-title",
            ),
            rx.text(
                "Use your email and password to restore your session.",
                color="var(--hub-color-text-muted)",
            ),
            _error_banner(AuthState.login_form_error),
            rx.form(
                rx.el.fieldset(
                    rx.el.legend("Log in credentials", class_name="hub-visually-hidden"),
                    rx.vstack(
                        _field(
                            label="Email",
                            name="email",
                            placeholder="alice@example.com",
                            error_message=AuthState.login_email_error,
                            input_type="email",
                        ),
                        _field(
                            label="Password",
                            name="password",
                            placeholder="Enter your password",
                            error_message=AuthState.login_password_error,
                            input_type="password",
                        ),
                        rx.button(
                            "Log in",
                            type="submit",
                            size="3",
                            width="100%",
                        ),
                        rx.text(
                            "Need an account?",
                            color="var(--hub-color-text-muted)",
                        ),
                        rx.link(
                            "Create one",
                            href=REGISTER_ROUTE,
                            color="var(--hub-color-accent-strong)",
                            text_decoration="underline",
                        ),
                        align="start",
                        gap="var(--hub-space-4)",
                        width="100%",
                    ),
                    style=fieldset_style,
                ),
                on_submit=AuthState.submit_login,
                width="100%",
                custom_attrs={"aria-labelledby": "login-form-title", "data-testid": "login-form"},
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
    """Render the public login page."""
    return app_shell(
        page_section(
            rx.grid(
                _benefits_panel(),
                _login_form(),
                columns=rx.breakpoints(initial="1", lg="2"),
                gap="var(--hub-space-6)",
                width="100%",
                align_items="start",
            ),
            custom_attrs={"data-testid": "login-page"},
        ),
        page_title="Log in",
        page_intro=(
            "Restore your developer session to save favorites, rate contracts, "
            "and prepare deployments."
        ),
        page_kicker="Account access",
    )


__all__ = ["ON_LOAD", "ROUTE", "index"]
