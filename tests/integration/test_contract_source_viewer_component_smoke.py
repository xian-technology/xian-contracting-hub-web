from __future__ import annotations

import pytest

from contracting_hub.components import contract_source_viewer

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


def test_contract_source_viewer_renders_python_code_actions_and_line_numbers() -> None:
    rendered = contract_source_viewer(
        source_code="@export\ndef seed():\n    return 'escrow'\n",
        source_download_url="data:text/x-python;charset=utf-8,@export%0Adef%20seed%28%29%3A",
        source_download_filename="con_escrow-1.2.0.py",
        version_label="1.2.0",
        line_count_label="2 lines",
        has_source_code=True,
        custom_attrs={"data-testid": "contract-source-viewer"},
    ).render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"contract-source-viewer"' in rendered["props"]
    assert "Contract source" in rendered_text
    assert "Python viewer" in rendered_text
    assert "Python" in rendered_text
    assert "1.2.0" in rendered_text
    assert "2 lines" in rendered_text
    assert "Copy code" in rendered_text
    assert "Download .py" in rendered_text
    assert any('language:"python"' in prop for prop in rendered_props)
    assert any("showLineNumbers:true" in prop for prop in rendered_props)
    assert any("_download" in prop for prop in rendered_props)


def test_contract_source_viewer_renders_empty_state_without_source_code() -> None:
    rendered = contract_source_viewer(
        source_code="",
        source_download_url="",
        source_download_filename="con_escrow.py",
        version_label="",
        line_count_label="0 lines",
        has_source_code=False,
    ).render()
    rendered_text = _rendered_text(rendered)

    assert "Source unavailable" in rendered_text
    assert (
        "The selected public version does not currently expose a source snapshot." in rendered_text
    )
