"""Persistence helpers for contract version write workflows."""

from __future__ import annotations

from sqlmodel import Session, select

from contracting_hub.models import Contract, ContractVersion


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

    def add_contract_version(self, version: ContractVersion) -> ContractVersion:
        """Stage a newly created version row and assign its primary key."""
        self._session.add(version)
        self._session.flush()
        return version


__all__ = ["ContractVersionRepository"]
