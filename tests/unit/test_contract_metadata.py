import pytest

from contracting_hub.models import ContractRelationType, PublicationStatus
from contracting_hub.services import (
    MAX_CONTRACT_NAME_LENGTH,
    MAX_CONTRACT_SLUG_LENGTH,
    MAX_SEMANTIC_VERSION_LENGTH,
    ContractMetadataValidationError,
    ContractMetadataValidationErrorCode,
    validate_contract_name,
    validate_contract_slug,
    validate_publication_status,
    validate_relation_type,
    validate_semantic_version,
)


@pytest.mark.parametrize(
    ("raw_name", "expected_name"),
    [
        ("con_escrow", "con_escrow"),
        ("  con_token_v2  ", "con_token_v2"),
    ],
)
def test_validate_contract_name_accepts_xian_style_names(
    raw_name: str,
    expected_name: str,
) -> None:
    assert validate_contract_name(raw_name) == expected_name


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "escrow",
        "con-Escrow",
        "con_Upper",
        f"con_{'a' * MAX_CONTRACT_NAME_LENGTH}",
    ],
)
def test_validate_contract_name_rejects_invalid_values(invalid_name: str) -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_contract_name(invalid_name)

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_CONTRACT_NAME
    assert error.value.field == "contract_name"


@pytest.mark.parametrize(
    ("raw_slug", "expected_slug"),
    [
        ("escrow", "escrow"),
        ("  nft-market  ", "nft-market"),
    ],
)
def test_validate_contract_slug_accepts_stable_url_slugs(
    raw_slug: str,
    expected_slug: str,
) -> None:
    assert validate_contract_slug(raw_slug) == expected_slug


@pytest.mark.parametrize(
    "invalid_slug",
    [
        "",
        "Escrow",
        "nft_market",
        "-leading",
        "trailing-",
        "double--dash",
        f"{'a' * (MAX_CONTRACT_SLUG_LENGTH + 1)}",
    ],
)
def test_validate_contract_slug_rejects_invalid_values(invalid_slug: str) -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_contract_slug(invalid_slug)

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_SLUG
    assert error.value.field == "slug"


def test_validate_contract_slug_rejects_non_string_inputs() -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_contract_slug(None)  # type: ignore[arg-type]

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_SLUG
    assert error.value.field == "slug"
    assert error.value.details["expected_type"] == "str"


@pytest.mark.parametrize(
    ("raw_version", "expected_version"),
    [
        ("1.2.0", "1.2.0"),
        ("  2.0.0-rc.1+build.5  ", "2.0.0-rc.1+build.5"),
    ],
)
def test_validate_semantic_version_accepts_semver_strings(
    raw_version: str,
    expected_version: str,
) -> None:
    assert validate_semantic_version(raw_version) == expected_version


@pytest.mark.parametrize(
    "invalid_version",
    [
        "",
        "1.0",
        "1",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "v1.2.3",
        f"1.2.3-{'a' * MAX_SEMANTIC_VERSION_LENGTH}",
    ],
)
def test_validate_semantic_version_rejects_invalid_values(invalid_version: str) -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_semantic_version(invalid_version)

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_SEMANTIC_VERSION
    assert error.value.field == "semantic_version"


def test_validate_semantic_version_rejects_non_string_inputs() -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_semantic_version(None)  # type: ignore[arg-type]

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_SEMANTIC_VERSION
    assert error.value.field == "semantic_version"
    assert error.value.details["expected_type"] == "str"


def test_validate_publication_status_accepts_enums_and_strings() -> None:
    assert validate_publication_status(PublicationStatus.PUBLISHED) is PublicationStatus.PUBLISHED
    assert validate_publication_status("  deprecated  ") is PublicationStatus.DEPRECATED


def test_validate_publication_status_rejects_unknown_values_with_allowed_list() -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_publication_status("retired")

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_PUBLICATION_STATUS
    assert error.value.details["allowed_values"] == [
        "draft",
        "published",
        "archived",
        "deprecated",
    ]


def test_validate_publication_status_rejects_non_string_inputs() -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_publication_status(None)  # type: ignore[arg-type]

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_PUBLICATION_STATUS
    assert error.value.details["expected_type"] == "str"


def test_validate_relation_type_accepts_enums_and_strings() -> None:
    assert validate_relation_type(ContractRelationType.EXTENDS) is ContractRelationType.EXTENDS
    assert validate_relation_type("  depends_on  ") is ContractRelationType.DEPENDS_ON


def test_validate_relation_type_rejects_unknown_values() -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_relation_type("related_to")

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_RELATION_TYPE
    assert error.value.field == "relation_type"


def test_validate_contract_name_rejects_non_string_inputs() -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_contract_name(42)  # type: ignore[arg-type]

    assert error.value.code is ContractMetadataValidationErrorCode.INVALID_CONTRACT_NAME
    assert error.value.details["expected_type"] == "str"


def test_validation_errors_serialize_stable_payloads() -> None:
    with pytest.raises(ContractMetadataValidationError) as error:
        validate_contract_slug("invalid_slug")

    assert error.value.as_payload() == {
        "code": "invalid_slug",
        "field": "slug",
        "message": (
            "Contract slugs must use lowercase letters, numbers, and single hyphen separators."
        ),
        "details": {"pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$"},
    }
