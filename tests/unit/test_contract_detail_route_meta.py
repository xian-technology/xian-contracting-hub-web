from __future__ import annotations

from contracting_hub.utils.meta import build_contract_detail_path


def test_build_contract_detail_path_defaults_to_latest_public_route() -> None:
    assert build_contract_detail_path("escrow") == "/contracts/escrow"


def test_build_contract_detail_path_supports_shareable_version_queries() -> None:
    assert (
        build_contract_detail_path("escrow", semantic_version="1.2.0-rc.1")
        == "/contracts/escrow?version=1.2.0-rc.1"
    )


def test_build_contract_detail_path_ignores_blank_version_queries() -> None:
    assert build_contract_detail_path("escrow", semantic_version="   ") == "/contracts/escrow"
