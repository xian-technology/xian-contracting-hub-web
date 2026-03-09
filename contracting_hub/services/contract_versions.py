"""Service helpers for immutable contract version storage."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from contracting_hub.models import ContractVersion, PublicationStatus, utc_now
from contracting_hub.repositories import ContractVersionRepository
from contracting_hub.services.contract_metadata import (
    validate_publication_status,
    validate_semantic_version,
)

PUBLIC_VERSION_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)


class ContractVersionServiceErrorCode(StrEnum):
    """Stable version-storage failures exposed to callers."""

    CONTRACT_NOT_FOUND = "contract_not_found"
    DUPLICATE_VERSION = "duplicate_version"
    INVALID_CHANGELOG = "invalid_changelog"
    INVALID_SOURCE_CODE = "invalid_source_code"
    PREVIOUS_VERSION_NOT_FOUND = "previous_version_not_found"


class ContractVersionServiceError(ValueError):
    """Structured service error for immutable version storage workflows."""

    def __init__(
        self,
        code: ContractVersionServiceErrorCode,
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
        """Serialize the service failure for UI or API responses."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


def create_contract_version(
    *,
    session: Session,
    contract_slug: str,
    semantic_version: str,
    source_code: str,
    changelog: str | None = None,
    status: PublicationStatus | str = PublicationStatus.DRAFT,
    published_at: datetime | None = None,
    previous_version_semantic_version: str | None = None,
) -> ContractVersion:
    """Create a new append-only contract version row for the target contract."""
    repository = ContractVersionRepository(session)
    contract = repository.get_contract_by_slug(contract_slug)
    if contract is None:
        raise ContractVersionServiceError(
            ContractVersionServiceErrorCode.CONTRACT_NOT_FOUND,
            f"Contract {contract_slug!r} does not exist.",
            field="contract_slug",
            details={"contract_slug": contract_slug},
        )

    normalized_version = validate_semantic_version(semantic_version)
    normalized_status = validate_publication_status(status)
    snapshot = validate_contract_source_code(source_code)
    normalized_changelog = normalize_version_changelog(changelog)

    if repository.get_contract_version(contract.id, normalized_version) is not None:
        raise ContractVersionServiceError(
            ContractVersionServiceErrorCode.DUPLICATE_VERSION,
            (f"Contract {contract.slug!r} already has a version {normalized_version!r}."),
            field="semantic_version",
            details={
                "contract_slug": contract.slug,
                "semantic_version": normalized_version,
            },
        )

    previous_version = _resolve_previous_version(
        repository,
        contract_id=contract.id,
        previous_version_semantic_version=previous_version_semantic_version,
    )
    version = ContractVersion(
        contract_id=contract.id,
        semantic_version=normalized_version,
        status=normalized_status,
        source_code=snapshot,
        source_hash_sha256=build_source_hash(snapshot),
        changelog=normalized_changelog,
        previous_version_id=previous_version.id if previous_version is not None else None,
        published_at=_resolve_published_at(
            status=normalized_status,
            published_at=published_at,
        ),
    )

    try:
        repository.add_contract_version(version)
        if normalized_status in PUBLIC_VERSION_STATUSES:
            contract.latest_published_version = version
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _looks_like_duplicate_version_violation(error):
            raise ContractVersionServiceError(
                ContractVersionServiceErrorCode.DUPLICATE_VERSION,
                (f"Contract {contract.slug!r} already has a version {normalized_version!r}."),
                field="semantic_version",
                details={
                    "contract_slug": contract.slug,
                    "semantic_version": normalized_version,
                },
            ) from error
        raise

    session.refresh(version)
    return version


def validate_contract_source_code(source_code: str) -> str:
    """Validate that a stored source snapshot is a non-empty string."""
    if not isinstance(source_code, str):
        raise ContractVersionServiceError(
            ContractVersionServiceErrorCode.INVALID_SOURCE_CODE,
            "Source code must be a string.",
            field="source_code",
            details={"expected_type": "str"},
        )
    if source_code.strip():
        return source_code

    raise ContractVersionServiceError(
        ContractVersionServiceErrorCode.INVALID_SOURCE_CODE,
        "Source code is required.",
        field="source_code",
    )


def normalize_version_changelog(changelog: str | None) -> str | None:
    """Trim changelog input while keeping empty values nullable."""
    if changelog is None:
        return None
    if not isinstance(changelog, str):
        raise ContractVersionServiceError(
            ContractVersionServiceErrorCode.INVALID_CHANGELOG,
            "Changelog must be a string.",
            field="changelog",
            details={"expected_type": "str"},
        )

    normalized = changelog.strip()
    return normalized or None


def build_source_hash(source_code: str) -> str:
    """Return the persisted SHA-256 digest for a source snapshot."""
    return hashlib.sha256(source_code.encode("utf-8")).hexdigest()


def _resolve_previous_version(
    repository: ContractVersionRepository,
    *,
    contract_id: int,
    previous_version_semantic_version: str | None,
) -> ContractVersion | None:
    if previous_version_semantic_version is None:
        return repository.get_latest_contract_version(contract_id)

    normalized_previous_version = validate_semantic_version(previous_version_semantic_version)
    previous_version = repository.get_contract_version(contract_id, normalized_previous_version)
    if previous_version is not None:
        return previous_version

    raise ContractVersionServiceError(
        ContractVersionServiceErrorCode.PREVIOUS_VERSION_NOT_FOUND,
        f"Previous version {normalized_previous_version!r} does not exist for this contract.",
        field="previous_version_semantic_version",
        details={
            "contract_id": contract_id,
            "semantic_version": normalized_previous_version,
        },
    )


def _resolve_published_at(
    *,
    status: PublicationStatus,
    published_at: datetime | None,
) -> datetime | None:
    if status in PUBLIC_VERSION_STATUSES:
        return published_at or utc_now()
    return None


def _looks_like_duplicate_version_violation(error: IntegrityError) -> bool:
    error_message = str(error.orig).lower()
    return "contract_versions.contract_id, contract_versions.semantic_version" in error_message


__all__ = [
    "PUBLIC_VERSION_STATUSES",
    "ContractVersionServiceError",
    "ContractVersionServiceErrorCode",
    "build_source_hash",
    "create_contract_version",
    "normalize_version_changelog",
    "validate_contract_source_code",
]
