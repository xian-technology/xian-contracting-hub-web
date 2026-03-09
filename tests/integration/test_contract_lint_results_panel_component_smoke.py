from __future__ import annotations

import pytest

from contracting_hub.components import contract_lint_results_panel

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


def test_contract_lint_results_panel_renders_summary_and_detailed_findings() -> None:
    rendered = contract_lint_results_panel(
        selected_version="1.2.0",
        has_lint_report=True,
        lint_status_label="Warn",
        lint_status_color_scheme="orange",
        lint_summary_copy="Non-blocking lint warnings were detected for this public release.",
        issue_count_label="2 issues",
        error_count_label="0 errors",
        warning_count_label="1 warning",
        info_count_label="1 info note",
        findings=[
            {
                "severity_label": "Warning",
                "severity_color_scheme": "orange",
                "message": "Prefer explicit timeout docs for claim paths.",
                "location_label": "Line 12, Column 4",
            },
            {
                "severity_label": "Info",
                "severity_color_scheme": "gray",
                "message": "Generated metadata was normalized for display.",
                "location_label": "General finding",
            },
        ],
        has_findings=True,
        custom_attrs={"data-testid": "contract-lint-results-panel"},
    ).render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)
    rendered_repr = repr(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"contract-lint-results-panel"' in rendered["props"]
    assert "Lint results" in rendered_text
    assert "Quality checks" in rendered_text
    assert "1.2.0" in rendered_text
    assert "Warn" in rendered_text
    assert "2 issues" in rendered_text
    assert "1 warning" in rendered_text
    assert "Detailed findings" in rendered_text
    assert "Prefer explicit timeout docs for claim paths." in rendered_repr
    assert "Line 12, Column 4" in rendered_repr
    assert any("data-testid" in prop for prop in rendered_props)


def test_contract_lint_results_panel_renders_unavailable_state_without_report() -> None:
    rendered = contract_lint_results_panel(
        selected_version="1.0.0",
        has_lint_report=False,
        lint_status_label="Unavailable",
        lint_status_color_scheme="gray",
        lint_summary_copy="Lint metadata is unavailable for this public release.",
        issue_count_label="0 issues",
        error_count_label="0 errors",
        warning_count_label="0 warnings",
        info_count_label="0 info notes",
        findings=[],
        has_findings=False,
    ).render()
    rendered_text = _rendered_text(rendered)

    assert "Lint report unavailable" in rendered_text
    assert "does not currently expose stored lint metadata" in " ".join(rendered_text)
