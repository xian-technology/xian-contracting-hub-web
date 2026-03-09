import pytest

from contracting_hub.integrations import XianLintFinding
from contracting_hub.models import LintStatus
from contracting_hub.services import (
    ContractLintServiceError,
    ContractLintServiceErrorCode,
    build_contract_lint_report,
    lint_contract_source_code,
)


def test_lint_contract_source_code_returns_pass_report_for_valid_contract_source() -> None:
    report = lint_contract_source_code("@export\ndef seed():\n    return 'ok'\n")

    assert report.status is LintStatus.PASS
    assert report.summary == {
        "status": "pass",
        "issue_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
    }
    assert report.results == []


def test_lint_contract_source_code_returns_fail_report_for_invalid_contract_source() -> None:
    report = lint_contract_source_code("def seed():\n    return 'ok'\n")

    assert report.status is LintStatus.FAIL
    assert report.summary["issue_count"] == 1
    assert report.summary["error_count"] == 1
    assert report.results == [
        {
            "message": "S13- No valid contracting decorator found",
            "severity": "error",
            "position": {"line": 0, "column": 0},
        }
    ]


def test_build_contract_lint_report_promotes_warnings_without_errors() -> None:
    report = build_contract_lint_report([XianLintFinding(message="Be careful", severity="warning")])

    assert report.status is LintStatus.WARN
    assert report.summary == {
        "status": "warn",
        "issue_count": 1,
        "error_count": 0,
        "warning_count": 1,
        "info_count": 0,
    }


def test_lint_contract_source_code_maps_integration_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_unavailable(*_args, **_kwargs):
        from contracting_hub.integrations import (
            XianLinterIntegrationError,
            XianLinterIntegrationErrorCode,
        )

        raise XianLinterIntegrationError(
            XianLinterIntegrationErrorCode.UNAVAILABLE,
            "missing dependency",
        )

    monkeypatch.setattr(
        "contracting_hub.services.contract_linting.lint_contract_source",
        _raise_unavailable,
    )

    with pytest.raises(ContractLintServiceError) as error:
        lint_contract_source_code("@export\ndef seed():\n    return 'ok'\n")

    assert error.value.code is ContractLintServiceErrorCode.LINTER_UNAVAILABLE
