"""Helpers for contract version source diffs and retrieval."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlmodel import Session

from contracting_hub.models import Contract, ContractVersion, PublicationStatus
from contracting_hub.repositories import ContractVersionRepository
from contracting_hub.services.contract_metadata import validate_semantic_version

VISIBLE_DIFF_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)


class ContractVersionDiffServiceErrorCode(StrEnum):
    """Stable diff retrieval failures exposed to callers."""

    CONTRACT_NOT_FOUND = "contract_not_found"
    INVALID_CONTEXT_LINES = "invalid_context_lines"
    VERSION_NOT_FOUND = "version_not_found"


class ContractVersionDiffServiceError(ValueError):
    """Structured service error for version diff workflows."""

    def __init__(
        self,
        code: ContractVersionDiffServiceErrorCode,
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
class ContractVersionDiff:
    """Combined diff payload for a contract version comparison."""

    unified_diff: str | None
    summary: dict[str, Any]


@dataclass(frozen=True)
class ContractVersionDiffRecord:
    """Resolved contract/version bundle returned by diff lookups."""

    contract: Contract
    version: ContractVersion
    previous_version: ContractVersion | None
    unified_diff: str | None
    summary: dict[str, Any]


def build_contract_diff_summary(
    *,
    previous_source_code: str | None,
    current_source_code: str,
    from_version: str | None = None,
    to_version: str | None = None,
    context_lines: int = 3,
) -> dict[str, Any]:
    """Return line-level summary metadata for a source comparison."""
    normalized_context_lines = _normalize_context_lines(context_lines)
    current_lines = current_source_code.splitlines()
    if previous_source_code is None:
        return {
            "from_version": from_version,
            "to_version": to_version,
            "has_previous_version": False,
            "has_changes": False,
            "added_lines": 0,
            "removed_lines": 0,
            "line_delta": len(current_lines),
            "from_line_count": 0,
            "to_line_count": len(current_lines),
            "hunk_count": 0,
            "context_lines": normalized_context_lines,
        }

    previous_lines = previous_source_code.splitlines()
    matcher = difflib.SequenceMatcher(a=previous_lines, b=current_lines)
    grouped_opcodes = tuple(matcher.get_grouped_opcodes(n=normalized_context_lines))
    added_lines = 0
    removed_lines = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added_lines += j2 - j1
        elif tag == "delete":
            removed_lines += i2 - i1
        elif tag == "replace":
            removed_lines += i2 - i1
            added_lines += j2 - j1

    return {
        "from_version": from_version,
        "to_version": to_version,
        "has_previous_version": True,
        "has_changes": bool(added_lines or removed_lines),
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "line_delta": len(current_lines) - len(previous_lines),
        "from_line_count": len(previous_lines),
        "to_line_count": len(current_lines),
        "hunk_count": len(grouped_opcodes),
        "context_lines": normalized_context_lines,
    }


def build_unified_contract_diff(
    *,
    previous_source_code: str | None,
    current_source_code: str,
    from_version: str | None = None,
    to_version: str | None = None,
    context_lines: int = 3,
) -> str | None:
    """Render a unified diff for a version comparison."""
    normalized_context_lines = _normalize_context_lines(context_lines)
    if previous_source_code is None:
        return None

    diff_lines = difflib.unified_diff(
        previous_source_code.splitlines(keepends=True),
        current_source_code.splitlines(keepends=True),
        fromfile=_format_diff_label(from_version, fallback="previous"),
        tofile=_format_diff_label(to_version, fallback="current"),
        n=normalized_context_lines,
    )
    return "".join(diff_lines)


def build_contract_version_diff(
    *,
    previous_source_code: str | None,
    current_source_code: str,
    from_version: str | None = None,
    to_version: str | None = None,
    context_lines: int = 3,
) -> ContractVersionDiff:
    """Return both unified diff text and structured summary metadata."""
    return ContractVersionDiff(
        unified_diff=build_unified_contract_diff(
            previous_source_code=previous_source_code,
            current_source_code=current_source_code,
            from_version=from_version,
            to_version=to_version,
            context_lines=context_lines,
        ),
        summary=build_contract_diff_summary(
            previous_source_code=previous_source_code,
            current_source_code=current_source_code,
            from_version=from_version,
            to_version=to_version,
            context_lines=context_lines,
        ),
    )


def get_contract_version_diff(
    *,
    session: Session,
    contract_slug: str,
    semantic_version: str | None = None,
    include_unpublished: bool = False,
    context_lines: int = 3,
) -> ContractVersionDiffRecord:
    """Load a contract version and generate the appropriate comparison diff."""
    normalized_context_lines = _normalize_context_lines(context_lines)
    repository = ContractVersionRepository(session)
    contract = repository.get_contract_by_slug(contract_slug)
    if contract is None:
        raise ContractVersionDiffServiceError(
            ContractVersionDiffServiceErrorCode.CONTRACT_NOT_FOUND,
            f"Contract {contract_slug!r} does not exist.",
            field="contract_slug",
            details={"contract_slug": contract_slug},
        )

    normalized_version = (
        validate_semantic_version(semantic_version) if semantic_version is not None else None
    )
    version = repository.get_version_by_slug(
        contract_slug,
        semantic_version=normalized_version,
        include_unpublished=include_unpublished,
    )
    if version is None:
        raise ContractVersionDiffServiceError(
            ContractVersionDiffServiceErrorCode.VERSION_NOT_FOUND,
            (f"Version {normalized_version!r} is not available for contract {contract_slug!r}.")
            if normalized_version is not None
            else f"No diffable version is available for contract {contract_slug!r}.",
            field="semantic_version",
            details={
                "contract_slug": contract_slug,
                "semantic_version": normalized_version,
                "include_unpublished": include_unpublished,
            },
        )

    previous_version = _resolve_previous_version_for_diff(
        version,
        include_unpublished=include_unpublished,
    )
    generated_diff = build_contract_version_diff(
        previous_source_code=previous_version.source_code if previous_version is not None else None,
        current_source_code=version.source_code,
        from_version=previous_version.semantic_version if previous_version is not None else None,
        to_version=version.semantic_version,
        context_lines=normalized_context_lines,
    )
    summary = (
        version.diff_summary
        if _summary_matches_stored_baseline(
            version.diff_summary,
            previous_version=previous_version,
            version=version,
            context_lines=normalized_context_lines,
        )
        else generated_diff.summary
    )
    return ContractVersionDiffRecord(
        contract=version.contract,
        version=version,
        previous_version=previous_version,
        unified_diff=generated_diff.unified_diff,
        summary=summary,
    )


def _resolve_previous_version_for_diff(
    version: ContractVersion,
    *,
    include_unpublished: bool,
) -> ContractVersion | None:
    previous_version = version.previous_version
    if include_unpublished:
        return previous_version

    while previous_version is not None and previous_version.status not in VISIBLE_DIFF_STATUSES:
        previous_version = previous_version.previous_version
    return previous_version


def _summary_matches_stored_baseline(
    summary: dict[str, Any] | None,
    *,
    previous_version: ContractVersion | None,
    version: ContractVersion,
    context_lines: int,
) -> bool:
    if summary is None:
        return False
    return (
        summary.get("from_version")
        == (previous_version.semantic_version if previous_version is not None else None)
        and summary.get("to_version") == version.semantic_version
        and summary.get("context_lines") == context_lines
    )


def _format_diff_label(version: str | None, *, fallback: str) -> str:
    if version is None:
        return fallback
    return f"v{version}"


def _normalize_context_lines(context_lines: int) -> int:
    if isinstance(context_lines, int) and context_lines >= 0:
        return context_lines

    raise ContractVersionDiffServiceError(
        ContractVersionDiffServiceErrorCode.INVALID_CONTEXT_LINES,
        "Diff context_lines must be a non-negative integer.",
        field="context_lines",
        details={"context_lines": context_lines},
    )


__all__ = [
    "ContractVersionDiff",
    "ContractVersionDiffRecord",
    "ContractVersionDiffServiceError",
    "ContractVersionDiffServiceErrorCode",
    "VISIBLE_DIFF_STATUSES",
    "build_contract_diff_summary",
    "build_contract_version_diff",
    "build_unified_contract_diff",
    "get_contract_version_diff",
]
