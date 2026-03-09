"""Admin helpers for immutable contract-version management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.database import session_scope
from contracting_hub.models import (
    AdminAuditLog,
    Contract,
    ContractVersion,
    LintStatus,
    PublicationStatus,
)
from contracting_hub.repositories import ContractVersionRepository
from contracting_hub.services.auth import require_admin_user
from contracting_hub.services.contract_diffs import build_contract_version_diff
from contracting_hub.services.contract_linting import (
    ContractLintServiceError,
    ContractLintServiceErrorCode,
    lint_contract_source_code,
)
from contracting_hub.services.contract_metadata import validate_semantic_version
from contracting_hub.services.contract_search import rebuild_contract_search_document
from contracting_hub.services.contract_versions import (
    PUBLIC_VERSION_STATUSES,
    ContractVersionServiceError,
    create_contract_version,
    normalize_version_changelog,
    validate_contract_source_code,
)
from contracting_hub.utils.meta import (
    build_admin_contract_edit_path,
    build_contract_detail_path,
)


class AdminContractVersionManagerServiceErrorCode(StrEnum):
    """Stable admin version-manager failures exposed to callers."""

    CONTRACT_NOT_FOUND = "contract_not_found"
    DUPLICATE_VERSION = "duplicate_version"
    INVALID_CHANGELOG = "invalid_changelog"
    INVALID_SEMANTIC_VERSION = "invalid_semantic_version"
    INVALID_SOURCE_CODE = "invalid_source_code"
    LINT_EXECUTION_FAILED = "lint_execution_failed"


class AdminContractVersionManagerServiceError(ValueError):
    """Structured service error for admin version-manager workflows."""

    def __init__(
        self,
        code: AdminContractVersionManagerServiceErrorCode,
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


@dataclass(frozen=True)
class AdminContractVersionHistoryEntry:
    """One persisted version row rendered in the admin manager."""

    semantic_version: str
    status: PublicationStatus
    previous_version: str | None
    lint_status: LintStatus | None
    created_at: object
    published_at: object
    is_latest_published: bool
    public_detail_href: str | None


@dataclass(frozen=True)
class AdminContractVersionLintFinding:
    """One lint issue exposed in preview mode."""

    severity: str
    line: int | None
    column: int | None
    message: str


@dataclass(frozen=True)
class AdminContractVersionPreview:
    """Lint and diff preview generated before persisting a version."""

    semantic_version: str
    changelog: str | None
    previous_version: str | None
    has_lint_report: bool
    lint_status: LintStatus | None
    lint_summary: dict[str, object] | None
    lint_findings: tuple[AdminContractVersionLintFinding, ...]
    lint_unavailable_message: str | None
    diff_summary: dict[str, object]
    unified_diff: str | None
    can_publish: bool


@dataclass(frozen=True)
class AdminContractVersionManagerSnapshot:
    """Loaded admin version-manager data for one contract."""

    contract_id: int | None
    slug: str
    display_name: str
    contract_name: str
    contract_status: PublicationStatus
    latest_public_version: str | None
    latest_saved_version: str | None
    public_detail_href: str | None
    edit_href: str
    version_history: tuple[AdminContractVersionHistoryEntry, ...]


def build_empty_admin_contract_version_manager_snapshot(
    *,
    contract_slug: str | None = None,
) -> AdminContractVersionManagerSnapshot:
    """Return a stable empty version-manager snapshot."""
    normalized_slug = str(contract_slug or "").strip().lower()
    return AdminContractVersionManagerSnapshot(
        contract_id=None,
        slug=normalized_slug,
        display_name="",
        contract_name="",
        contract_status=PublicationStatus.DRAFT,
        latest_public_version=None,
        latest_saved_version=None,
        public_detail_href=None,
        edit_href=build_admin_contract_edit_path(normalized_slug),
        version_history=(),
    )


def load_admin_contract_version_manager_snapshot(
    *,
    session: Session,
    contract_slug: str,
) -> AdminContractVersionManagerSnapshot:
    """Load contract version history and editor context for the admin page."""
    contract = _require_contract_for_version_manager(session, contract_slug=contract_slug)
    ordered_versions = _sort_contract_versions(contract.versions)
    latest_public_version = (
        contract.latest_published_version.semantic_version
        if contract.latest_published_version is not None
        else None
    )
    return AdminContractVersionManagerSnapshot(
        contract_id=contract.id,
        slug=contract.slug,
        display_name=contract.display_name,
        contract_name=contract.contract_name,
        contract_status=contract.status,
        latest_public_version=latest_public_version,
        latest_saved_version=ordered_versions[0].semantic_version if ordered_versions else None,
        public_detail_href=(
            build_contract_detail_path(contract.slug)
            if contract.status in PUBLIC_VERSION_STATUSES and latest_public_version is not None
            else None
        ),
        edit_href=build_admin_contract_edit_path(contract.slug),
        version_history=tuple(
            AdminContractVersionHistoryEntry(
                semantic_version=version.semantic_version,
                status=version.status,
                previous_version=(
                    version.previous_version.semantic_version
                    if version.previous_version is not None
                    else None
                ),
                lint_status=version.lint_status,
                created_at=version.created_at,
                published_at=version.published_at,
                is_latest_published=version.id == contract.latest_published_version_id,
                public_detail_href=(
                    build_contract_detail_path(
                        contract.slug,
                        semantic_version=None
                        if version.id == contract.latest_published_version_id
                        else version.semantic_version,
                    )
                    if version.status in PUBLIC_VERSION_STATUSES
                    else None
                ),
            )
            for version in ordered_versions
        ),
    )


def load_admin_contract_version_manager_snapshot_safe(
    *,
    contract_slug: str | None = None,
) -> AdminContractVersionManagerSnapshot:
    """Load the version manager while tolerating a missing or unmigrated database."""
    try:
        with session_scope() as session:
            return load_admin_contract_version_manager_snapshot(
                session=session,
                contract_slug=str(contract_slug or "").strip().lower(),
            )
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_admin_contract_version_manager_snapshot(contract_slug=contract_slug)


def preview_admin_contract_version(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
    semantic_version: str,
    source_code: str,
    changelog: str | None = None,
) -> AdminContractVersionPreview:
    """Build lint and diff previews for a candidate immutable version."""
    require_admin_user(session=session, session_token=session_token)
    repository = ContractVersionRepository(session)
    contract = _require_contract_for_version_manager(session, contract_slug=contract_slug)
    contract_id = _require_persisted_id(contract.id, label="contract")
    normalized_version = _normalize_preview_semantic_version(semantic_version)
    normalized_source = _normalize_preview_source_code(source_code)
    normalized_changelog = _normalize_preview_changelog(changelog)

    if repository.get_contract_version(contract_id, normalized_version) is not None:
        raise AdminContractVersionManagerServiceError(
            AdminContractVersionManagerServiceErrorCode.DUPLICATE_VERSION,
            f"Contract {contract.slug!r} already has a version {normalized_version!r}.",
            field="semantic_version",
            details={
                "contract_slug": contract.slug,
                "semantic_version": normalized_version,
            },
        )

    lint_status: LintStatus | None = None
    lint_summary: dict[str, object] | None = None
    lint_findings: tuple[AdminContractVersionLintFinding, ...] = ()
    lint_unavailable_message: str | None = None
    can_publish = False
    try:
        lint_report = lint_contract_source_code(normalized_source)
    except ContractLintServiceError as error:
        if error.code is not ContractLintServiceErrorCode.LINTER_UNAVAILABLE:
            raise AdminContractVersionManagerServiceError(
                AdminContractVersionManagerServiceErrorCode.LINT_EXECUTION_FAILED,
                "Contract linting could not analyze the provided source.",
                field="source_code",
                details=error.as_payload(),
            ) from error
        lint_unavailable_message = "Contract linting is unavailable in the current environment."
    else:
        lint_status = lint_report.status
        lint_summary = dict(lint_report.summary)
        lint_findings = tuple(
            AdminContractVersionLintFinding(
                severity=finding.severity,
                line=finding.position.line if finding.position is not None else None,
                column=finding.position.column if finding.position is not None else None,
                message=finding.message,
            )
            for finding in lint_report.findings
        )
        can_publish = not lint_report.has_errors

    previous_version = repository.get_latest_contract_version(contract.id)
    generated_diff = build_contract_version_diff(
        previous_source_code=previous_version.source_code if previous_version is not None else None,
        current_source_code=normalized_source,
        from_version=previous_version.semantic_version if previous_version is not None else None,
        to_version=normalized_version,
    )
    return AdminContractVersionPreview(
        semantic_version=normalized_version,
        changelog=normalized_changelog,
        previous_version=(
            previous_version.semantic_version if previous_version is not None else None
        ),
        has_lint_report=lint_summary is not None,
        lint_status=lint_status,
        lint_summary=lint_summary,
        lint_findings=lint_findings,
        lint_unavailable_message=lint_unavailable_message,
        diff_summary=generated_diff.summary,
        unified_diff=generated_diff.unified_diff,
        can_publish=can_publish,
    )


def create_admin_contract_version(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
    semantic_version: str,
    source_code: str,
    changelog: str | None = None,
    publish_now: bool = False,
) -> ContractVersion:
    """Create a draft or published immutable version from the admin workspace."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    contract = _require_contract_for_version_manager(session, contract_slug=contract_slug)
    previous_contract_status = contract.status
    version = create_contract_version(
        session=session,
        contract_slug=contract.slug,
        semantic_version=semantic_version,
        source_code=source_code,
        changelog=changelog,
        status=PublicationStatus.PUBLISHED if publish_now else PublicationStatus.DRAFT,
        auto_commit=False,
    )
    contract_id = _require_persisted_id(contract.id, label="contract")
    version_id = _require_persisted_id(version.id, label="contract_version")
    if publish_now and contract.status not in PUBLIC_VERSION_STATUSES:
        contract.status = PublicationStatus.PUBLISHED
        session.add(contract)
        rebuild_contract_search_document(session, contract_id=contract_id)

    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="publish_contract_version" if publish_now else "create_contract_version",
            entity_type="contract_version",
            entity_id=version_id,
            summary=(
                f"Published version {version.semantic_version} for {contract.slug}."
                if publish_now
                else f"Created draft version {version.semantic_version} for {contract.slug}."
            ),
            details={
                "contract_slug": contract.slug,
                "semantic_version": version.semantic_version,
                "previous_version": (
                    version.previous_version.semantic_version
                    if version.previous_version is not None
                    else None
                ),
                "version_status": version.status.value,
                "previous_contract_status": previous_contract_status.value,
                "next_contract_status": contract.status.value,
            },
        )
    )
    session.commit()
    session.refresh(version)
    return version


def _normalize_preview_semantic_version(value: str) -> str:
    try:
        return validate_semantic_version(value)
    except ValueError as error:
        raise AdminContractVersionManagerServiceError(
            AdminContractVersionManagerServiceErrorCode.INVALID_SEMANTIC_VERSION,
            str(error),
            field="semantic_version",
        ) from error


def _normalize_preview_source_code(value: str) -> str:
    try:
        return validate_contract_source_code(value)
    except ContractVersionServiceError as error:
        raise AdminContractVersionManagerServiceError(
            AdminContractVersionManagerServiceErrorCode.INVALID_SOURCE_CODE,
            str(error),
            field="source_code",
            details=error.as_payload(),
        ) from error


def _normalize_preview_changelog(value: str | None) -> str | None:
    try:
        return normalize_version_changelog(value)
    except ContractVersionServiceError as error:
        raise AdminContractVersionManagerServiceError(
            AdminContractVersionManagerServiceErrorCode.INVALID_CHANGELOG,
            str(error),
            field="changelog",
            details=error.as_payload(),
        ) from error


def _require_contract_for_version_manager(session: Session, *, contract_slug: str) -> Contract:
    normalized_slug = str(contract_slug or "").strip().lower()
    statement = (
        select(Contract)
        .options(
            selectinload(Contract.latest_published_version),
            selectinload(Contract.versions).selectinload(ContractVersion.previous_version),
        )
        .where(Contract.slug == normalized_slug)
    )
    contract = session.exec(statement).first()
    if contract is not None:
        return contract
    raise AdminContractVersionManagerServiceError(
        AdminContractVersionManagerServiceErrorCode.CONTRACT_NOT_FOUND,
        "The requested contract could not be found.",
        field="contract_slug",
        details={"contract_slug": normalized_slug},
    )


def _sort_contract_versions(
    versions: list[ContractVersion],
) -> tuple[ContractVersion, ...]:
    return tuple(
        sorted(
            versions,
            key=lambda version: (
                _sortable_version_datetime(version.published_at or version.created_at),
                _sortable_version_datetime(version.created_at),
                version.id or 0,
            ),
            reverse=True,
        )
    )


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is not None:
        return value
    raise ValueError(f"{label} must be persisted before it can be referenced.")


def _sortable_version_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_admin_version_timestamp(value: object) -> str:
    """Return a stable calendar label for one version timestamp."""
    if value is None:
        return "Pending"
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d")


__all__ = [
    "AdminContractVersionHistoryEntry",
    "AdminContractVersionManagerServiceError",
    "AdminContractVersionManagerServiceErrorCode",
    "AdminContractVersionManagerSnapshot",
    "AdminContractVersionPreview",
    "build_empty_admin_contract_version_manager_snapshot",
    "create_admin_contract_version",
    "format_admin_version_timestamp",
    "load_admin_contract_version_manager_snapshot",
    "load_admin_contract_version_manager_snapshot_safe",
    "preview_admin_contract_version",
]
