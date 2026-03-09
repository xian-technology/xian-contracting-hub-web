"""Xian linter integration boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable


class XianLinterIntegrationErrorCode(StrEnum):
    """Stable failure modes surfaced by the local xian-linter adapter."""

    UNAVAILABLE = "unavailable"
    EXECUTION_FAILED = "execution_failed"


class XianLinterIntegrationError(RuntimeError):
    """Structured error raised when the local linter cannot run."""

    def __init__(
        self,
        code: XianLinterIntegrationErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def as_payload(self) -> dict[str, Any]:
        """Serialize the adapter failure for service-layer mapping."""
        return {
            "code": self.code.value,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class XianLintPosition:
    """Normalized lint finding position."""

    line: int
    column: int

    def as_payload(self) -> dict[str, int]:
        """Return the persisted JSON shape for the lint position."""
        return {"line": self.line, "column": self.column}


@dataclass(frozen=True, slots=True)
class XianLintFinding:
    """Normalized lint finding returned by the adapter."""

    message: str
    severity: str
    position: XianLintPosition | None = None

    def as_payload(self) -> dict[str, Any]:
        """Return the persisted JSON shape for the lint finding."""
        payload: dict[str, Any] = {
            "message": self.message,
            "severity": self.severity,
        }
        if self.position is not None:
            payload["position"] = self.position.as_payload()
        return payload


def lint_contract_source(
    source_code: str,
    *,
    whitelist_patterns: Iterable[str] | None = None,
) -> tuple[XianLintFinding, ...]:
    """Run xian-linter synchronously and normalize its findings."""
    lint_code_inline = _load_lint_callable()
    try:
        raw_findings = lint_code_inline(source_code, whitelist_patterns=whitelist_patterns)
    except Exception as error:  # pragma: no cover - defensive adapter boundary
        raise XianLinterIntegrationError(
            XianLinterIntegrationErrorCode.EXECUTION_FAILED,
            "xian-linter could not analyze the contract source.",
            details={"error": str(error)},
        ) from error

    return tuple(_normalize_lint_finding(finding) for finding in raw_findings)


def _load_lint_callable():
    try:
        from xian_linter import lint_code_inline
    except ImportError as error:  # pragma: no cover - environment specific
        raise XianLinterIntegrationError(
            XianLinterIntegrationErrorCode.UNAVAILABLE,
            "xian-linter is not installed in the current environment.",
            details={"error": str(error)},
        ) from error
    return lint_code_inline


def _normalize_lint_finding(finding: Any) -> XianLintFinding:
    position = finding.position
    normalized_position: XianLintPosition | None = None
    if position is not None:
        normalized_position = XianLintPosition(
            line=int(position.line),
            column=int(position.column),
        )

    return XianLintFinding(
        message=str(finding.message),
        severity=str(finding.severity).lower().strip(),
        position=normalized_position,
    )


__all__ = [
    "XianLintFinding",
    "XianLintPosition",
    "XianLinterIntegrationError",
    "XianLinterIntegrationErrorCode",
    "lint_contract_source",
]
