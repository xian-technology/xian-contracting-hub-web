from __future__ import annotations

from contracting_hub.pages.browse import index
from contracting_hub.utils.meta import BROWSE_ROUTE


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


def test_app_registers_the_public_browse_route(app_module: dict[str, object]) -> None:
    assert BROWSE_ROUTE.lstrip("/") in app_module["app"]._unevaluated_pages


def test_browse_page_renders_filters_sort_controls_and_public_shell() -> None:
    rendered = index().render()
    rendered_text = _rendered_text(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"app-shell"' in rendered["props"]
    assert "Browse Contracts" in rendered_text
    assert "Browse Controls" in rendered_text
    assert "Apply filters" in rendered_text
    assert "Best match" in rendered_text
    assert "Most starred" in rendered_text
    assert "Public Catalog" in rendered_text
    assert "Browse" in rendered_text
