from __future__ import annotations

import pytest
import reflex as rx

from contracting_hub.components import (
    ContractCardMetric,
    contract_detail_header,
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


def test_contract_detail_header_renders_author_categories_metrics_and_actions() -> None:
    rendered = contract_detail_header(
        badges=rx.flex(
            contract_metadata_badge("DeFi", tone="category"),
            contract_metadata_badge("Featured", tone="featured"),
            wrap="wrap",
            gap="0.5rem",
        ),
        context_label="Version 1.2.0 • Published Feb 5, 2026 • Updated Feb 6, 2026",
        display_name="Escrow",
        contract_name="con_escrow",
        short_summary="Curated escrow primitives for treasury flows.",
        long_description="Protects staged claims, refunds, and settlement windows.",
        taxonomy=rx.vstack(
            rx.text("Categories"),
            rx.flex(contract_metadata_badge("DeFi", tone="category"), gap="0.5rem"),
            rx.text("Tags"),
            rx.flex(contract_metadata_badge("escrow"), contract_metadata_badge("treasury")),
            align="start",
        ),
        metrics=(
            ContractCardMetric("Version", "1.2.0"),
            ContractCardMetric("Updated", "Feb 6, 2026"),
            ContractCardMetric("Stars", "31"),
            ContractCardMetric(
                "Rating",
                contract_rating_summary(
                    headline="4.5 avg",
                    detail="2 ratings",
                    empty=False,
                ),
            ),
        ),
        author_panel=rx.box(
            rx.vstack(
                rx.text("Author"),
                rx.text("Alice Builder"),
                rx.text("@alice"),
                rx.text("Builds escrow flows for treasury teams."),
                rx.link("GitHub", href="https://github.com/alice"),
                align="start",
            )
        ),
        actions=rx.flex(
            rx.button("Browse catalog"),
            rx.button("Documentation"),
            rx.button("Source repo"),
            wrap="wrap",
            gap="0.5rem",
        ),
        custom_attrs={"data-testid": "contract-detail-header"},
    ).render()
    rendered_text = _rendered_text(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"contract-detail-header"' in rendered["props"]
    assert "Escrow" in rendered_text
    assert "con_escrow" in rendered_text
    assert "Alice Builder" in rendered_text
    assert "@alice" in rendered_text
    assert "Categories" in rendered_text
    assert "DeFi" in rendered_text
    assert "escrow" in rendered_text
    assert "4.5 avg" in rendered_text
    assert "2 ratings" in rendered_text
    assert "Browse catalog" in rendered_text
    assert "Documentation" in rendered_text
    assert "Source repo" in rendered_text
