"""Repository helpers for contract catalog reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import (
    Contract,
    ContractCategoryLink,
    ContractRelation,
    ContractVersion,
    PublicationStatus,
    User,
)

PUBLIC_VISIBLE_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)
CONTRACT_SEARCH_INDEX_TABLE_NAME = "contract_search_index"


@dataclass(frozen=True)
class ContractRelationTraversal:
    """Resolved incoming and outgoing relations for a contract."""

    outgoing: tuple[ContractRelation, ...]
    incoming: tuple[ContractRelation, ...]


@dataclass(frozen=True)
class ContractDetailRecord:
    """Loaded contract detail bundle used by service and UI layers."""

    contract: Contract
    versions: tuple[ContractVersion, ...]
    relations: ContractRelationTraversal


@dataclass(frozen=True)
class ContractSearchResult:
    """Search hit plus the computed ranking score."""

    contract: Contract
    rank: float


class ContractRepository:
    """Persistence-oriented read queries for contract catalog pages."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_contracts(
        self,
        *,
        include_unpublished: bool = False,
        statuses: Iterable[PublicationStatus] | None = None,
        featured: bool | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Contract]:
        """Return contracts ordered for browse-style list rendering."""
        statement = (
            select(Contract)
            .options(*_contract_summary_load_options())
            .order_by(
                Contract.featured.desc(),
                Contract.updated_at.desc(),
                Contract.display_name.asc(),
            )
        )
        statement = _apply_contract_visibility(
            statement,
            include_unpublished=include_unpublished,
            statuses=statuses,
        )

        if featured is not None:
            statement = statement.where(Contract.featured.is_(featured))
        if offset:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        return list(self._session.exec(statement).all())

    def get_contract_detail(
        self,
        slug: str,
        *,
        include_unpublished: bool = False,
    ) -> ContractDetailRecord | None:
        """Load a contract plus visible versions and related contracts."""
        contract = self._get_contract_by_slug(slug, include_unpublished=include_unpublished)
        if contract is None:
            return None

        return ContractDetailRecord(
            contract=contract,
            versions=self._load_contract_versions(
                contract.id,
                include_unpublished=include_unpublished,
            ),
            relations=self.traverse_relations(
                slug,
                include_unpublished=include_unpublished,
            )
            or ContractRelationTraversal(outgoing=(), incoming=()),
        )

    def get_published_version(
        self,
        contract_slug: str,
        *,
        semantic_version: str | None = None,
    ) -> ContractVersion | None:
        """Return a publicly visible version for a contract."""
        contract = self._get_contract_by_slug(contract_slug, include_unpublished=False)
        if contract is None or contract.latest_published_version_id is None:
            return None

        if semantic_version is None:
            statement = (
                select(ContractVersion)
                .where(ContractVersion.id == contract.latest_published_version_id)
                .where(ContractVersion.status.in_(PUBLIC_VISIBLE_STATUSES))
            )
            return self._session.exec(statement).first()

        statement = (
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract.id)
            .where(ContractVersion.semantic_version == semantic_version)
            .where(ContractVersion.status.in_(PUBLIC_VISIBLE_STATUSES))
            .order_by(*_version_ordering_clause())
        )
        return self._session.exec(statement).first()

    def search_contracts(
        self,
        *,
        match_query: str,
        normalized_query: str,
        include_unpublished: bool = False,
        statuses: Iterable[PublicationStatus] | None = None,
        featured: bool | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ContractSearchResult]:
        """Return contracts ranked by FTS relevance and exact-name boosts."""
        search_index = sa.table(
            CONTRACT_SEARCH_INDEX_TABLE_NAME,
            sa.column("rowid", sa.Integer()),
        )
        lower_query = normalized_query.lower()
        prefix_query = f"{lower_query}%"
        rank_expression = sa.literal_column(
            (
                "bm25("
                f"{CONTRACT_SEARCH_INDEX_TABLE_NAME}, "
                "14.0, 12.0, 10.0, 5.0, 3.0, 8.0, 6.0, 4.0, 1.5"
                ")"
            )
        )
        exact_match_boost = sa.case(
            (sa.func.lower(Contract.contract_name) == lower_query, 3),
            (sa.func.lower(Contract.display_name) == lower_query, 2),
            (sa.func.lower(Contract.slug) == lower_query, 1),
            else_=0,
        )
        prefix_match_boost = sa.case(
            (sa.func.lower(Contract.contract_name).like(prefix_query), 3),
            (sa.func.lower(Contract.display_name).like(prefix_query), 2),
            (sa.func.lower(Contract.slug).like(prefix_query), 1),
            else_=0,
        )
        score = rank_expression.label("search_rank")
        statement = (
            select(Contract, score)
            .join(search_index, search_index.c.rowid == Contract.id)
            .options(*_contract_summary_load_options())
            .where(sa.text(f"{CONTRACT_SEARCH_INDEX_TABLE_NAME} MATCH :match_query"))
            .order_by(
                exact_match_boost.desc(),
                prefix_match_boost.desc(),
                score.asc(),
                Contract.featured.desc(),
                Contract.updated_at.desc(),
                Contract.display_name.asc(),
            )
        )
        statement = _apply_contract_visibility(
            statement,
            include_unpublished=include_unpublished,
            statuses=statuses,
        )

        if featured is not None:
            statement = statement.where(Contract.featured.is_(featured))
        if offset:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        rows = self._session.execute(statement, {"match_query": match_query}).all()
        return [ContractSearchResult(contract=row[0], rank=float(row[1])) for row in rows]

    def traverse_relations(
        self,
        contract_slug: str,
        *,
        include_unpublished: bool = False,
    ) -> ContractRelationTraversal | None:
        """Return incoming and outgoing relations for a visible contract."""
        contract = self._get_contract_by_slug(
            contract_slug,
            include_unpublished=include_unpublished,
        )
        if contract is None:
            return None

        outgoing_statement = (
            select(ContractRelation)
            .where(ContractRelation.source_contract_id == contract.id)
            .options(
                selectinload(ContractRelation.target_contract)
                .selectinload(Contract.author)
                .selectinload(User.profile),
                selectinload(ContractRelation.target_contract)
                .selectinload(Contract.category_links)
                .selectinload(ContractCategoryLink.category),
                selectinload(ContractRelation.target_contract).selectinload(
                    Contract.latest_published_version
                ),
            )
            .order_by(ContractRelation.relation_type.asc(), ContractRelation.id.asc())
        )
        incoming_statement = (
            select(ContractRelation)
            .where(ContractRelation.target_contract_id == contract.id)
            .options(
                selectinload(ContractRelation.source_contract)
                .selectinload(Contract.author)
                .selectinload(User.profile),
                selectinload(ContractRelation.source_contract)
                .selectinload(Contract.category_links)
                .selectinload(ContractCategoryLink.category),
                selectinload(ContractRelation.source_contract).selectinload(
                    Contract.latest_published_version
                ),
            )
            .order_by(ContractRelation.relation_type.asc(), ContractRelation.id.asc())
        )

        if not include_unpublished:
            outgoing_statement = outgoing_statement.join(
                Contract,
                Contract.id == ContractRelation.target_contract_id,
            )
            outgoing_statement = _apply_public_contract_visibility(outgoing_statement, Contract)
            incoming_statement = incoming_statement.join(
                Contract,
                Contract.id == ContractRelation.source_contract_id,
            )
            incoming_statement = _apply_public_contract_visibility(incoming_statement, Contract)

        outgoing = tuple(self._session.exec(outgoing_statement).all())
        incoming = tuple(self._session.exec(incoming_statement).all())
        return ContractRelationTraversal(outgoing=outgoing, incoming=incoming)

    def _get_contract_by_slug(
        self,
        slug: str,
        *,
        include_unpublished: bool,
    ) -> Contract | None:
        statement = (
            select(Contract).where(Contract.slug == slug).options(*_contract_summary_load_options())
        )
        statement = _apply_contract_visibility(
            statement,
            include_unpublished=include_unpublished,
            statuses=None,
        )
        return self._session.exec(statement).first()

    def _load_contract_versions(
        self,
        contract_id: int,
        *,
        include_unpublished: bool,
    ) -> tuple[ContractVersion, ...]:
        statement = (
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract_id)
            .order_by(*_version_ordering_clause())
        )
        if not include_unpublished:
            statement = statement.where(ContractVersion.status.in_(PUBLIC_VISIBLE_STATUSES))
        return tuple(self._session.exec(statement).all())


def _contract_summary_load_options() -> tuple[object, ...]:
    return (
        selectinload(Contract.author).selectinload(User.profile),
        selectinload(Contract.latest_published_version),
        selectinload(Contract.category_links).selectinload(ContractCategoryLink.category),
    )


def _apply_contract_visibility(
    statement: sa.sql.Select,
    *,
    include_unpublished: bool,
    statuses: Iterable[PublicationStatus] | None,
) -> sa.sql.Select:
    if statuses is not None:
        normalized_statuses = tuple(dict.fromkeys(statuses))
        if not normalized_statuses:
            return statement.where(sa.false())
        return statement.where(Contract.status.in_(normalized_statuses))

    if include_unpublished:
        return statement

    return _apply_public_contract_visibility(statement, Contract)


def _apply_public_contract_visibility(
    statement: sa.sql.Select,
    contract_model: type[Contract],
) -> sa.sql.Select:
    return statement.where(contract_model.status.in_(PUBLIC_VISIBLE_STATUSES)).where(
        contract_model.latest_published_version_id.is_not(None)
    )


def _version_ordering_clause() -> tuple[sa.ColumnElement[object], ...]:
    return (
        sa.case((ContractVersion.published_at.is_(None), 1), else_=0).asc(),
        ContractVersion.published_at.desc(),
        ContractVersion.created_at.desc(),
        ContractVersion.id.desc(),
    )


__all__ = [
    "CONTRACT_SEARCH_INDEX_TABLE_NAME",
    "ContractDetailRecord",
    "ContractRelationTraversal",
    "ContractRepository",
    "ContractSearchResult",
    "PUBLIC_VISIBLE_STATUSES",
]
