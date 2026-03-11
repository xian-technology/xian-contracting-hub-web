"""Global design tokens and Reflex theme configuration."""

from __future__ import annotations

from collections.abc import Mapping

import reflex as rx

ACCENT_COLOR = "grass"
MUTED_TEXT_COLOR = "sand"

FONT_FAMILIES: dict[str, str] = {
    "display": '"Space Grotesk", "Avenir Next", "Segoe UI", sans-serif',
    "body": '"IBM Plex Sans", "Segoe UI", sans-serif',
    "mono": '"IBM Plex Mono", "SFMono-Regular", monospace',
}

COLOR_TOKENS: dict[str, str] = {
    "canvas": "#f5efe2",
    "canvas_emphasis": "#e9deca",
    "surface": "rgba(255, 251, 244, 0.92)",
    "surface_strong": "#fff9ef",
    "line": "rgba(52, 43, 30, 0.10)",
    "text": "#1f1a12",
    "text_muted": "#5f5648",
    "accent": "#4d7a33",
    "accent_strong": "#2e4d18",
    "accent_soft": "#d9e7c7",
    "highlight": "#bc7b28",
    "highlight_soft": "#f3debe",
}

SPACING_SCALE: dict[str, str] = {
    "1": "0.25rem",
    "2": "0.5rem",
    "3": "0.75rem",
    "4": "1rem",
    "5": "1.25rem",
    "6": "1.5rem",
    "7": "2rem",
    "8": "3rem",
    "9": "4rem",
}

RADIUS_SCALE: dict[str, str] = {
    "sm": "0.375rem",
    "md": "0.5rem",
    "lg": "0.75rem",
    "pill": "999px",
}

SHADOW_TOKENS: dict[str, str] = {
    "panel": "0 1px 3px rgba(40, 31, 17, 0.06), 0 6px 16px rgba(40, 31, 17, 0.04)",
    "header": "0 1px 2px rgba(40, 31, 17, 0.05)",
    "card_hover": "0 2px 8px rgba(40, 31, 17, 0.08), 0 12px 28px rgba(40, 31, 17, 0.06)",
}

LAYOUT_TOKENS: dict[str, str] = {
    "max_width": "76rem",
    "gutter": "clamp(1rem, 3vw, 2.5rem)",
    "section_gap": "var(--hub-space-7)",
}

APP_STYLESHEETS = [
    (
        "https://fonts.googleapis.com/css2?"
        "family=IBM+Plex+Mono:wght@400;500&"
        "family=IBM+Plex+Sans:wght@400;500;600;700&"
        "family=Space+Grotesk:wght@500;700&display=swap"
    ),
    "/accessibility.css",
]


def _css_variables(prefix: str, tokens: Mapping[str, str]) -> dict[str, str]:
    """Convert token dictionaries into CSS custom properties."""
    return {f"--hub-{prefix}-{name.replace('_', '-')}": value for name, value in tokens.items()}


APP_THEME = rx.theme(
    accent_color=ACCENT_COLOR,
    gray_color=MUTED_TEXT_COLOR,
    panel_background="translucent",
    radius="medium",
    scaling="100%",
    has_background=False,
)

APP_STYLE: dict[str, str] = {
    **_css_variables("font", FONT_FAMILIES),
    **_css_variables("color", COLOR_TOKENS),
    **_css_variables("space", SPACING_SCALE),
    **_css_variables("radius", RADIUS_SCALE),
    **_css_variables("shadow", SHADOW_TOKENS),
    **_css_variables("layout", LAYOUT_TOKENS),
    "background": "#f4efe4",
    "color": "var(--hub-color-text)",
    "font_family": "var(--hub-font-body)",
    "line_height": "1.6",
    "min_height": "100vh",
}

__all__ = [
    "ACCENT_COLOR",
    "APP_STYLE",
    "APP_STYLESHEETS",
    "APP_THEME",
    "COLOR_TOKENS",
    "FONT_FAMILIES",
    "LAYOUT_TOKENS",
    "MUTED_TEXT_COLOR",
    "RADIUS_SCALE",
    "SHADOW_TOKENS",
    "SPACING_SCALE",
]
