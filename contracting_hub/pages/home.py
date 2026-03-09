"""Public landing page for the smart contract hub."""

import reflex as rx

from contracting_hub.components import app_shell, page_section
from contracting_hub.utils.meta import APP_NAME, HOME_BADGE_TEXT, HOME_ROUTE, HOME_TAGLINE

ROUTE = HOME_ROUTE


def _feature_panel(label: str, title: str, body: str) -> rx.Component:
    """Render a concise product foundation panel."""
    return page_section(
        rx.vstack(
            rx.badge(
                label,
                radius="full",
                variant="soft",
                color_scheme="bronze",
                width="fit-content",
                padding_x="0.8rem",
                padding_y="0.3rem",
            ),
            rx.heading(
                title,
                size="5",
                font_family="var(--hub-font-display)",
                letter_spacing="-0.04em",
                color="var(--hub-color-text)",
            ),
            rx.text(
                body,
                color="var(--hub-color-text-muted)",
            ),
            align="start",
            gap="var(--hub-space-4)",
        ),
        height="100%",
    )


def index() -> rx.Component:
    """Render the initial public landing page."""
    return app_shell(
        rx.grid(
            _feature_panel(
                "Discover",
                "Curated contract browsing",
                "A shell built for stable routes, search-first navigation, and readable metadata.",
            ),
            _feature_panel(
                "Inspect",
                "Version-aware detail views",
                (
                    "The shared layout leaves room for source code, lint signals, "
                    "changelogs, and diffs."
                ),
            ),
            _feature_panel(
                "Deploy",
                "Operational actions without clutter",
                (
                    "Authenticated workflows can attach ratings, stars, and "
                    "playground deployment states later."
                ),
            ),
            columns=rx.breakpoints(initial="1", md="3"),
            gap="var(--hub-space-5)",
            width="100%",
        ),
        page_kicker=HOME_BADGE_TEXT,
        page_title=APP_NAME,
        page_intro=HOME_TAGLINE,
    )
