from __future__ import annotations

import pytest
import reflex as rx

from contracting_hub.components import (
    ContractCardMetric,
    contract_card,
    contract_metadata_badge,
    contract_rating_summary,
)

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


def test_contract_catalog_components_render_shared_card_metadata_and_rating() -> None:
    rendered = contract_card(
        badges=rx.flex(
            contract_metadata_badge("DeFi", tone="category"),
            contract_metadata_badge("Published", tone="success"),
            contract_metadata_badge("Featured", tone="featured"),
            wrap="wrap",
            gap="0.5rem",
        ),
        context_label="Updated Mar 9, 2026",
        display_name="Escrow Vault",
        contract_name="con_escrow_vault",
        short_summary="Escrow and settlement primitives for Xian treasury flows.",
        metrics=(
            ContractCardMetric("Version", "1.2.0"),
            ContractCardMetric(
                "Rating",
                contract_rating_summary(
                    headline="4.8 avg",
                    detail="12 ratings",
                    empty=False,
                ),
            ),
            ContractCardMetric("Stars", "41"),
        ),
        author_name="Avery",
        tags=rx.flex(
            contract_metadata_badge("escrow"),
            contract_metadata_badge("treasury"),
            wrap="wrap",
            gap="0.5rem",
        ),
        metric_columns="3",
        custom_attrs={"data-testid": "contract-card"},
    ).render()
    rendered_text = _rendered_text(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"contract-card"' in rendered["props"]
    assert "DeFi" in rendered_text
    assert "Published" in rendered_text
    assert "Featured" in rendered_text
    assert "Escrow Vault" in rendered_text
    assert "con_escrow_vault" in rendered_text
    assert "4.8 avg" in rendered_text
    assert "12 ratings" in rendered_text
    assert "Avery" in rendered_text
