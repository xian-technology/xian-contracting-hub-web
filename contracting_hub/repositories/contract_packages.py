"""Persistence helpers for package release workflows."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import (
    ContractPackage,
    ContractPackageRelease,
    ContractPackageReleaseArtifact,
    ContractVersion,
)


class ContractPackageRepository:
    """Persistence-oriented helpers for package release flows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_package_by_slug(self, slug: str) -> ContractPackage | None:
        """Return a package by stable slug."""
        statement = select(ContractPackage).where(ContractPackage.slug == slug)
        return self._session.exec(statement).first()

    def get_package_release(
        self,
        package_id: int,
        semantic_version: str,
    ) -> ContractPackageRelease | None:
        """Return one package release by package and semantic version."""
        statement = (
            select(ContractPackageRelease)
            .where(ContractPackageRelease.package_id == package_id)
            .where(ContractPackageRelease.semantic_version == semantic_version)
        )
        return self._session.exec(statement).first()

    def get_package_release_by_id(self, release_id: int) -> ContractPackageRelease | None:
        """Return one package release by primary key."""
        statement = (
            select(ContractPackageRelease)
            .options(selectinload(ContractPackageRelease.package))
            .where(ContractPackageRelease.id == release_id)
        )
        return self._session.exec(statement).first()

    def get_package_release_detail(
        self,
        package_slug: str,
        *,
        semantic_version: str | None = None,
    ) -> ContractPackageRelease | None:
        """Return a release with package and artifacts eagerly loaded."""
        statement = (
            select(ContractPackageRelease)
            .join(ContractPackage, ContractPackage.id == ContractPackageRelease.package_id)
            .options(
                selectinload(ContractPackageRelease.package),
                selectinload(ContractPackageRelease.artifacts)
                .selectinload(ContractPackageReleaseArtifact.contract_version)
                .selectinload(ContractVersion.contract),
            )
            .where(ContractPackage.slug == package_slug)
        )
        if semantic_version is not None:
            statement = statement.where(ContractPackageRelease.semantic_version == semantic_version)
        statement = statement.order_by(*_release_ordering_clause())
        return self._session.exec(statement).first()

    def get_contract_version_by_id(self, contract_version_id: int) -> ContractVersion | None:
        """Return one immutable contract version by primary key."""
        statement = select(ContractVersion).where(ContractVersion.id == contract_version_id)
        return self._session.exec(statement).first()

    def add_package(self, package: ContractPackage) -> ContractPackage:
        """Stage a package and assign its primary key."""
        self._session.add(package)
        self._session.flush()
        return package

    def add_release(self, release: ContractPackageRelease) -> ContractPackageRelease:
        """Stage a package release and assign its primary key."""
        self._session.add(release)
        self._session.flush()
        return release

    def add_release_artifact(
        self,
        artifact: ContractPackageReleaseArtifact,
    ) -> ContractPackageReleaseArtifact:
        """Stage a package release artifact and assign its primary key."""
        self._session.add(artifact)
        self._session.flush()
        return artifact


def _release_ordering_clause() -> tuple[sa.ColumnElement[object], ...]:
    return (
        sa.case((ContractPackageRelease.published_at.is_(None), 1), else_=0).asc(),
        ContractPackageRelease.published_at.desc(),
        ContractPackageRelease.created_at.desc(),
        ContractPackageRelease.id.desc(),
    )


__all__ = ["ContractPackageRepository"]
