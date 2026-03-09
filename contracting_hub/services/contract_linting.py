"""Contract lint service built on top of xian-linter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from contracting_hub.integrations import (
    XianLinterIntegrationError,
    XianLinterIntegrationErrorCode,
    XianLintFinding,
    lint_contract_source,
)
from contracting_hub.models import LintStatus

ERROR_SEVERITIES = frozenset({"error", "fatal"})
WARNING_SEVERITIES = frozenset({"warn", "warning"})


class ContractLintServiceErrorCode(StrEnum):
    """Stable errors surfaced by the contract lint service."""

    LINTER_UNAVAILABLE = "linter_unavailable"
    LINTER_EXECUTION_FAILED = "linter_execution_failed"


class ContractLintServiceError(RuntimeError):
    """Structured contract lint service failure."""

    def __init__(
        self,
        code: ContractLintServiceErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def as_payload(self) -> dict[str, Any]:
        """Serialize the service failure for UI or API consumers."""
        return {
            "code": self.code.value,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class ContractLintReport:
    """Normalized lint report persisted alongside contract versions."""

    status: LintStatus
    findings: tuple[XianLintFinding, ...]
    error_count: int
    warning_count: int
    info_count: int

    @property
    def issue_count(self) -> int:
        """Return the total number of lint issues."""
        return len(self.findings)

    @property
    def has_errors(self) -> bool:
        """Return whether the report contains blocking lint failures."""
        return self.error_count > 0

    @property
    def summary(self) -> dict[str, Any]:
        """Return the persisted summary payload."""
        return {
            "status": self.status.value,
            "issue_count": self.issue_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
        }

    @property
    def results(self) -> list[dict[str, Any]]:
        """Return the persisted issue payloads."""
        return [finding.as_payload() for finding in self.findings]


def lint_contract_source_code(
    source_code: str,
    *,
    whitelist_patterns: Iterable[str] | None = None,
) -> ContractLintReport:
    """Run xian-linter and return a normalized report."""
    try:
        findings = lint_contract_source(
            source_code,
            whitelist_patterns=whitelist_patterns,
        )
    except XianLinterIntegrationError as error:
        raise _map_lint_integration_error(error) from error

    return build_contract_lint_report(findings)


def build_contract_lint_report(findings: Iterable[XianLintFinding]) -> ContractLintReport:
    """Summarize normalized lint findings into persisted version metadata."""
    normalized_findings = tuple(findings)
    error_count = 0
    warning_count = 0
    info_count = 0

    for finding in normalized_findings:
        severity = finding.severity.lower()
        if severity in ERROR_SEVERITIES:
            error_count += 1
        elif severity in WARNING_SEVERITIES:
            warning_count += 1
        else:
            info_count += 1

    return ContractLintReport(
        status=_resolve_lint_status(error_count=error_count, warning_count=warning_count),
        findings=normalized_findings,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
    )


def _resolve_lint_status(*, error_count: int, warning_count: int) -> LintStatus:
    if error_count > 0:
        return LintStatus.FAIL
    if warning_count > 0:
        return LintStatus.WARN
    return LintStatus.PASS


def _map_lint_integration_error(
    error: XianLinterIntegrationError,
) -> ContractLintServiceError:
    if error.code is XianLinterIntegrationErrorCode.UNAVAILABLE:
        return ContractLintServiceError(
            ContractLintServiceErrorCode.LINTER_UNAVAILABLE,
            "Contract linting is unavailable in the current environment.",
            details=error.as_payload(),
        )

    return ContractLintServiceError(
        ContractLintServiceErrorCode.LINTER_EXECUTION_FAILED,
        "Contract linting could not analyze the provided source.",
        details=error.as_payload(),
    )


__all__ = [
    "ContractLintReport",
    "ContractLintServiceError",
    "ContractLintServiceErrorCode",
    "build_contract_lint_report",
    "lint_contract_source_code",
]
