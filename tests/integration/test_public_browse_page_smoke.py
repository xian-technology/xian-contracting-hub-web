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
        false_value = current.get("false_value")
        true_value = current.get("true_value")
        if false_value is not None:
            stack.append(false_value)
        if true_value is not None:
            stack.append(true_value)

    return text_fragments


def _collect_props(node: dict[str, object]) -> list[str]:
    props_values: list[str] = []
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue

        props = current.get("props")
        if isinstance(props, list):
            props_values.extend(str(prop) for prop in props)

        stack.extend(reversed(current.get("children", [])))
        false_value = current.get("false_value")
        true_value = current.get("true_value")
        if false_value is not None:
            stack.append(false_value)
        if true_value is not None:
            stack.append(true_value)

    return props_values


def test_app_registers_the_public_browse_route(app_module: dict[str, object]) -> None:
    assert BROWSE_ROUTE.lstrip("/") in app_module["app"]._unevaluated_pages


def test_browse_page_renders_filters_sort_controls_and_public_shell() -> None:
    rendered = index().render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"app-shell"' in rendered["props"]
    assert any('"data-testid":"browse-filters"' in prop for prop in rendered_props)
    assert any('"data-testid":"browse-results-loading"' in prop for prop in rendered_props)
    assert any('htmlFor:"browse-query"' in prop for prop in rendered_props)
    assert any('id:"browse-query"' in prop for prop in rendered_props)
    assert any('id:"browse-category"' in prop for prop in rendered_props)
    assert any('id:"browse-tag"' in prop for prop in rendered_props)
    assert any('id:"browse-sort"' in prop for prop in rendered_props)
    assert "Browse Contracts" in rendered_text
    assert "Browse Controls" in rendered_text
    assert "Apply filters" in rendered_text
    assert "Loading catalog results" in rendered_text
    assert "Browse" in rendered_text
