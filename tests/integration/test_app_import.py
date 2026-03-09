from __future__ import annotations

import pytest

from contracting_hub.components.app_shell import SHELL_PILLARS
from contracting_hub.utils.meta import APP_NAME, HOME_TAGLINE

pytestmark = pytest.mark.smoke


def _rendered_text(node: dict[str, object]) -> list[str]:
    text_fragments: list[str] = []
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue

        contents = current.get("contents")
        if isinstance(contents, str):
            text_fragments.append(contents.strip('"'))

        stack.extend(reversed(current.get("children", [])))

    return text_fragments


def test_app_module_exports_reflex_app(app_module: dict[str, object]) -> None:
    assert app_module["app"] is not None
    assert app_module["app"].theme is not None
    assert app_module["app"].style["--hub-layout-max-width"] == "76rem"
    assert app_module["app"].stylesheets


def test_home_page_uses_the_shared_shell(app_module: dict[str, object]) -> None:
    rendered = app_module["index"]().render()
    rendered_text = _rendered_text(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"app-shell"' in rendered["props"]
    assert APP_NAME in rendered_text
    assert HOME_TAGLINE in rendered_text
    assert "Featured Contracts" in rendered_text
    assert "Trending Now" in rendered_text
    assert "Recently Updated" in rendered_text
    assert "Recently Deployed" in rendered_text
    assert "Curated repository scaffolding for Xian smart contracts." in rendered_text
    assert "Designed for search, diffs, lint feedback, and deployments." in rendered_text
    for pillar in SHELL_PILLARS:
        assert pillar in rendered_text
