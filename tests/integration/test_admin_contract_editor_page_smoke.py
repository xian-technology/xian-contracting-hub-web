from __future__ import annotations

from contracting_hub.admin.contract_editor import edit_contract, new_contract


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


def test_admin_contract_editor_placeholders_render_stable_scaffolding() -> None:
    new_rendered = new_contract().render()
    edit_rendered = edit_contract().render()
    new_text = _rendered_text(new_rendered)
    edit_text = _rendered_text(edit_rendered)
    new_props = _collect_props(new_rendered)
    edit_props = _collect_props(edit_rendered)

    assert '"data-testid":"app-shell"' in new_rendered["props"]
    assert '"data-testid":"app-shell"' in edit_rendered["props"]
    assert any('"data-testid":"admin-contract-editor-page"' in prop for prop in new_props)
    assert any('"data-testid":"admin-contract-editor-page"' in prop for prop in edit_props)
    assert any('"data-testid":"admin-contract-editor-loading"' in prop for prop in new_props)
    assert any('"data-testid":"admin-contract-editor-loading"' in prop for prop in edit_props)
    assert "Loading contract editor" in new_text
    assert "Loading contract editor" in edit_text
