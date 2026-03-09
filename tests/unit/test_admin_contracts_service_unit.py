from __future__ import annotations

from contracting_hub.services.admin_contracts import (
    AdminContractFeaturedFilter,
    AdminContractStatusFilter,
    build_admin_contracts_path,
    normalize_admin_contract_featured_filter,
    normalize_admin_contract_status_filter,
)


def test_admin_contract_filter_normalizers_fall_back_to_safe_defaults() -> None:
    assert normalize_admin_contract_status_filter(None) is AdminContractStatusFilter.ALL
    assert (
        normalize_admin_contract_status_filter(" published ") is AdminContractStatusFilter.PUBLISHED
    )
    assert normalize_admin_contract_status_filter("unknown") is AdminContractStatusFilter.ALL

    assert normalize_admin_contract_featured_filter(None) is AdminContractFeaturedFilter.ALL
    assert (
        normalize_admin_contract_featured_filter(" not_featured ")
        is AdminContractFeaturedFilter.NOT_FEATURED
    )
    assert normalize_admin_contract_featured_filter("other") is AdminContractFeaturedFilter.ALL


def test_build_admin_contracts_path_omits_defaults_and_canonicalizes_filters() -> None:
    assert build_admin_contracts_path() == "/admin/contracts"
    assert (
        build_admin_contracts_path(
            query="  escrow  ",
            status_filter="draft",
            featured_filter="not_featured",
        )
        == "/admin/contracts?query=escrow&status=draft&featured=not_featured"
    )
    assert (
        build_admin_contracts_path(status_filter="all", featured_filter="all") == "/admin/contracts"
    )
