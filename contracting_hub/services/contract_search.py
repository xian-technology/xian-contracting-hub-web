"""SQLite FTS-backed search helpers for the contract catalog."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import (
    Category,
    Contract,
    ContractCategoryLink,
    Profile,
    PublicationStatus,
    User,
)
from contracting_hub.repositories import (
    CONTRACT_SEARCH_INDEX_TABLE_NAME,
    ContractRepository,
    ContractSearchResult,
)

SEARCH_QUERY_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
INDEXED_SOURCE_MAX_LINES = 40
INDEXED_SOURCE_MAX_CHARS = 4000
SEARCH_INDEX_SHADOW_TABLE_NAMES = {
    CONTRACT_SEARCH_INDEX_TABLE_NAME,
    f"{CONTRACT_SEARCH_INDEX_TABLE_NAME}_config",
    f"{CONTRACT_SEARCH_INDEX_TABLE_NAME}_content",
    f"{CONTRACT_SEARCH_INDEX_TABLE_NAME}_data",
    f"{CONTRACT_SEARCH_INDEX_TABLE_NAME}_docsize",
    f"{CONTRACT_SEARCH_INDEX_TABLE_NAME}_idx",
}


@dataclass(frozen=True)
class ContractSearchDocument:
    """Materialized search text persisted into the FTS table."""

    contract_id: int
    slug: str
    contract_name: str
    display_name: str
    short_summary: str
    long_description: str
    author_text: str
    category_text: str
    tags_text: str
    source_text: str


def normalize_contract_search_query(query: str | None) -> str:
    """Collapse user input into a stable query string."""
    if query is None:
        return ""
    return " ".join(query.split())


def build_contract_search_match_expression(query: str | None) -> str | None:
    """Compile user input into a safe FTS5 match expression."""
    normalized_query = normalize_contract_search_query(query).lower()
    tokens = SEARCH_QUERY_TOKEN_PATTERN.findall(normalized_query)
    if not tokens:
        return None

    prefix_clause = " AND ".join(f"{token}*" for token in tokens)
    if len(tokens) == 1:
        return prefix_clause

    phrase_clause = f'"{" ".join(tokens)}"'
    return f"({phrase_clause}) OR ({prefix_clause})"


def extract_indexed_source_text(
    source_code: str | None,
    *,
    max_lines: int = INDEXED_SOURCE_MAX_LINES,
    max_chars: int = INDEXED_SOURCE_MAX_CHARS,
) -> str:
    """Return a bounded excerpt from the latest public source snapshot."""
    if not source_code:
        return ""

    excerpt = "\n".join(line.rstrip() for line in source_code.splitlines() if line.strip()).strip()
    if not excerpt:
        return ""

    limited_lines = "\n".join(excerpt.splitlines()[:max_lines]).strip()
    if len(limited_lines) <= max_chars:
        return limited_lines
    return limited_lines[:max_chars].rstrip()


def build_contract_search_document(contract: Contract) -> ContractSearchDocument:
    """Build the persisted search document for a contract."""
    if contract.id is None:
        raise ValueError("Contracts must be persisted before indexing.")

    latest_public_version = contract.latest_published_version
    return ContractSearchDocument(
        contract_id=contract.id,
        slug=contract.slug,
        contract_name=contract.contract_name,
        display_name=contract.display_name,
        short_summary=contract.short_summary,
        long_description=contract.long_description,
        author_text=_resolve_author_search_text(contract),
        category_text=_resolve_category_search_text(contract),
        tags_text=_join_search_terms(contract.tags),
        source_text=extract_indexed_source_text(
            latest_public_version.source_code if latest_public_version is not None else None
        ),
    )


def ensure_contract_search_schema(session: Session) -> None:
    """Create the SQLite FTS table lazily when it is missing."""
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return

    existing_table = session.execute(
        sa.text(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = :table_name
            """
        ),
        {"table_name": CONTRACT_SEARCH_INDEX_TABLE_NAME},
    ).scalar_one_or_none()
    if existing_table is not None:
        return

    session.execute(
        sa.text(
            f"""
            CREATE VIRTUAL TABLE {CONTRACT_SEARCH_INDEX_TABLE_NAME} USING fts5(
                slug,
                contract_name,
                display_name,
                short_summary,
                long_description,
                author_text,
                category_text,
                tags_text,
                source_text,
                tokenize = 'unicode61'
            )
            """
        )
    )


def rebuild_contract_search_index(session: Session) -> None:
    """Rebuild the entire search index from current contract rows."""
    ensure_contract_search_schema(session)
    session.execute(sa.text(f"DELETE FROM {CONTRACT_SEARCH_INDEX_TABLE_NAME}"))
    for contract in _load_contracts_for_search_index(session):
        _insert_contract_search_document(session, build_contract_search_document(contract))


def rebuild_contract_search_document(session: Session, *, contract_id: int) -> None:
    """Rebuild the search document for one contract."""
    ensure_contract_search_schema(session)
    session.execute(
        sa.text(f"DELETE FROM {CONTRACT_SEARCH_INDEX_TABLE_NAME} WHERE rowid = :contract_id"),
        {"contract_id": contract_id},
    )

    contract = _load_contract_for_search_index(session, contract_id=contract_id)
    if contract is None:
        return

    _insert_contract_search_document(session, build_contract_search_document(contract))


def search_contract_catalog(
    *,
    session: Session,
    query: str | None,
    include_unpublished: bool = False,
    statuses: Iterable[PublicationStatus] | None = None,
    featured: bool | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[ContractSearchResult]:
    """Return browse-ready contract search results."""
    repository = ContractRepository(session)
    normalized_query = normalize_contract_search_query(query)
    if not normalized_query:
        return [
            ContractSearchResult(contract=contract, rank=0.0)
            for contract in repository.list_contracts(
                include_unpublished=include_unpublished,
                statuses=statuses,
                featured=featured,
                limit=limit,
                offset=offset,
            )
        ]

    match_query = build_contract_search_match_expression(normalized_query)
    if match_query is None:
        return []

    _ensure_populated_contract_search_index(session)
    return repository.search_contracts(
        match_query=match_query,
        normalized_query=normalized_query,
        include_unpublished=include_unpublished,
        statuses=statuses,
        featured=featured,
        limit=limit,
        offset=offset,
    )


def _ensure_populated_contract_search_index(session: Session) -> None:
    ensure_contract_search_schema(session)
    document_count = session.execute(
        sa.text(f"SELECT COUNT(*) FROM {CONTRACT_SEARCH_INDEX_TABLE_NAME}")
    ).scalar_one()
    if document_count:
        return

    contract_count = session.execute(sa.select(sa.func.count()).select_from(Contract)).scalar_one()
    if contract_count:
        rebuild_contract_search_index(session)


def _load_contracts_for_search_index(session: Session) -> list[Contract]:
    statement = select(Contract).options(*_search_index_load_options()).order_by(Contract.id.asc())
    return list(session.exec(statement).all())


def _load_contract_for_search_index(
    session: Session,
    *,
    contract_id: int,
) -> Contract | None:
    statement = (
        select(Contract).where(Contract.id == contract_id).options(*_search_index_load_options())
    )
    return session.exec(statement).first()


def _search_index_load_options() -> tuple[object, ...]:
    return (
        selectinload(Contract.author).selectinload(User.profile),
        selectinload(Contract.latest_published_version),
        selectinload(Contract.category_links).selectinload(ContractCategoryLink.category),
    )


def _resolve_author_search_text(contract: Contract) -> str:
    profile: Profile | None = None
    if contract.author is not None:
        profile = contract.author.profile

    return _join_search_terms(
        (
            profile.display_name if profile is not None else None,
            profile.username if profile is not None else None,
            contract.author_label,
        )
    )


def _resolve_category_search_text(contract: Contract) -> str:
    return _join_search_terms(
        term
        for category in _iter_contract_categories(contract)
        for term in (category.name, category.slug)
    )


def _iter_contract_categories(contract: Contract) -> tuple[Category, ...]:
    return tuple(link.category for link in contract.category_links if link.category is not None)


def _join_search_terms(terms: Iterable[str | None]) -> str:
    normalized_terms: list[str] = []
    seen_terms: set[str] = set()
    for term in terms:
        if term is None:
            continue
        cleaned = " ".join(term.split())
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen_terms:
            continue
        seen_terms.add(lowered)
        normalized_terms.append(cleaned)
    return " ".join(normalized_terms)


def _insert_contract_search_document(
    session: Session,
    document: ContractSearchDocument,
) -> None:
    session.execute(
        sa.text(
            f"""
            INSERT INTO {CONTRACT_SEARCH_INDEX_TABLE_NAME} (
                rowid,
                slug,
                contract_name,
                display_name,
                short_summary,
                long_description,
                author_text,
                category_text,
                tags_text,
                source_text
            ) VALUES (
                :rowid,
                :slug,
                :contract_name,
                :display_name,
                :short_summary,
                :long_description,
                :author_text,
                :category_text,
                :tags_text,
                :source_text
            )
            """
        ),
        {
            "rowid": document.contract_id,
            "slug": document.slug,
            "contract_name": document.contract_name,
            "display_name": document.display_name,
            "short_summary": document.short_summary,
            "long_description": document.long_description,
            "author_text": document.author_text,
            "category_text": document.category_text,
            "tags_text": document.tags_text,
            "source_text": document.source_text,
        },
    )


__all__ = [
    "ContractSearchDocument",
    "INDEXED_SOURCE_MAX_CHARS",
    "INDEXED_SOURCE_MAX_LINES",
    "SEARCH_INDEX_SHADOW_TABLE_NAMES",
    "SEARCH_QUERY_TOKEN_PATTERN",
    "build_contract_search_document",
    "build_contract_search_match_expression",
    "ensure_contract_search_schema",
    "extract_indexed_source_text",
    "normalize_contract_search_query",
    "rebuild_contract_search_document",
    "rebuild_contract_search_index",
    "search_contract_catalog",
]
