from contracting_hub.models import (
    Category,
    Contract,
    ContractCategoryLink,
    ContractVersion,
    Profile,
    User,
)
from contracting_hub.services import (
    build_contract_search_document,
    build_contract_search_match_expression,
    extract_indexed_source_text,
    normalize_contract_search_query,
)


def test_normalize_contract_search_query_collapses_whitespace() -> None:
    assert normalize_contract_search_query("  Escrow   Vault \n  ") == "Escrow Vault"


def test_build_contract_search_match_expression_adds_phrase_and_prefix_matching() -> None:
    assert build_contract_search_match_expression("Escrow Vault") == (
        '("escrow vault") OR (escrow* AND vault*)'
    )
    assert build_contract_search_match_expression("  ") is None


def test_extract_indexed_source_text_drops_blank_lines_and_honors_limits() -> None:
    source_code = "\n\n@export\n\ndef seed():\n    return 'ok'\n\n# trailing comment\n"

    excerpt = extract_indexed_source_text(source_code, max_lines=2, max_chars=20)

    assert excerpt == "@export\ndef seed():"


def test_build_contract_search_document_collects_public_metadata_fields() -> None:
    author = User(email="alice@example.com", password_hash="hashed")
    author.profile = Profile(username="alice", display_name="Alice")
    contract = Contract(
        id=7,
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Curated escrow primitives.",
        long_description="Detailed escrow description for sandbox settlement flows.",
        author=author,
        featured=True,
        tags=["escrow", "settlement", "escrow"],
    )
    category = Category(id=3, slug="defi", name="DeFi", sort_order=10)
    contract.category_links.append(
        ContractCategoryLink(contract=contract, category=category, is_primary=True)
    )
    contract.latest_published_version = ContractVersion(
        semantic_version="1.0.0",
        source_code="@export\n\ndef settle(amount):\n    return amount\n",
        source_hash_sha256="a" * 64,
    )

    document = build_contract_search_document(contract)

    assert document.contract_id == 7
    assert document.author_text == "Alice"
    assert document.category_text == "DeFi"
    assert document.tags_text == "escrow settlement"
    assert document.source_text == "@export\ndef settle(amount):\n    return amount"
