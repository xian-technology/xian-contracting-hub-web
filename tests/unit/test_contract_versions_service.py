import pytest

from contracting_hub.services import (
    ContractVersionServiceError,
    ContractVersionServiceErrorCode,
    build_source_hash,
    normalize_version_changelog,
    validate_contract_source_code,
)


def test_validate_contract_source_code_preserves_snapshot_content() -> None:
    snapshot = "\n# generated\nvalue = 1  \n"

    assert validate_contract_source_code(snapshot) == snapshot


@pytest.mark.parametrize("invalid_source", ["", "   \n\t  "])
def test_validate_contract_source_code_rejects_blank_snapshots(invalid_source: str) -> None:
    with pytest.raises(ContractVersionServiceError) as error:
        validate_contract_source_code(invalid_source)

    assert error.value.code is ContractVersionServiceErrorCode.INVALID_SOURCE_CODE
    assert error.value.field == "source_code"


def test_normalize_version_changelog_trims_or_drops_empty_values() -> None:
    assert normalize_version_changelog("  Added timeout handling.  ") == "Added timeout handling."
    assert normalize_version_changelog("   ") is None
    assert normalize_version_changelog(None) is None


def test_normalize_version_changelog_rejects_non_string_inputs() -> None:
    with pytest.raises(ContractVersionServiceError) as error:
        normalize_version_changelog(42)  # type: ignore[arg-type]

    assert error.value.code is ContractVersionServiceErrorCode.INVALID_CHANGELOG
    assert error.value.details["expected_type"] == "str"


def test_build_source_hash_returns_stable_sha256_digest() -> None:
    assert build_source_hash("def seed():\n    return 'ok'\n") == (
        "fb2bae4fd7890771563bbf06e6f01983b9396305673a8995fffc1774652edd55"
    )
