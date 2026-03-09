from __future__ import annotations

import pytest

from contracting_hub.components import contract_version_diff_viewer

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


def test_contract_version_diff_viewer_renders_unified_diff_metrics_and_code_block() -> None:
    rendered = contract_version_diff_viewer(
        selected_version="1.2.0",
        previous_version="1.1.0",
        has_previous_version=True,
        has_diff_content=True,
        added_lines_label="+2 lines added",
        removed_lines_label="-1 line removed",
        line_delta_label="+1 line net",
        hunk_count_label="1 hunk",
        context_lines_label="3 context lines",
        unified_diff=(
            "--- v1.1.0\n"
            "+++ v1.2.0\n"
            "@@ -1,2 +1,3 @@\n"
            " def seed():\n"
            "-    return 'legacy'\n"
            "+    value = 'current'\n"
            "+    return value\n"
        ),
        custom_attrs={"data-testid": "contract-version-diff-viewer"},
    ).render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"contract-version-diff-viewer"' in rendered["props"]
    assert "Version diff" in rendered_text
    assert "Change viewer" in rendered_text
    assert "Previous visible release" in rendered_text
    assert "Current selection" in rendered_text
    assert "1.1.0" in rendered_text
    assert "1.2.0" in rendered_text
    assert "+2 lines added" in rendered_text
    assert "-1 line removed" in rendered_text
    assert "Unified diff" in rendered_text
    assert any('language:"diff"' in prop for prop in rendered_props)
    assert any("showLineNumbers:true" in prop for prop in rendered_props)


def test_contract_version_diff_viewer_renders_initial_release_empty_state() -> None:
    rendered = contract_version_diff_viewer(
        selected_version="1.0.0",
        previous_version="",
        has_previous_version=False,
        has_diff_content=False,
        added_lines_label="+0 lines added",
        removed_lines_label="-0 lines removed",
        line_delta_label="No line delta",
        hunk_count_label="0 hunks",
        context_lines_label="3 context lines",
        unified_diff="",
    ).render()
    rendered_text = _rendered_text(rendered)

    assert "Initial public release" in rendered_text
    assert "is the first visible release for this contract" in " ".join(rendered_text)
