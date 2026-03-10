from __future__ import annotations

from contracting_hub.admin.catalog_operations import index as admin_catalog_operations_page
from contracting_hub.utils.meta import ADMIN_OPERATIONS_ROUTE


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


def test_app_registers_admin_catalog_operations_route(app_module: dict[str, object]) -> None:
    assert ADMIN_OPERATIONS_ROUTE.lstrip("/") in app_module["app"]._unevaluated_pages


def test_admin_catalog_operations_page_renders_workspace_sections() -> None:
    rendered = admin_catalog_operations_page().render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"app-shell"' in rendered["props"]
    assert any('"data-testid":"admin-catalog-page"' in prop for prop in rendered_props)
    assert any('"data-testid":"admin-catalog-loading"' in prop for prop in rendered_props)
    assert "Admin catalog operations" in rendered_text
    assert "Loading catalog operations" in rendered_text
