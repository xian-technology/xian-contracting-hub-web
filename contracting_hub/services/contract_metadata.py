"""Validation helpers for contract metadata managed by the catalog."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TypeVar

from contracting_hub.models import ContractRelationType, PublicationStatus

MAX_CONTRACT_NAME_LENGTH = 64
MAX_CONTRACT_SLUG_LENGTH = 128
MAX_SEMANTIC_VERSION_LENGTH = 32

CONTRACT_NAME_PATTERN = re.compile(r"^con_[a-z0-9_]+$")
CONTRACT_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-"
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*"
    r")?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class ContractMetadataValidationErrorCode(StrEnum):
    """Stable metadata validation failures exposed to services and UI code."""

    INVALID_CONTRACT_NAME = "invalid_contract_name"
    INVALID_SLUG = "invalid_slug"
    INVALID_SEMANTIC_VERSION = "invalid_semantic_version"
    INVALID_PUBLICATION_STATUS = "invalid_publication_status"
    INVALID_RELATION_TYPE = "invalid_relation_type"


class ContractMetadataValidationError(ValueError):
    """Structured metadata validation error."""

    def __init__(
        self,
        code: ContractMetadataValidationErrorCode,
        message: str,
        *,
        field: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.details = details or {}

    def as_payload(self) -> dict[str, object]:
        """Serialize the validation failure for UI or API responses."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


def validate_contract_name(contract_name: str) -> str:
    """Validate a Xian contract name and return the normalized value."""
    normalized_name = _normalize_text(
        contract_name,
        field="contract_name",
        code=ContractMetadataValidationErrorCode.INVALID_CONTRACT_NAME,
    )
    if len(normalized_name) > MAX_CONTRACT_NAME_LENGTH:
        raise ContractMetadataValidationError(
            ContractMetadataValidationErrorCode.INVALID_CONTRACT_NAME,
            "Contract names must be 64 characters or fewer.",
            field="contract_name",
            details={"max_length": MAX_CONTRACT_NAME_LENGTH},
        )
    if CONTRACT_NAME_PATTERN.fullmatch(normalized_name):
        return normalized_name

    raise ContractMetadataValidationError(
        ContractMetadataValidationErrorCode.INVALID_CONTRACT_NAME,
        "Contract names must start with 'con_' and use lowercase letters, numbers, or underscores.",
        field="contract_name",
        details={"pattern": CONTRACT_NAME_PATTERN.pattern},
    )


def validate_contract_slug(slug: str) -> str:
    """Validate a stable catalog slug and return the normalized value."""
    normalized_slug = _normalize_text(
        slug,
        field="slug",
        code=ContractMetadataValidationErrorCode.INVALID_SLUG,
    )
    if len(normalized_slug) > MAX_CONTRACT_SLUG_LENGTH:
        raise ContractMetadataValidationError(
            ContractMetadataValidationErrorCode.INVALID_SLUG,
            "Contract slugs must be 128 characters or fewer.",
            field="slug",
            details={"max_length": MAX_CONTRACT_SLUG_LENGTH},
        )
    if CONTRACT_SLUG_PATTERN.fullmatch(normalized_slug):
        return normalized_slug

    raise ContractMetadataValidationError(
        ContractMetadataValidationErrorCode.INVALID_SLUG,
        "Contract slugs must use lowercase letters, numbers, and single hyphen separators.",
        field="slug",
        details={"pattern": CONTRACT_SLUG_PATTERN.pattern},
    )


def validate_semantic_version(semantic_version: str) -> str:
    """Validate a semantic version string and return the normalized value."""
    normalized_version = _normalize_text(
        semantic_version,
        field="semantic_version",
        code=ContractMetadataValidationErrorCode.INVALID_SEMANTIC_VERSION,
    )
    if len(normalized_version) > MAX_SEMANTIC_VERSION_LENGTH:
        raise ContractMetadataValidationError(
            ContractMetadataValidationErrorCode.INVALID_SEMANTIC_VERSION,
            "Semantic versions must be 32 characters or fewer.",
            field="semantic_version",
            details={"max_length": MAX_SEMANTIC_VERSION_LENGTH},
        )
    if SEMANTIC_VERSION_PATTERN.fullmatch(normalized_version):
        return normalized_version

    raise ContractMetadataValidationError(
        ContractMetadataValidationErrorCode.INVALID_SEMANTIC_VERSION,
        "Semantic versions must follow semantic versioning, for example '1.2.0' or '1.2.0-rc.1'.",
        field="semantic_version",
        details={"pattern": SEMANTIC_VERSION_PATTERN.pattern},
    )


def validate_publication_status(status: PublicationStatus | str) -> PublicationStatus:
    """Validate and normalize a persisted publication status value."""
    return _coerce_enum(
        status,
        enum_type=PublicationStatus,
        field="status",
        code=ContractMetadataValidationErrorCode.INVALID_PUBLICATION_STATUS,
    )


def validate_relation_type(relation_type: ContractRelationType | str) -> ContractRelationType:
    """Validate and normalize a typed contract relation value."""
    return _coerce_enum(
        relation_type,
        enum_type=ContractRelationType,
        field="relation_type",
        code=ContractMetadataValidationErrorCode.INVALID_RELATION_TYPE,
    )


_EnumValue = TypeVar("_EnumValue", ContractRelationType, PublicationStatus)


def _normalize_text(
    value: str,
    *,
    field: str,
    code: ContractMetadataValidationErrorCode,
) -> str:
    if not isinstance(value, str):
        raise ContractMetadataValidationError(
            code,
            f"{field.replace('_', ' ').capitalize()} must be a string.",
            field=field,
            details={"expected_type": "str"},
        )

    normalized = value.strip()
    if normalized:
        return normalized

    raise ContractMetadataValidationError(
        code,
        f"{field.replace('_', ' ').capitalize()} is required.",
        field=field,
    )


def _coerce_enum(
    value: _EnumValue | str,
    *,
    enum_type: type[_EnumValue],
    field: str,
    code: ContractMetadataValidationErrorCode,
) -> _EnumValue:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise ContractMetadataValidationError(
            code,
            f"{field.replace('_', ' ').capitalize()} must be a string.",
            field=field,
            details={
                "allowed_values": [member.value for member in enum_type],
                "expected_type": "str",
            },
        )

    normalized = value.strip().lower()
    try:
        return enum_type(normalized)
    except ValueError as error:
        raise ContractMetadataValidationError(
            code,
            f"Unsupported {field.replace('_', ' ')}.",
            field=field,
            details={"allowed_values": [member.value for member in enum_type]},
        ) from error


__all__ = [
    "CONTRACT_NAME_PATTERN",
    "CONTRACT_SLUG_PATTERN",
    "MAX_CONTRACT_NAME_LENGTH",
    "MAX_CONTRACT_SLUG_LENGTH",
    "MAX_SEMANTIC_VERSION_LENGTH",
    "SEMANTIC_VERSION_PATTERN",
    "ContractMetadataValidationError",
    "ContractMetadataValidationErrorCode",
    "validate_contract_name",
    "validate_contract_slug",
    "validate_publication_status",
    "validate_relation_type",
    "validate_semantic_version",
]
