"""Admin contract-index helpers and lifecycle quick actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from enum import Enum
from urllib.parse import urlencode

import sqlalchemy as sa
from sqlmodel import Session, select

from contracting_hub.database import session_scope
from contracting_hub.models import AdminAuditLog, Contract, ContractCategoryLink, PublicationStatus
from contracting_hub.repositories import ContractRepository
from contracting_hub.services.auth import require_admin_user
from contracting_hub.services.contract_search import (
    normalize_contract_search_query,
    search_contract_catalog,
)
from contracting_hub.services.contract_versions import PUBLIC_VERSION_STATUSES
from contracting_hub.utils.meta import (
    ADMIN_CONTRACTS_ROUTE,
    build_admin_contract_edit_path,
    build_admin_contract_versions_path,
    build_contract_detail_path,
)


class AdminContractStatusFilter(str, Enum):
    """Supported admin contract-index status tabs."""

    ALL = "all"
    DRAFT = PublicationStatus.DRAFT.value
    PUBLISHED = PublicationStatus.PUBLISHED.value
    DEPRECATED = PublicationStatus.DEPRECATED.value
    ARCHIVED = PublicationStatus.ARCHIVED.value


class AdminContractFeaturedFilter(str, Enum):
    """Supported featured-state filters for the admin index."""

    ALL = "all"
    FEATURED = "featured"
    NOT_FEATURED = "not_featured"


class AdminContractActionErrorCode(str, Enum):
    """Stable error codes for admin quick-action failures."""

    CONTRACT_NOT_FOUND = "contract_not_found"
    PUBLISHABLE_VERSION_REQUIRED = "publishable_version_required"
    ALREADY_PUBLISHED = "already_published"
    ALREADY_ARCHIVED = "already_archived"
    DELETE_NOT_ALLOWED = "delete_not_allowed"


class AdminContractActionError(ValueError):
    """Stable admin contract action error."""

    def __init__(self, code: AdminContractActionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AdminContractStatusTab:
    """One admin status-tab summary rendered above the index."""

    value: AdminContractStatusFilter
    label: str
    count: int
    is_active: bool
    href: str


@dataclass(frozen=True)
class AdminContractIndexEntry:
    """One admin-visible contract summary row."""

    slug: str
    display_name: str
    contract_name: str
    short_summary: str
    status: PublicationStatus
    featured: bool
    author_name: str
    primary_category_name: str | None
    category_names: tuple[str, ...]
    latest_public_version: str | None
    updated_at_label: str
    public_detail_href: str | None
    edit_href: str
    versions_href: str
    can_publish: bool
    can_archive: bool
    can_delete: bool
    action_hint: str


@dataclass(frozen=True)
class AdminContractIndexSnapshot:
    """Admin contract-index data plus normalized filter state."""

    results: tuple[AdminContractIndexEntry, ...]
    query: str
    status_filter: AdminContractStatusFilter
    featured_filter: AdminContractFeaturedFilter
    status_tabs: tuple[AdminContractStatusTab, ...]
    total_results: int


def normalize_admin_contract_status_filter(
    status_filter: AdminContractStatusFilter | PublicationStatus | str | None,
) -> AdminContractStatusFilter:
    """Normalize one admin status-filter input."""
    if status_filter is None:
        return AdminContractStatusFilter.ALL
    if isinstance(status_filter, AdminContractStatusFilter):
        return status_filter
    if isinstance(status_filter, PublicationStatus):
        return AdminContractStatusFilter(status_filter.value)
    if isinstance(status_filter, str):
        normalized = status_filter.strip().lower()
        if not normalized:
            return AdminContractStatusFilter.ALL
        try:
            return AdminContractStatusFilter(normalized)
        except ValueError:
            return AdminContractStatusFilter.ALL
    return AdminContractStatusFilter.ALL


def normalize_admin_contract_featured_filter(
    featured_filter: AdminContractFeaturedFilter | str | None,
) -> AdminContractFeaturedFilter:
    """Normalize one admin featured-filter input."""
    if featured_filter is None:
        return AdminContractFeaturedFilter.ALL
    if isinstance(featured_filter, AdminContractFeaturedFilter):
        return featured_filter
    if isinstance(featured_filter, str):
        normalized = featured_filter.strip().lower()
        if not normalized:
            return AdminContractFeaturedFilter.ALL
        try:
            return AdminContractFeaturedFilter(normalized)
        except ValueError:
            return AdminContractFeaturedFilter.ALL
    return AdminContractFeaturedFilter.ALL


def build_admin_contracts_path(
    *,
    query: str | None = None,
    status_filter: AdminContractStatusFilter | PublicationStatus | str | None = None,
    featured_filter: AdminContractFeaturedFilter | str | None = None,
) -> str:
    """Build the canonical admin contract-index URL for the current filter state."""
    normalized_query = normalize_contract_search_query(query)
    normalized_status = normalize_admin_contract_status_filter(status_filter)
    normalized_featured = normalize_admin_contract_featured_filter(featured_filter)

    params: dict[str, str] = {}
    if normalized_query:
        params["query"] = normalized_query
    if normalized_status is not AdminContractStatusFilter.ALL:
        params["status"] = normalized_status.value
    if normalized_featured is not AdminContractFeaturedFilter.ALL:
        params["featured"] = normalized_featured.value

    if not params:
        return ADMIN_CONTRACTS_ROUTE
    return f"{ADMIN_CONTRACTS_ROUTE}?{urlencode(params)}"


def build_empty_admin_contract_index_snapshot(
    *,
    query: str | None = None,
    status_filter: AdminContractStatusFilter | PublicationStatus | str | None = None,
    featured_filter: AdminContractFeaturedFilter | str | None = None,
) -> AdminContractIndexSnapshot:
    """Return a stable empty admin snapshot."""
    normalized_query = normalize_contract_search_query(query)
    normalized_status = normalize_admin_contract_status_filter(status_filter)
    normalized_featured = normalize_admin_contract_featured_filter(featured_filter)
    return AdminContractIndexSnapshot(
        results=(),
        query=normalized_query,
        status_filter=normalized_status,
        featured_filter=normalized_featured,
        status_tabs=tuple(
            AdminContractStatusTab(
                value=status_value,
                label=_status_filter_label(status_value),
                count=0,
                is_active=status_value is normalized_status,
                href=build_admin_contracts_path(
                    query=normalized_query,
                    status_filter=status_value,
                    featured_filter=normalized_featured,
                ),
            )
            for status_value in _ordered_status_filters()
        ),
        total_results=0,
    )


def load_admin_contract_index_snapshot(
    *,
    session: Session,
    query: str | None = None,
    status_filter: AdminContractStatusFilter | PublicationStatus | str | None = None,
    featured_filter: AdminContractFeaturedFilter | str | None = None,
) -> AdminContractIndexSnapshot:
    """Load the admin contract index for the supplied filter state."""
    normalized_query = normalize_contract_search_query(query)
    normalized_status = normalize_admin_contract_status_filter(status_filter)
    normalized_featured = normalize_admin_contract_featured_filter(featured_filter)

    status_count_records = _load_filtered_contracts(
        session=session,
        query=normalized_query,
        status_filter=AdminContractStatusFilter.ALL,
        featured_filter=normalized_featured,
    )
    selected_records = _load_filtered_contracts(
        session=session,
        query=normalized_query,
        status_filter=normalized_status,
        featured_filter=normalized_featured,
    )
    status_counts = _count_contracts_by_status(status_count_records)

    return AdminContractIndexSnapshot(
        results=tuple(_build_index_entry(contract) for contract in selected_records),
        query=normalized_query,
        status_filter=normalized_status,
        featured_filter=normalized_featured,
        status_tabs=tuple(
            AdminContractStatusTab(
                value=status_value,
                label=_status_filter_label(status_value),
                count=status_counts.get(status_value, 0),
                is_active=status_value is normalized_status,
                href=build_admin_contracts_path(
                    query=normalized_query,
                    status_filter=status_value,
                    featured_filter=normalized_featured,
                ),
            )
            for status_value in _ordered_status_filters()
        ),
        total_results=len(selected_records),
    )


def load_admin_contract_index_snapshot_safe(
    *,
    query: str | None = None,
    status_filter: AdminContractStatusFilter | PublicationStatus | str | None = None,
    featured_filter: AdminContractFeaturedFilter | str | None = None,
) -> AdminContractIndexSnapshot:
    """Load the admin index while tolerating a missing or unmigrated database."""
    try:
        with session_scope() as session:
            return load_admin_contract_index_snapshot(
                session=session,
                query=query,
                status_filter=status_filter,
                featured_filter=featured_filter,
            )
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_admin_contract_index_snapshot(
            query=query,
            status_filter=status_filter,
            featured_filter=featured_filter,
        )


def publish_admin_contract(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
) -> Contract:
    """Promote a contract back into the public catalog when it has a public release."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    contract = _require_contract(session, contract_slug)

    if contract.status in PUBLIC_VERSION_STATUSES:
        raise AdminContractActionError(
            AdminContractActionErrorCode.ALREADY_PUBLISHED,
            "This contract is already publicly visible.",
        )
    if contract.latest_published_version_id is None:
        raise AdminContractActionError(
            AdminContractActionErrorCode.PUBLISHABLE_VERSION_REQUIRED,
            "Publish a contract version before making the contract public.",
        )

    previous_status = contract.status
    contract.status = PublicationStatus.PUBLISHED
    session.add(contract)
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="publish_contract",
            entity_type="contract",
            entity_id=contract.id,
            summary=f"Published contract {contract.slug}.",
            details={
                "slug": contract.slug,
                "previous_status": previous_status.value,
                "next_status": contract.status.value,
            },
        )
    )
    session.commit()
    session.refresh(contract)
    return contract


def archive_admin_contract(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
) -> Contract:
    """Archive a contract while keeping its immutable history intact."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    contract = _require_contract(session, contract_slug)

    if contract.status is PublicationStatus.ARCHIVED:
        raise AdminContractActionError(
            AdminContractActionErrorCode.ALREADY_ARCHIVED,
            "This contract is already archived.",
        )

    previous_status = contract.status
    contract.status = PublicationStatus.ARCHIVED
    session.add(contract)
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="archive_contract",
            entity_type="contract",
            entity_id=contract.id,
            summary=f"Archived contract {contract.slug}.",
            details={
                "slug": contract.slug,
                "previous_status": previous_status.value,
                "next_status": contract.status.value,
            },
        )
    )
    session.commit()
    session.refresh(contract)
    return contract


def delete_admin_contract(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
) -> None:
    """Delete a contract only when it has no public release history."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    contract = _require_contract(session, contract_slug)

    if (
        contract.status in PUBLIC_VERSION_STATUSES
        or contract.latest_published_version_id is not None
    ):
        raise AdminContractActionError(
            AdminContractActionErrorCode.DELETE_NOT_ALLOWED,
            "Only draft or archived contracts without a public release can be deleted.",
        )
    if contract.id is None:
        raise AdminContractActionError(
            AdminContractActionErrorCode.CONTRACT_NOT_FOUND,
            "The requested contract could not be found.",
        )

    contract_id = contract.id
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="delete_contract",
            entity_type="contract",
            entity_id=contract_id,
            summary=f"Deleted contract {contract.slug}.",
            details={
                "slug": contract.slug,
                "display_name": contract.display_name,
                "status": contract.status.value,
            },
        )
    )
    session.delete(contract)
    session.flush()
    try:
        session.execute(
            sa.text("DELETE FROM contract_search_index WHERE rowid = :contract_id"),
            {"contract_id": contract_id},
        )
    except sa.exc.OperationalError:
        pass
    session.commit()


def _load_filtered_contracts(
    *,
    session: Session,
    query: str,
    status_filter: AdminContractStatusFilter,
    featured_filter: AdminContractFeaturedFilter,
) -> list[Contract]:
    repository = ContractRepository(session)
    statuses = _status_filter_statuses(status_filter)
    featured = _featured_filter_value(featured_filter)
    if query:
        return [
            result.contract
            for result in search_contract_catalog(
                session=session,
                query=query,
                include_unpublished=True,
                statuses=statuses,
                featured=featured,
            )
        ]
    return repository.list_contracts(
        include_unpublished=True,
        statuses=statuses,
        featured=featured,
    )


def _status_filter_statuses(
    status_filter: AdminContractStatusFilter,
) -> tuple[PublicationStatus, ...] | None:
    if status_filter is AdminContractStatusFilter.ALL:
        return None
    return (PublicationStatus(status_filter.value),)


def _featured_filter_value(
    featured_filter: AdminContractFeaturedFilter,
) -> bool | None:
    if featured_filter is AdminContractFeaturedFilter.ALL:
        return None
    return featured_filter is AdminContractFeaturedFilter.FEATURED


def _ordered_status_filters() -> tuple[AdminContractStatusFilter, ...]:
    return (
        AdminContractStatusFilter.ALL,
        AdminContractStatusFilter.DRAFT,
        AdminContractStatusFilter.PUBLISHED,
        AdminContractStatusFilter.DEPRECATED,
        AdminContractStatusFilter.ARCHIVED,
    )


def _status_filter_label(status_filter: AdminContractStatusFilter) -> str:
    if status_filter is AdminContractStatusFilter.ALL:
        return "All"
    return status_filter.value.title()


def _count_contracts_by_status(contracts: list[Contract]) -> dict[AdminContractStatusFilter, int]:
    counts = {status_filter: 0 for status_filter in _ordered_status_filters()}
    counts[AdminContractStatusFilter.ALL] = len(contracts)
    for contract in contracts:
        counts[AdminContractStatusFilter(contract.status.value)] += 1
    return counts


def _build_index_entry(contract: Contract) -> AdminContractIndexEntry:
    ordered_categories = _sorted_contract_category_links(contract)
    category_names = tuple(
        link.category.name for link in ordered_categories if link.category is not None
    )
    latest_public_version = (
        contract.latest_published_version.semantic_version
        if contract.latest_published_version is not None
        else None
    )
    can_publish = (
        contract.status not in PUBLIC_VERSION_STATUSES
        and contract.latest_published_version_id is not None
    )
    can_archive = contract.status is not PublicationStatus.ARCHIVED
    can_delete = (
        contract.status in {PublicationStatus.DRAFT, PublicationStatus.ARCHIVED}
        and contract.latest_published_version_id is None
    )
    return AdminContractIndexEntry(
        slug=contract.slug,
        display_name=contract.display_name,
        contract_name=contract.contract_name,
        short_summary=contract.short_summary,
        status=contract.status,
        featured=contract.featured,
        author_name=_resolve_author_name(contract),
        primary_category_name=category_names[0] if category_names else None,
        category_names=category_names,
        latest_public_version=latest_public_version,
        updated_at_label=_format_admin_timestamp(contract.updated_at),
        public_detail_href=(
            build_contract_detail_path(contract.slug)
            if contract.status in PUBLIC_VERSION_STATUSES and latest_public_version is not None
            else None
        ),
        edit_href=build_admin_contract_edit_path(contract.slug),
        versions_href=build_admin_contract_versions_path(contract.slug),
        can_publish=can_publish,
        can_archive=can_archive,
        can_delete=can_delete,
        action_hint=_build_action_hint(
            status=contract.status,
            latest_public_version=latest_public_version,
            can_delete=can_delete,
        ),
    )


def _sorted_contract_category_links(contract: Contract) -> tuple[ContractCategoryLink, ...]:
    return tuple(
        sorted(
            contract.category_links,
            key=lambda link: (
                not link.is_primary,
                link.sort_order,
                link.category.sort_order if link.category is not None else 10**6,
                link.category.name if link.category is not None else "",
            ),
        )
    )


def _resolve_author_name(contract: Contract) -> str:
    if contract.author is not None and contract.author.profile is not None:
        profile = contract.author.profile
        if profile.display_name:
            return profile.display_name
        if profile.username:
            return f"@{profile.username}"
    if contract.author_label:
        return contract.author_label
    return "Unassigned"


def _build_action_hint(
    *,
    status: PublicationStatus,
    latest_public_version: str | None,
    can_delete: bool,
) -> str:
    if latest_public_version is None:
        if can_delete:
            return "Draft-only shell. Safe to delete if the entry is no longer needed."
        return "Add and publish a version before promoting this contract."
    if status is PublicationStatus.ARCHIVED:
        return "Archived from public discovery. Publish to restore visibility."
    if status is PublicationStatus.DEPRECATED:
        return "Deprecated contract kept available for historical compatibility."
    return f"Latest public version {latest_public_version} is available for detail-page review."


def _format_admin_timestamp(value) -> str:
    if value is None:
        return "No catalog updates yet"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d")


def _require_contract(session: Session, contract_slug: str) -> Contract:
    normalized_slug = str(contract_slug or "").strip().lower()
    if not normalized_slug:
        raise AdminContractActionError(
            AdminContractActionErrorCode.CONTRACT_NOT_FOUND,
            "The requested contract could not be found.",
        )

    statement = select(Contract).where(Contract.slug == normalized_slug)
    contract = session.exec(statement).first()
    if contract is None:
        raise AdminContractActionError(
            AdminContractActionErrorCode.CONTRACT_NOT_FOUND,
            "The requested contract could not be found.",
        )
    return contract


__all__ = [
    "AdminContractActionError",
    "AdminContractActionErrorCode",
    "AdminContractFeaturedFilter",
    "AdminContractIndexEntry",
    "AdminContractIndexSnapshot",
    "AdminContractStatusFilter",
    "AdminContractStatusTab",
    "archive_admin_contract",
    "build_admin_contracts_path",
    "build_empty_admin_contract_index_snapshot",
    "delete_admin_contract",
    "load_admin_contract_index_snapshot",
    "load_admin_contract_index_snapshot_safe",
    "normalize_admin_contract_featured_filter",
    "normalize_admin_contract_status_filter",
    "publish_admin_contract",
]
