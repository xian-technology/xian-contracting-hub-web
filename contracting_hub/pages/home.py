"""Public landing page for the smart contract hub."""

import reflex as rx

from contracting_hub.components import page_section
from contracting_hub.theme import ACCENT_COLOR, MUTED_TEXT_COLOR
from contracting_hub.utils.meta import APP_NAME, HOME_BADGE_TEXT, HOME_ROUTE, HOME_TAGLINE

ROUTE = HOME_ROUTE


def index() -> rx.Component:
    """Render the initial public landing page."""
    return page_section(
        rx.vstack(
            rx.badge(HOME_BADGE_TEXT, color_scheme=ACCENT_COLOR),
            rx.heading(APP_NAME, size="8"),
            rx.text(
                HOME_TAGLINE,
                size="4",
                color_scheme=MUTED_TEXT_COLOR,
            ),
            spacing="4",
            align="start",
        )
    )
