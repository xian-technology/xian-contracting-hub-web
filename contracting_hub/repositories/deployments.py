"""Persistence helpers for contract deployment workflows."""

from __future__ import annotations

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import (
    Contract,
    ContractVersion,
    DeploymentHistory,
    PlaygroundTarget,
    PublicationStatus,
    User,
)

PUBLIC_DEPLOYABLE_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)


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


__all__ = [
    "DeploymentRepository",
    "PUBLIC_DEPLOYABLE_STATUSES",
]
