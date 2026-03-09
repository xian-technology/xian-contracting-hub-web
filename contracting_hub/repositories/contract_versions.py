"""Persistence helpers for contract version write workflows."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import Contract, ContractVersion, PublicationStatus

PUBLIC_VISIBLE_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)


class ContractVersionRepository:
    """Persistence-oriented helpers for contract version creation flows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_contract_by_slug(self, slug: str) -> Contract | None:
        """Return the contract identified by its stable slug."""
        statement = select(Contract).where(Contract.slug == slug)
        return self._session.exec(statement).first()

    def get_contract_version(
        self,
        contract_id: int,
        semantic_version: str,
    ) -> ContractVersion | None:
        """Return a specific version row for the given contract."""
        statement = (
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract_id)
            .where(ContractVersion.semantic_version == semantic_version)
        )
        return self._session.exec(statement).first()

    def get_latest_contract_version(self, contract_id: int) -> ContractVersion | None:
        """Return the most recently created version row for a contract."""
        statement = (
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract_id)
            .order_by(ContractVersion.created_at.desc(), ContractVersion.id.desc())
        )
        return self._session.exec(statement).first()

    def get_version_by_slug(
        self,
        contract_slug: str,
        *,
        semantic_version: str | None = None,
        include_unpublished: bool = False,
    ) -> ContractVersion | None:
        """Return a contract version row plus its immediate comparison context."""
        statement = (
            select(ContractVersion)
            .join(Contract, Contract.id == ContractVersion.contract_id)
            .options(
                selectinload(ContractVersion.contract),
                selectinload(ContractVersion.previous_version),
            )
            .where(Contract.slug == contract_slug)
        )
        if semantic_version is not None:
            statement = statement.where(ContractVersion.semantic_version == semantic_version)
        if not include_unpublished:
            statement = statement.where(Contract.status.in_(PUBLIC_VISIBLE_STATUSES))
            statement = statement.where(Contract.latest_published_version_id.is_not(None))
            statement = statement.where(ContractVersion.status.in_(PUBLIC_VISIBLE_STATUSES))

        statement = statement.order_by(*_version_ordering_clause())
        return self._session.exec(statement).first()

    def add_contract_version(self, version: ContractVersion) -> ContractVersion:
        """Stage a newly created version row and assign its primary key."""
        self._session.add(version)
        self._session.flush()
        return version


def _version_ordering_clause() -> tuple[sa.ColumnElement[object], ...]:
    return (
        sa.case((ContractVersion.published_at.is_(None), 1), else_=0).asc(),
        ContractVersion.published_at.desc(),
        ContractVersion.created_at.desc(),
        ContractVersion.id.desc(),
    )


__all__ = ["ContractVersionRepository", "PUBLIC_VISIBLE_STATUSES"]
