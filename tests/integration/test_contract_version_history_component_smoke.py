from __future__ import annotations

import pytest

from contracting_hub.components import contract_version_history

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


def test_contract_version_history_renders_selector_and_release_notes() -> None:
    rendered = contract_version_history(
        versions=[
            {
                "semantic_version": "1.2.0",
                "href": "/contracts/escrow",
                "status_label": "Published",
                "status_color_scheme": "grass",
                "published_label": "Feb 5, 2026",
                "is_selected": True,
                "is_latest_public": True,
            },
            {
                "semantic_version": "1.1.0",
                "href": "/contracts/escrow?version=1.1.0",
                "status_label": "Deprecated",
                "status_color_scheme": "orange",
                "published_label": "Feb 1, 2026",
                "is_selected": False,
                "is_latest_public": False,
            },
        ],
        version_count_label="2 public versions",
        selected_version="1.2.0",
        selected_version_status_label="Published",
        selected_version_status_color_scheme="grass",
        selected_version_published_label="Feb 5, 2026",
        selected_version_changelog="Add settlement timeouts and clearer validation.",
        has_selected_version_changelog=True,
        selected_version_is_latest_public=True,
        custom_attrs={"data-testid": "contract-version-history"},
    ).render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"contract-version-history"' in rendered["props"]
    assert "Version history" in rendered_text
    assert "Release selector" in rendered_text
    assert "2 public versions" in rendered_text
    assert "1.2.0" in rendered_text
    assert "Latest public" in rendered_text
    assert "Published" in rendered_text
    assert "Release notes" in rendered_text
    assert "Add settlement timeouts and clearer validation." in rendered_text
    assert any("data-testid" in prop for prop in rendered_props)


def test_contract_version_history_renders_empty_changelog_state() -> None:
    rendered = contract_version_history(
        versions=[
            {
                "semantic_version": "1.0.0",
                "href": "/contracts/escrow",
                "status_label": "Published",
                "status_color_scheme": "grass",
                "published_label": "Feb 5, 2026",
                "is_selected": True,
                "is_latest_public": True,
            }
        ],
        version_count_label="1 public version",
        selected_version="1.0.0",
        selected_version_status_label="Published",
        selected_version_status_color_scheme="grass",
        selected_version_published_label="Feb 5, 2026",
        selected_version_changelog="",
        has_selected_version_changelog=False,
        selected_version_is_latest_public=True,
    ).render()
    rendered_text = _rendered_text(rendered)

    assert "No changelog published" in rendered_text
    assert "This public release does not yet include release notes." in " ".join(rendered_text)
