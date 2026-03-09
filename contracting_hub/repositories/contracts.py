"""Repository helpers for contract catalog reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import (
    Contract,
    ContractCategoryLink,
    ContractRelation,
    ContractVersion,
    DeploymentHistory,
    DeploymentStatus,
    PublicationStatus,
    Rating,
    Star,
    User,
)

PUBLIC_VISIBLE_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)
PUBLIC_HOME_PAGE_DEPLOYMENT_STATUSES: tuple[DeploymentStatus, ...] = (
    DeploymentStatus.PENDING,
    DeploymentStatus.ACCEPTED,
    DeploymentStatus.REDIRECT_REQUIRED,
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


@dataclass(frozen=True)
class ContractHighlightRecord:
    """Contract summary plus aggregate metrics for homepage-style cards."""

    contract: Contract
    star_count: int
    rating_count: int
    average_rating: float | None
    deployment_count: int
    latest_deployment_at: datetime | None


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

    def list_featured_contract_highlights(
        self,
        *,
        limit: int | None = None,
    ) -> list[ContractHighlightRecord]:
        """Return featured public contracts for the homepage spotlight section."""
        return self._list_contract_highlights(
            featured=True,
            limit=limit,
            ordering="featured",
        )

    def list_trending_contract_highlights(
        self,
        *,
        limit: int | None = None,
    ) -> list[ContractHighlightRecord]:
        """Return public contracts ordered by aggregate engagement signals."""
        return self._list_contract_highlights(
            limit=limit,
            ordering="trending",
        )

    def list_recently_updated_contract_highlights(
        self,
        *,
        limit: int | None = None,
    ) -> list[ContractHighlightRecord]:
        """Return public contracts ordered by the latest catalog update timestamp."""
        return self._list_contract_highlights(
            limit=limit,
            ordering="recently_updated",
        )

    def list_recently_deployed_contract_highlights(
        self,
        *,
        limit: int | None = None,
    ) -> list[ContractHighlightRecord]:
        """Return public contracts ordered by their latest visible deployment."""
        return self._list_contract_highlights(
            limit=limit,
            require_deployments=True,
            ordering="recently_deployed",
        )

    def list_authored_contract_highlights(
        self,
        *,
        author_user_id: int,
        limit: int | None = None,
    ) -> list[ContractHighlightRecord]:
        """Return one developer's public authored contracts ordered by recent updates."""
        return self._list_contract_highlights(
            ordering="recently_updated",
            author_user_id=author_user_id,
            limit=limit,
        )

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

    def _list_contract_highlights(
        self,
        *,
        ordering: str,
        author_user_id: int | None = None,
        featured: bool | None = None,
        require_deployments: bool = False,
        limit: int | None = None,
    ) -> list[ContractHighlightRecord]:
        star_metrics = _build_contract_star_metrics_subquery()
        rating_metrics = _build_contract_rating_metrics_subquery()
        deployment_metrics = _build_contract_deployment_metrics_subquery()

        star_count = sa.func.coalesce(star_metrics.c.star_count, 0).label("star_count")
        rating_count = sa.func.coalesce(rating_metrics.c.rating_count, 0).label("rating_count")
        average_rating = rating_metrics.c.average_rating.label("average_rating")
        deployment_count = sa.func.coalesce(deployment_metrics.c.deployment_count, 0).label(
            "deployment_count"
        )
        latest_deployment_at = deployment_metrics.c.latest_deployment_at.label(
            "latest_deployment_at"
        )

        statement = (
            select(
                Contract,
                star_count,
                rating_count,
                average_rating,
                deployment_count,
                latest_deployment_at,
            )
            .options(*_contract_summary_load_options())
            .outerjoin(star_metrics, star_metrics.c.contract_id == Contract.id)
            .outerjoin(rating_metrics, rating_metrics.c.contract_id == Contract.id)
            .outerjoin(deployment_metrics, deployment_metrics.c.contract_id == Contract.id)
        )
        statement = _apply_public_contract_visibility(statement, Contract)

        if author_user_id is not None:
            statement = statement.where(Contract.author_user_id == author_user_id)
        if featured is not None:
            statement = statement.where(Contract.featured.is_(featured))
        if require_deployments:
            statement = statement.where(deployment_count > 0)
        statement = statement.order_by(
            *self._contract_highlight_ordering(
                ordering=ordering,
                star_count=star_count,
                rating_count=rating_count,
                average_rating=average_rating,
                deployment_count=deployment_count,
                latest_deployment_at=latest_deployment_at,
            )
        )
        if limit is not None:
            statement = statement.limit(limit)

        rows = self._session.execute(statement).all()
        return [
            ContractHighlightRecord(
                contract=row[0],
                star_count=int(row[1]),
                rating_count=int(row[2]),
                average_rating=float(row[3]) if row[3] is not None else None,
                deployment_count=int(row[4]),
                latest_deployment_at=row[5],
            )
            for row in rows
        ]

    def _contract_highlight_ordering(
        self,
        *,
        ordering: str,
        star_count: sa.ColumnElement[object],
        rating_count: sa.ColumnElement[object],
        average_rating: sa.ColumnElement[object],
        deployment_count: sa.ColumnElement[object],
        latest_deployment_at: sa.ColumnElement[object],
    ) -> tuple[sa.ColumnElement[object], ...]:
        if ordering == "featured":
            return (
                Contract.updated_at.desc(),
                star_count.desc(),
                Contract.display_name.asc(),
            )
        if ordering == "trending":
            return (
                star_count.desc(),
                deployment_count.desc(),
                sa.func.coalesce(average_rating, 0.0).desc(),
                rating_count.desc(),
                Contract.updated_at.desc(),
                Contract.display_name.asc(),
            )
        if ordering == "recently_updated":
            return (
                Contract.updated_at.desc(),
                star_count.desc(),
                Contract.display_name.asc(),
            )
        if ordering == "recently_deployed":
            return (
                latest_deployment_at.desc(),
                deployment_count.desc(),
                Contract.updated_at.desc(),
                Contract.display_name.asc(),
            )
        raise ValueError(f"Unsupported contract highlight ordering: {ordering}")


def _contract_summary_load_options() -> tuple[object, ...]:
    return (
        selectinload(Contract.author).selectinload(User.profile),
        selectinload(Contract.latest_published_version),
        selectinload(Contract.category_links).selectinload(ContractCategoryLink.category),
    )


def _build_contract_star_metrics_subquery() -> sa.Subquery:
    return (
        sa.select(
            Star.contract_id.label("contract_id"),
            sa.func.count(Star.id).label("star_count"),
        )
        .group_by(Star.contract_id)
        .subquery()
    )


def _build_contract_rating_metrics_subquery() -> sa.Subquery:
    return (
        sa.select(
            Rating.contract_id.label("contract_id"),
            sa.func.count(Rating.id).label("rating_count"),
            sa.func.avg(Rating.score).label("average_rating"),
        )
        .group_by(Rating.contract_id)
        .subquery()
    )


def _build_contract_deployment_metrics_subquery() -> sa.Subquery:
    return (
        sa.select(
            ContractVersion.contract_id.label("contract_id"),
            sa.func.count(DeploymentHistory.id).label("deployment_count"),
            sa.func.max(DeploymentHistory.initiated_at).label("latest_deployment_at"),
        )
        .select_from(DeploymentHistory)
        .join(ContractVersion, ContractVersion.id == DeploymentHistory.contract_version_id)
        .where(DeploymentHistory.status.in_(PUBLIC_HOME_PAGE_DEPLOYMENT_STATUSES))
        .group_by(ContractVersion.contract_id)
        .subquery()
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
        if include_unpublished:
            return statement.where(Contract.status.in_(normalized_statuses))

        visible_statuses = tuple(
            status for status in normalized_statuses if status in PUBLIC_VISIBLE_STATUSES
        )
        if not visible_statuses:
            return statement.where(sa.false())
        return _apply_public_contract_visibility(statement, Contract).where(
            Contract.status.in_(visible_statuses)
        )

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
    "ContractHighlightRecord",
    "ContractRelationTraversal",
    "ContractRepository",
    "ContractSearchResult",
    "PUBLIC_HOME_PAGE_DEPLOYMENT_STATUSES",
    "PUBLIC_VISIBLE_STATUSES",
]
