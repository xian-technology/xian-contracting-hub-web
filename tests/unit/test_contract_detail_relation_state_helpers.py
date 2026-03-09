from __future__ import annotations

from contracting_hub.models import ContractRelationType
from contracting_hub.services.contract_detail import ContractDetailRelatedContractSummary
from contracting_hub.states.contract_detail import (
    _format_related_contract_count_label,
    _format_relation_group_count_label,
    _serialize_related_contracts,
)


def test_serialize_related_contracts_builds_public_detail_links_and_labels() -> None:
    payload = _serialize_related_contracts(
        [
            ContractDetailRelatedContractSummary(
                slug="vault",
                display_name="Vault",
                contract_name="con_vault",
                short_summary="Shared treasury settlement helpers.",
                relation_type=ContractRelationType.DEPENDS_ON,
                relation_label="Depends on",
                author_name="Treasury Team",
                primary_category_name="Treasury",
                latest_version_label="Latest 0.8.0",
            )
        ]
    )

    assert payload == [
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
    ]


def test_related_contract_count_labels_handle_pluralization() -> None:
    assert _format_related_contract_count_label(1) == "1 public link"
    assert _format_related_contract_count_label(3) == "3 public links"
    assert _format_relation_group_count_label(1, direction="incoming") == "1 incoming link"
    assert _format_relation_group_count_label(2, direction="outgoing") == "2 outgoing links"
