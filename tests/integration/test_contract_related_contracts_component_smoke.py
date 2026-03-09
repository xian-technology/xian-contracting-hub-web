from __future__ import annotations

import pytest

from contracting_hub.components import contract_related_contracts

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


def test_contract_related_contracts_component_renders_visible_incoming_and_outgoing_links() -> None:
    rendered = contract_related_contracts(
        total_count_label="2 public links",
        outgoing_count_label="1 outgoing link",
        incoming_count_label="1 incoming link",
        outgoing_relations=[
            {
                "relation_label": "Depends on",
                "href": "/contracts/vault",
                "display_name": "Vault",
                "contract_name": "con_vault",
                "short_summary": "Shared treasury settlement helpers.",
                "author_label": "Treasury Team",
                "primary_category_label": "Treasury",
                "latest_version_label": "Latest 0.8.0",
            }
        ],
        incoming_relations=[
            {
                "relation_label": "Example for",
                "href": "/contracts/escrow-example",
                "display_name": "Escrow Example",
                "contract_name": "con_escrow_example",
                "short_summary": "Reference walkthrough for escrow consumers.",
                "author_label": "Bob Example",
                "primary_category_label": "Guides",
                "latest_version_label": "Latest 0.3.0",
            }
        ],
        has_outgoing_relations=True,
        has_incoming_relations=True,
        custom_attrs={"data-testid": "contract-related-contracts"},
    ).render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"contract-related-contracts"' in rendered["props"]
    assert "Relation map" in rendered_text
    assert "Outgoing links" in rendered_text
    assert "Incoming links" in rendered_text
    assert "2 public links" in rendered_text
    assert "1 outgoing link" in rendered_text
    assert "1 incoming link" in rendered_text
    assert any("data-testid" in prop for prop in rendered_props)
