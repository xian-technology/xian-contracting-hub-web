from contracting_hub.models import ContractRelationType
from contracting_hub.services.admin_contract_relations import (
    MAX_RELATION_NOTE_LENGTH,
    build_empty_admin_contract_relation_manager_snapshot,
    format_admin_contract_relation_type_label,
    normalize_admin_contract_relation_note,
)


def test_build_empty_admin_contract_relation_manager_snapshot_uses_requested_slug() -> None:
    snapshot = build_empty_admin_contract_relation_manager_snapshot(contract_slug="Escrow")

    assert snapshot.slug == "escrow"
    assert snapshot.edit_href == "/admin/contracts/escrow/edit"
    assert snapshot.versions_href == "/admin/contracts/escrow/versions"
    assert snapshot.outgoing_relations == ()
    assert snapshot.incoming_relations == ()
    assert snapshot.target_options == ()


def test_normalize_admin_contract_relation_note_trims_blank_values() -> None:
    assert normalize_admin_contract_relation_note("  needs  review  ") == "needs review"
    assert normalize_admin_contract_relation_note("   ") is None
    assert normalize_admin_contract_relation_note(None) is None


def test_normalize_admin_contract_relation_note_rejects_overlong_values() -> None:
    try:
        normalize_admin_contract_relation_note("x" * (MAX_RELATION_NOTE_LENGTH + 1))
    except ValueError as error:
        assert "255 characters or fewer" in str(error)
    else:
        raise AssertionError("Expected an overlong note to fail validation")


def test_format_admin_contract_relation_type_label_returns_expected_copy() -> None:
    assert (
        format_admin_contract_relation_type_label(ContractRelationType.DEPENDS_ON) == "Depends on"
    )
    assert (
        format_admin_contract_relation_type_label(ContractRelationType.EXAMPLE_FOR) == "Example for"
    )
