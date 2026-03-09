from __future__ import annotations

from contracting_hub.states.contract_detail import (
    _build_source_download_filename,
    _build_source_download_url,
    _count_source_lines,
    _format_line_count,
)


def test_build_source_download_filename_uses_contract_name_and_version() -> None:
    filename = _build_source_download_filename(
        contract_name="con_escrow",
        contract_slug="escrow",
        version_label="1.2.0",
    )

    assert filename == "con_escrow-1.2.0.py"


def test_build_source_download_filename_falls_back_to_slug_and_sanitizes_tokens() -> None:
    filename = _build_source_download_filename(
        contract_name="",
        contract_slug="Escrow Hub",
        version_label="release candidate 1",
    )

    assert filename == "Escrow_Hub-release_candidate_1.py"


def test_build_source_download_url_encodes_python_source_into_a_data_url() -> None:
    download_url = _build_source_download_url("@export\ndef seed():\n    return 'ok'\n")

    assert download_url.startswith("data:text/x-python;charset=utf-8,")
    assert "%0A" in download_url
    assert "'" not in download_url


def test_line_count_helpers_treat_empty_and_non_empty_source_consistently() -> None:
    assert _count_source_lines("") == 0
    assert _count_source_lines("@export\ndef seed():\n    return 'ok'\n") == 3
    assert _format_line_count(1) == "1 line"
    assert _format_line_count(3) == "3 lines"
