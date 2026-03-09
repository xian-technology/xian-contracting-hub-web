import pytest

from contracting_hub.services import (
    ContractVersionDiffServiceError,
    ContractVersionDiffServiceErrorCode,
    build_contract_version_diff,
)


def test_build_contract_version_diff_counts_changes_and_renders_unified_output() -> None:
    diff = build_contract_version_diff(
        previous_source_code="def seed():\n    return 'one'\n",
        current_source_code="def seed():\n    value = 'two'\n    return value\n",
        from_version="1.0.0",
        to_version="1.1.0",
    )

    assert diff.summary == {
        "from_version": "1.0.0",
        "to_version": "1.1.0",
        "has_previous_version": True,
        "has_changes": True,
        "added_lines": 2,
        "removed_lines": 1,
        "line_delta": 1,
        "from_line_count": 2,
        "to_line_count": 3,
        "hunk_count": 1,
        "context_lines": 3,
    }
    assert diff.unified_diff is not None
    assert "--- v1.0.0" in diff.unified_diff
    assert "+++ v1.1.0" in diff.unified_diff
    assert "-    return 'one'" in diff.unified_diff
    assert "+    value = 'two'" in diff.unified_diff
    assert "+    return value" in diff.unified_diff


def test_build_contract_version_diff_handles_initial_versions_without_a_baseline() -> None:
    diff = build_contract_version_diff(
        previous_source_code=None,
        current_source_code="def seed():\n    return 'initial'\n",
        to_version="1.0.0",
    )

    assert diff.unified_diff is None
    assert diff.summary == {
        "from_version": None,
        "to_version": "1.0.0",
        "has_previous_version": False,
        "has_changes": False,
        "added_lines": 0,
        "removed_lines": 0,
        "line_delta": 2,
        "from_line_count": 0,
        "to_line_count": 2,
        "hunk_count": 0,
        "context_lines": 3,
    }


def test_build_contract_version_diff_rejects_negative_context_lines() -> None:
    with pytest.raises(ContractVersionDiffServiceError) as error:
        build_contract_version_diff(
            previous_source_code="value = 1\n",
            current_source_code="value = 2\n",
            context_lines=-1,
        )

    assert error.value.code is ContractVersionDiffServiceErrorCode.INVALID_CONTEXT_LINES
    assert error.value.field == "context_lines"
