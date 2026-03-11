"""Primary responsive application shell."""

from __future__ import annotations

import reflex as rx

from contracting_hub.states import AuthState
from contracting_hub.utils.meta import (
    APP_NAME,
    BROWSE_ROUTE,
    DEPLOYMENT_HISTORY_ROUTE,
    DEVELOPER_LEADERBOARD_ROUTE,
    HOME_ROUTE,
    LOGIN_ROUTE,
    PROFILE_SETTINGS_ROUTE,
    REGISTER_ROUTE,
)

SHELL_PILLARS = (
    "Curated catalog",
    "Immutable versions",
    "Playground deploys",
)
MAIN_CONTENT_ID = "main-content"


def _skip_to_content_button() -> rx.Component:
    """Render the keyboard-visible shortcut to the main content landmark."""
    return rx.el.button(
        "Skip to main content",
        type="button",
        class_name="hub-skip-link",
        on_click=[rx.scroll_to(MAIN_CONTENT_ID), rx.set_focus(MAIN_CONTENT_ID)],
        custom_attrs={"data-testid": "skip-to-content"},
    )


def _brand_lockup() -> rx.Component:
    """Render the shared brand block used in the global header."""
    return rx.link(
        rx.hstack(
            rx.box(
                rx.text(
                    "xh",
                    font_family="var(--hub-font-display)",
                    font_size="0.85rem",
                    font_weight="700",
                    letter_spacing="0.1em",
                    text_transform="uppercase",
                    color="var(--hub-color-accent-strong)",
                ),
                width="2.25rem",
                height="2.25rem",
                display="flex",
                align_items="center",
                justify_content="center",
                border_radius="var(--hub-radius-sm)",
                border="1px solid rgba(52, 43, 30, 0.08)",
                background="var(--hub-color-accent-soft)",
                flex_shrink="0",
            ),
            rx.text(
                APP_NAME,
                font_family="var(--hub-font-display)",
                font_size="1.05rem",
                font_weight="700",
                letter_spacing="-0.03em",
                color="var(--hub-color-text)",
            ),
            align="center",
            gap="var(--hub-space-3)",
        ),
        href=HOME_ROUTE,
        text_decoration="none",
        width="fit-content",
    )


def _header_badges() -> rx.Component:
    """Render shared status badges in the shell header."""
    return rx.flex(
        *[
            rx.text(
                pillar,
                font_size="0.78rem",
                color="var(--hub-color-text-muted)",
                letter_spacing="0.02em",
            )
            for pillar in SHELL_PILLARS
        ],
        wrap="wrap",
        gap="var(--hub-space-4)",
        justify=rx.breakpoints(initial="start", md="end"),
        display=rx.breakpoints(initial="none", md="flex"),
    )


def _shell_navigation() -> rx.Component:
    """Render the shared public navigation links."""
    return rx.el.nav(
        rx.flex(
            rx.link(
                "Home",
                href=HOME_ROUTE,
                text_decoration="none",
                color="var(--hub-color-text)",
                font_weight="500",
                font_size="0.92rem",
                class_name="hub-nav-link",
            ),
            rx.link(
                "Browse",
                href=BROWSE_ROUTE,
                text_decoration="none",
                color="var(--hub-color-text)",
                font_weight="500",
                font_size="0.92rem",
                class_name="hub-nav-link",
            ),
            rx.link(
                "Developers",
                href=DEVELOPER_LEADERBOARD_ROUTE,
                text_decoration="none",
                color="var(--hub-color-text)",
                font_weight="500",
                font_size="0.92rem",
                class_name="hub-nav-link",
            ),
            gap="var(--hub-space-5)",
            wrap="wrap",
            justify=rx.breakpoints(initial="start", md="end"),
        ),
        custom_attrs={"aria-label": "Primary"},
    )


def _guest_session_navigation() -> rx.Component:
    """Render header actions for anonymous visitors."""
    return rx.flex(
        rx.link(
            rx.button("Log in", size="2", variant="soft"),
            href=LOGIN_ROUTE,
            text_decoration="none",
        ),
        rx.link(
            rx.button("Create account", size="2", variant="solid"),
            href=REGISTER_ROUTE,
            text_decoration="none",
        ),
        gap="var(--hub-space-3)",
        wrap="wrap",
        justify=rx.breakpoints(initial="start", md="end"),
    )


def _authenticated_session_navigation(auth_state: type[AuthState]) -> rx.Component:
    """Render header account context for authenticated viewers."""
    return rx.flex(
        rx.box(
            rx.vstack(
                rx.text(
                    auth_state.current_identity_label,
                    font_size="0.92rem",
                    font_weight="600",
                    color="var(--hub-color-text)",
                ),
                rx.cond(
                    auth_state.has_current_identity_secondary,
                    rx.text(
                        auth_state.current_identity_secondary,
                        font_size="0.82rem",
                        color="var(--hub-color-text-muted)",
                    ),
                ),
                align="start",
                spacing="1",
            ),
            padding="0.8rem 1rem",
            border="1px solid var(--hub-color-line)",
            border_radius="var(--hub-radius-md)",
            background="rgba(255, 250, 242, 0.88)",
        ),
        rx.link(
            rx.button("Profile settings", size="2", variant="soft"),
            href=PROFILE_SETTINGS_ROUTE,
            text_decoration="none",
        ),
        rx.link(
            rx.button("Deployment history", size="2", variant="soft"),
            href=DEPLOYMENT_HISTORY_ROUTE,
            text_decoration="none",
        ),
        rx.button(
            "Log out",
            size="2",
            variant="soft",
            on_click=auth_state.logout_current_user,
        ),
        direction=rx.breakpoints(initial="column", md="row"),
        align=rx.breakpoints(initial="start", md="center"),
        gap="var(--hub-space-3)",
        width=rx.breakpoints(initial="100%", md="auto"),
        justify=rx.breakpoints(initial="start", md="end"),
    )


def _session_navigation(auth_state: type[AuthState]) -> rx.Component:
    """Render session-aware navigation controls inside the shell header."""
    return rx.el.nav(
        rx.cond(
            auth_state.is_authenticated,
            _authenticated_session_navigation(auth_state),
            _guest_session_navigation(),
        ),
        width=rx.breakpoints(initial="100%", md="auto"),
        custom_attrs={"aria-label": "Account", "data-testid": "session-navigation"},
    )


def _shell_frame(*children: rx.Component) -> rx.Component:
    """Constrain shared shell content to the global layout width."""
    return rx.box(
        *children,
        width="100%",
        max_width="var(--hub-layout-max-width)",
        margin="0 auto",
    )


def _page_intro(
    page_title: str | None,
    page_intro: str | None,
    page_kicker: str | None,
) -> rx.Component | None:
    """Render the optional page intro block shown above page content."""
    if page_title is None and page_intro is None and page_kicker is None:
        return None

    intro_children: list[rx.Component] = []
    if page_kicker is not None:
        intro_children.append(
            rx.badge(
                page_kicker,
                color_scheme="bronze",
                variant="soft",
                radius="full",
                width="fit-content",
                padding_x="0.9rem",
                padding_y="0.35rem",
            )
        )
    if page_title is not None:
        intro_children.append(
            rx.heading(
                page_title,
                size="8",
                font_family="var(--hub-font-display)",
                letter_spacing="-0.06em",
                color="var(--hub-color-text)",
            )
        )
    if page_intro is not None:
        intro_children.append(
            rx.text(
                page_intro,
                size="4",
                color="var(--hub-color-text-muted)",
                max_width="42rem",
            )
        )

    return rx.box(
        rx.vstack(
            *intro_children,
            align="start",
            gap="var(--hub-space-3)",
        ),
        width="100%",
        padding=rx.breakpoints(
            initial="var(--hub-space-5)",
            md="var(--hub-space-7) var(--hub-space-6)",
        ),
        border_bottom="1px solid var(--hub-color-line)",
        class_name="hub-fade-in",
    )


def _shell_header(auth_state: type[AuthState]) -> rx.Component:
    """Render the persistent application header."""
    return rx.el.header(
        _shell_frame(
            rx.flex(
                rx.flex(
                    _brand_lockup(),
                    _shell_navigation(),
                    align="center",
                    gap="var(--hub-space-6)",
                    direction=rx.breakpoints(initial="column", sm="row"),
                ),
                rx.flex(
                    _header_badges(),
                    _session_navigation(auth_state),
                    direction=rx.breakpoints(initial="column", lg="row"),
                    align=rx.breakpoints(initial="start", lg="center"),
                    gap="var(--hub-space-4)",
                    width=rx.breakpoints(initial="100%", lg="auto"),
                ),
                direction=rx.breakpoints(initial="column", lg="row"),
                align=rx.breakpoints(initial="start", lg="center"),
                justify="between",
                gap="var(--hub-space-4)",
            )
        ),
        width="100%",
        padding="var(--hub-space-4) var(--hub-layout-gutter)",
        border_bottom="1px solid var(--hub-color-line)",
        background="rgba(244, 239, 228, 0.85)",
        backdrop_filter="blur(12px)",
        position="sticky",
        top="0",
        z_index="10",
        custom_attrs={"role": "banner"},
    )


def _shell_footer() -> rx.Component:
    """Render the shared shell footer."""
    return rx.el.footer(
        _shell_frame(
            rx.flex(
                rx.text(
                    APP_NAME,
                    font_family="var(--hub-font-display)",
                    font_size="0.88rem",
                    font_weight="600",
                    color="var(--hub-color-text-muted)",
                ),
                rx.text(
                    "Curated Xian smart contracts",
                    color="var(--hub-color-text-muted)",
                    font_size="0.82rem",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                align=rx.breakpoints(initial="start", md="center"),
                justify="between",
                gap="var(--hub-space-3)",
            )
        ),
        width="100%",
        padding="var(--hub-space-5) var(--hub-layout-gutter)",
        border_top="1px solid var(--hub-color-line)",
        custom_attrs={"role": "contentinfo"},
    )


def app_shell(
    *children: rx.Component,
    page_title: str | None = None,
    page_intro: str | None = None,
    page_kicker: str | None = None,
    auth_state: type[AuthState] = AuthState,
) -> rx.Component:
    """Wrap page content in the shared responsive shell."""
    content_children: list[rx.Component] = []
    intro = _page_intro(page_title=page_title, page_intro=page_intro, page_kicker=page_kicker)
    if intro is not None:
        content_children.append(intro)
    content_children.extend(children)

    return rx.box(
        _skip_to_content_button(),
        rx.flex(
            _shell_header(auth_state),
            rx.el.main(
                _shell_frame(
                    rx.vstack(
                        *content_children,
                        width="100%",
                        gap="var(--hub-layout-section-gap)",
                        class_name="hub-stagger",
                    )
                ),
                width="100%",
                flex="1",
                padding="var(--hub-space-7) var(--hub-layout-gutter)",
                id=MAIN_CONTENT_ID,
                tab_index=-1,
            ),
            _shell_footer(),
            direction="column",
            min_height="100vh",
        ),
        width="100%",
        min_height="100vh",
        custom_attrs={"data-testid": "app-shell"},
    )


__all__ = ["SHELL_PILLARS", "app_shell"]
