"""Shared page-level layout primitives."""

import reflex as rx


def page_section(*children: rx.Component, **props: object) -> rx.Component:
    """Wrap page content in the shared root container."""
    container_props = {"padding_y": "5rem", **props}
    return rx.container(*children, **container_props)
