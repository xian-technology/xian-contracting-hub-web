from contracting_hub.services import (
    ContractBrowseSort,
    build_contract_browse_path,
    normalize_contract_browse_page,
    normalize_contract_browse_sort,
)


def test_normalize_contract_browse_sort_defaults_based_on_query_presence() -> None:
    assert normalize_contract_browse_sort(None, has_query=False) is ContractBrowseSort.FEATURED
    assert normalize_contract_browse_sort(None, has_query=True) is ContractBrowseSort.RELEVANCE
    assert (
        normalize_contract_browse_sort("not-a-sort", has_query=False) is ContractBrowseSort.FEATURED
    )
    assert (
        normalize_contract_browse_sort("not-a-sort", has_query=True) is ContractBrowseSort.RELEVANCE
    )


def test_build_contract_browse_path_normalizes_and_omits_default_state() -> None:
    assert (
        build_contract_browse_path(
            query="  Escrow   Vault  ",
            sort="relevance",
            page="1",
        )
        == "/browse?query=Escrow+Vault"
    )
    assert (
        build_contract_browse_path(
            query="escrow",
            category_slug=" DeFi ",
            tag=" Settlement ",
            sort="top_rated",
            page="2",
        )
        == "/browse?query=escrow&category=defi&tag=settlement&sort=top_rated&page=2"
    )
    assert normalize_contract_browse_page("garbage") == 1
