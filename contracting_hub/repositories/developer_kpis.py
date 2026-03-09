"""Persistence helpers for developer KPI and leaderboard workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Session

from contracting_hub.models import (
    Contract,
    ContractVersion,
    DeploymentHistory,
    Profile,
    PublicationStatus,
    Rating,
    Star,
    User,
)

PUBLISHED_KPI_CONTRACT_STATUSES: tuple[PublicationStatus, ...] = (PublicationStatus.PUBLISHED,)


@dataclass(frozen=True)
class DeveloperKPIRecord:
    """Aggregated leaderboard metrics for one developer profile."""

    user_id: int
    username: str
    display_name: str | None
    avatar_path: str | None
    published_contract_count: int
    total_stars_received: int
    weighted_average_rating: float | None
    total_rating_count: int
    total_deployment_count: int
    recent_published_contract_count: int
    recent_publish_count: int
    recent_stars_received: int
    recent_weighted_average_rating: float | None
    recent_rating_count: int
    recent_deployment_count: int

    @property
    def recent_activity_count(self) -> int:
        """Return the combined recent activity total used for leaderboard windows."""
        return (
            self.recent_publish_count
            + self.recent_stars_received
            + self.recent_rating_count
            + self.recent_deployment_count
        )


class DeveloperKPIRepository:
    """Persistence-oriented helpers for developer metrics and leaderboards."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_developer_kpis_by_username(
        self,
        *,
        username: str,
        activity_since: datetime,
    ) -> DeveloperKPIRecord | None:
        """Load one public developer KPI snapshot by username."""
        metrics = self._build_metrics_subquery(activity_since=activity_since)
        statement = sa.select(metrics).where(metrics.c.username == username)
        row = self._session.execute(statement).mappings().first()
        if row is None:
            return None
        return _build_kpi_record(row)

    def list_developer_kpis(
        self,
        *,
        activity_since: datetime,
        sort_by: str,
        timeframe: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DeveloperKPIRecord]:
        """List public developer KPI rows ordered for leaderboard rendering."""
        metrics = self._build_metrics_subquery(activity_since=activity_since)
        statement = sa.select(metrics).where(metrics.c.published_contract_count > 0)
        if timeframe == "recent":
            statement = statement.where(metrics.c.recent_activity_count > 0)

        statement = statement.order_by(
            *self._leaderboard_order_expressions(
                metrics=metrics,
                sort_by=sort_by,
                timeframe=timeframe,
            )
        )
        if offset:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        rows = self._session.execute(statement).mappings().all()
        return [_build_kpi_record(row) for row in rows]

    def _build_metrics_subquery(self, *, activity_since: datetime) -> sa.Subquery:
        contracts = self._build_contract_aggregate_subquery()
        stars = self._build_star_aggregate_subquery(activity_since=activity_since)
        ratings = self._build_rating_aggregate_subquery(activity_since=activity_since)
        deployments = self._build_deployment_aggregate_subquery(activity_since=activity_since)
        publishes = self._build_publish_aggregate_subquery(activity_since=activity_since)

        recent_publish_count = sa.func.coalesce(publishes.c.recent_publish_count, 0)
        recent_stars_received = sa.func.coalesce(stars.c.recent_stars_received, 0)
        recent_rating_count = sa.func.coalesce(ratings.c.recent_rating_count, 0)
        recent_deployment_count = sa.func.coalesce(deployments.c.recent_deployment_count, 0)

        return (
            sa.select(
                User.id.label("user_id"),
                Profile.username.label("username"),
                Profile.display_name.label("display_name"),
                Profile.avatar_path.label("avatar_path"),
                sa.func.coalesce(contracts.c.published_contract_count, 0).label(
                    "published_contract_count"
                ),
                sa.func.coalesce(stars.c.total_stars_received, 0).label("total_stars_received"),
                ratings.c.weighted_average_rating.label("weighted_average_rating"),
                sa.func.coalesce(ratings.c.total_rating_count, 0).label("total_rating_count"),
                sa.func.coalesce(deployments.c.total_deployment_count, 0).label(
                    "total_deployment_count"
                ),
                sa.func.coalesce(publishes.c.recent_published_contract_count, 0).label(
                    "recent_published_contract_count"
                ),
                recent_publish_count.label("recent_publish_count"),
                recent_stars_received.label("recent_stars_received"),
                ratings.c.recent_weighted_average_rating.label("recent_weighted_average_rating"),
                recent_rating_count.label("recent_rating_count"),
                recent_deployment_count.label("recent_deployment_count"),
                (
                    recent_publish_count
                    + recent_stars_received
                    + recent_rating_count
                    + recent_deployment_count
                ).label("recent_activity_count"),
            )
            .select_from(Profile)
            .join(User, User.id == Profile.user_id)
            .outerjoin(contracts, contracts.c.author_user_id == User.id)
            .outerjoin(stars, stars.c.author_user_id == User.id)
            .outerjoin(ratings, ratings.c.author_user_id == User.id)
            .outerjoin(deployments, deployments.c.author_user_id == User.id)
            .outerjoin(publishes, publishes.c.author_user_id == User.id)
            .subquery()
        )

    def _build_contract_aggregate_subquery(self) -> sa.Subquery:
        return (
            sa.select(
                Contract.author_user_id.label("author_user_id"),
                sa.func.count(sa.distinct(Contract.id)).label("published_contract_count"),
            )
            .where(Contract.author_user_id.is_not(None))
            .where(Contract.status.in_(PUBLISHED_KPI_CONTRACT_STATUSES))
            .group_by(Contract.author_user_id)
            .subquery()
        )

    def _build_star_aggregate_subquery(self, *, activity_since: datetime) -> sa.Subquery:
        recent_stars = sa.func.sum(
            sa.case(
                (Star.created_at >= activity_since, 1),
                else_=0,
            )
        )
        return (
            sa.select(
                Contract.author_user_id.label("author_user_id"),
                sa.func.count(Star.id).label("total_stars_received"),
                recent_stars.label("recent_stars_received"),
            )
            .select_from(Star)
            .join(Contract, Contract.id == Star.contract_id)
            .where(Contract.author_user_id.is_not(None))
            .where(Contract.status.in_(PUBLISHED_KPI_CONTRACT_STATUSES))
            .group_by(Contract.author_user_id)
            .subquery()
        )

    def _build_rating_aggregate_subquery(self, *, activity_since: datetime) -> sa.Subquery:
        recent_scores = sa.case(
            (Rating.updated_at >= activity_since, Rating.score),
            else_=None,
        )
        recent_rating_count = sa.func.sum(
            sa.case(
                (Rating.updated_at >= activity_since, 1),
                else_=0,
            )
        )
        return (
            sa.select(
                Contract.author_user_id.label("author_user_id"),
                sa.func.count(Rating.id).label("total_rating_count"),
                sa.func.avg(Rating.score).label("weighted_average_rating"),
                recent_rating_count.label("recent_rating_count"),
                sa.func.avg(recent_scores).label("recent_weighted_average_rating"),
            )
            .select_from(Rating)
            .join(Contract, Contract.id == Rating.contract_id)
            .where(Contract.author_user_id.is_not(None))
            .where(Contract.status.in_(PUBLISHED_KPI_CONTRACT_STATUSES))
            .group_by(Contract.author_user_id)
            .subquery()
        )

    def _build_deployment_aggregate_subquery(self, *, activity_since: datetime) -> sa.Subquery:
        recent_deployments = sa.func.sum(
            sa.case(
                (DeploymentHistory.initiated_at >= activity_since, 1),
                else_=0,
            )
        )
        return (
            sa.select(
                Contract.author_user_id.label("author_user_id"),
                sa.func.count(DeploymentHistory.id).label("total_deployment_count"),
                recent_deployments.label("recent_deployment_count"),
            )
            .select_from(DeploymentHistory)
            .join(ContractVersion, ContractVersion.id == DeploymentHistory.contract_version_id)
            .join(Contract, Contract.id == ContractVersion.contract_id)
            .where(Contract.author_user_id.is_not(None))
            .where(Contract.status.in_(PUBLISHED_KPI_CONTRACT_STATUSES))
            .group_by(Contract.author_user_id)
            .subquery()
        )

    def _build_publish_aggregate_subquery(self, *, activity_since: datetime) -> sa.Subquery:
        recent_publish_condition = ContractVersion.published_at >= activity_since
        return (
            sa.select(
                Contract.author_user_id.label("author_user_id"),
                sa.func.count(
                    sa.distinct(
                        sa.case(
                            (recent_publish_condition, ContractVersion.contract_id),
                            else_=None,
                        )
                    )
                ).label("recent_published_contract_count"),
                sa.func.sum(
                    sa.case(
                        (recent_publish_condition, 1),
                        else_=0,
                    )
                ).label("recent_publish_count"),
            )
            .select_from(ContractVersion)
            .join(Contract, Contract.id == ContractVersion.contract_id)
            .where(Contract.author_user_id.is_not(None))
            .where(Contract.status.in_(PUBLISHED_KPI_CONTRACT_STATUSES))
            .where(ContractVersion.published_at.is_not(None))
            .group_by(Contract.author_user_id)
            .subquery()
        )

    def _leaderboard_order_expressions(
        self,
        *,
        metrics: sa.Subquery,
        sort_by: str,
        timeframe: str,
    ) -> tuple[sa.ColumnElement[object], ...]:
        if timeframe == "recent":
            star_total = metrics.c.recent_stars_received
            contract_count = metrics.c.recent_published_contract_count
            recent_orders: dict[str, tuple[sa.ColumnElement[object], ...]] = {
                "contract_count": (
                    metrics.c.recent_published_contract_count.desc(),
                    star_total.desc(),
                    metrics.c.username.asc(),
                ),
                "star_total": (
                    star_total.desc(),
                    contract_count.desc(),
                    metrics.c.username.asc(),
                ),
                "weighted_rating": (
                    sa.func.coalesce(metrics.c.recent_weighted_average_rating, 0.0).desc(),
                    star_total.desc(),
                    contract_count.desc(),
                    metrics.c.username.asc(),
                ),
                "deployment_count": (
                    metrics.c.recent_deployment_count.desc(),
                    star_total.desc(),
                    contract_count.desc(),
                    metrics.c.username.asc(),
                ),
                "recent_activity": (
                    metrics.c.recent_activity_count.desc(),
                    star_total.desc(),
                    contract_count.desc(),
                    metrics.c.username.asc(),
                ),
            }
            return recent_orders[sort_by]

        all_time_orders: dict[str, tuple[sa.ColumnElement[object], ...]] = {
            "contract_count": (
                metrics.c.published_contract_count.desc(),
                metrics.c.total_stars_received.desc(),
                metrics.c.username.asc(),
            ),
            "star_total": (
                metrics.c.total_stars_received.desc(),
                metrics.c.published_contract_count.desc(),
                metrics.c.username.asc(),
            ),
            "weighted_rating": (
                sa.func.coalesce(metrics.c.weighted_average_rating, 0.0).desc(),
                metrics.c.total_stars_received.desc(),
                metrics.c.published_contract_count.desc(),
                metrics.c.username.asc(),
            ),
            "deployment_count": (
                metrics.c.total_deployment_count.desc(),
                metrics.c.total_stars_received.desc(),
                metrics.c.published_contract_count.desc(),
                metrics.c.username.asc(),
            ),
            "recent_activity": (
                metrics.c.recent_activity_count.desc(),
                metrics.c.total_stars_received.desc(),
                metrics.c.published_contract_count.desc(),
                metrics.c.username.asc(),
            ),
        }
        return all_time_orders[sort_by]


def _build_kpi_record(row: sa.RowMapping) -> DeveloperKPIRecord:
    return DeveloperKPIRecord(
        user_id=int(row["user_id"]),
        username=str(row["username"]),
        display_name=row["display_name"],
        avatar_path=row["avatar_path"],
        published_contract_count=int(row["published_contract_count"]),
        total_stars_received=int(row["total_stars_received"]),
        weighted_average_rating=(
            float(row["weighted_average_rating"])
            if row["weighted_average_rating"] is not None
            else None
        ),
        total_rating_count=int(row["total_rating_count"]),
        total_deployment_count=int(row["total_deployment_count"]),
        recent_published_contract_count=int(row["recent_published_contract_count"]),
        recent_publish_count=int(row["recent_publish_count"]),
        recent_stars_received=int(row["recent_stars_received"]),
        recent_weighted_average_rating=(
            float(row["recent_weighted_average_rating"])
            if row["recent_weighted_average_rating"] is not None
            else None
        ),
        recent_rating_count=int(row["recent_rating_count"]),
        recent_deployment_count=int(row["recent_deployment_count"]),
    )


__all__ = [
    "DeveloperKPIRecord",
    "DeveloperKPIRepository",
    "PUBLISHED_KPI_CONTRACT_STATUSES",
]
