"""Persistence helpers for contract deployment workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import (
    Contract,
    ContractVersion,
    DeploymentHistory,
    DeploymentStatus,
    DeploymentTransport,
    PlaygroundTarget,
    PublicationStatus,
    User,
)

PUBLIC_DEPLOYABLE_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)


@dataclass(frozen=True)
class DeploymentHistoryRecord:
    """Joined deployment-history content used by authenticated account surfaces."""

    deployment_id: int
    contract_slug: str
    contract_display_name: str
    contract_name: str
    semantic_version: str
    playground_id: str
    playground_target_id: int | None
    playground_target_label: str | None
    status: DeploymentStatus
    transport: DeploymentTransport | None
    redirect_url: str | None
    external_request_id: str | None
    initiated_at: datetime
    completed_at: datetime | None
    error_payload: dict[str, object] | None


class DeploymentRepository:
    """Persistence-oriented helpers for deployment requests and history."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_by_id(self, user_id: int) -> User | None:
        """Load one user row for deployment permission checks."""
        statement = select(User).where(User.id == user_id)
        return self._session.exec(statement).first()

    def get_contract_version_by_slug(
        self,
        *,
        contract_slug: str,
        semantic_version: str,
        include_unpublished: bool = False,
    ) -> ContractVersion | None:
        """Load one contract version plus the author context needed for payload metadata."""
        statement = (
            select(ContractVersion)
            .join(Contract, Contract.id == ContractVersion.contract_id)
            .options(
                selectinload(ContractVersion.contract)
                .selectinload(Contract.author)
                .selectinload(User.profile)
            )
            .where(Contract.slug == contract_slug)
            .where(ContractVersion.semantic_version == semantic_version)
        )
        if not include_unpublished:
            statement = statement.where(Contract.status.in_(PUBLIC_DEPLOYABLE_STATUSES))
            statement = statement.where(Contract.latest_published_version_id.is_not(None))
            statement = statement.where(ContractVersion.status.in_(PUBLIC_DEPLOYABLE_STATUSES))
        return self._session.exec(statement).first()

    def get_playground_target_by_id(
        self,
        *,
        user_id: int,
        target_id: int,
    ) -> PlaygroundTarget | None:
        """Load one saved target owned by the authenticated user."""
        statement = (
            select(PlaygroundTarget)
            .where(PlaygroundTarget.user_id == user_id)
            .where(PlaygroundTarget.id == target_id)
        )
        return self._session.exec(statement).first()

    def add_deployment(self, deployment: DeploymentHistory) -> DeploymentHistory:
        """Stage a deployment-history row and assign a primary key."""
        self._session.add(deployment)
        self._session.flush()
        return deployment

    def list_history_for_user(
        self,
        *,
        user_id: int,
        limit: int = 50,
    ) -> list[DeploymentHistoryRecord]:
        """Return one authenticated user's recent deployment attempts."""
        statement = (
            select(
                DeploymentHistory.id.label("deployment_id"),
                Contract.slug.label("contract_slug"),
                Contract.display_name.label("contract_display_name"),
                Contract.contract_name.label("contract_name"),
                ContractVersion.semantic_version.label("semantic_version"),
                DeploymentHistory.playground_id.label("playground_id"),
                DeploymentHistory.playground_target_id.label("playground_target_id"),
                PlaygroundTarget.label.label("playground_target_label"),
                DeploymentHistory.status.label("status"),
                DeploymentHistory.transport.label("transport"),
                DeploymentHistory.redirect_url.label("redirect_url"),
                DeploymentHistory.external_request_id.label("external_request_id"),
                DeploymentHistory.initiated_at.label("initiated_at"),
                DeploymentHistory.completed_at.label("completed_at"),
                DeploymentHistory.error_payload.label("error_payload"),
            )
            .select_from(DeploymentHistory)
            .join(ContractVersion, ContractVersion.id == DeploymentHistory.contract_version_id)
            .join(Contract, Contract.id == ContractVersion.contract_id)
            .outerjoin(
                PlaygroundTarget, PlaygroundTarget.id == DeploymentHistory.playground_target_id
            )
            .where(DeploymentHistory.user_id == user_id)
            .order_by(
                DeploymentHistory.initiated_at.desc(),
                DeploymentHistory.id.desc(),
            )
            .limit(limit)
        )
        rows = self._session.exec(statement).all()
        return [
            DeploymentHistoryRecord(
                deployment_id=int(row.deployment_id),
                contract_slug=row.contract_slug,
                contract_display_name=row.contract_display_name,
                contract_name=row.contract_name,
                semantic_version=row.semantic_version,
                playground_id=row.playground_id,
                playground_target_id=row.playground_target_id,
                playground_target_label=row.playground_target_label,
                status=row.status,
                transport=row.transport,
                redirect_url=row.redirect_url,
                external_request_id=row.external_request_id,
                initiated_at=row.initiated_at,
                completed_at=row.completed_at,
                error_payload=_coerce_error_payload(row.error_payload),
            )
            for row in rows
        ]


def _coerce_error_payload(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {str(key): value[key] for key in value}


__all__ = [
    "DeploymentRepository",
    "DeploymentHistoryRecord",
    "PUBLIC_DEPLOYABLE_STATUSES",
]
