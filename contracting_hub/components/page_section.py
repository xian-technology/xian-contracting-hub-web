"""Shared page-level layout primitives."""

import reflex as rx


def page_section(*children: rx.Component, **props: object) -> rx.Component:
    """Wrap page content in a shared bordered section surface."""
    section_props = {
        "width": "100%",
        "padding": "var(--hub-space-7)",
        "border": "1px solid var(--hub-color-line)",
        "border_radius": "var(--hub-radius-lg)",
        "background": "var(--hub-color-surface)",
        "box_shadow": "var(--hub-shadow-panel)",
        **props,
    }
    return rx.box(*children, **section_props)
