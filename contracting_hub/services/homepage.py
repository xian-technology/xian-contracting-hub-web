"""Service helpers for the public homepage contract collections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Session

from contracting_hub.database import session_scope
from contracting_hub.models import PublicationStatus
from contracting_hub.repositories import ContractHighlightRecord, ContractRepository

DEFAULT_HOME_PAGE_SECTION_LIMIT = 4


@dataclass(frozen=True)
class HomePageContractSummary:
    """Pure data summary rendered by the public homepage."""

    slug: str
    contract_name: str
    display_name: str
    short_summary: str
    status: PublicationStatus
    featured: bool
    semantic_version: str | None
    author_name: str | None
    primary_category_name: str | None
    category_names: tuple[str, ...]
    tag_names: tuple[str, ...]
    updated_at: datetime
    published_at: datetime | None
    star_count: int
    rating_count: int
    average_rating: float | None
    deployment_count: int
    latest_deployment_at: datetime | None


@dataclass(frozen=True)
class HomePageSnapshot:
    """Published-only contract collections rendered on the landing page."""

    featured_contracts: tuple[HomePageContractSummary, ...]
    trending_contracts: tuple[HomePageContractSummary, ...]
    recently_updated_contracts: tuple[HomePageContractSummary, ...]
    recently_deployed_contracts: tuple[HomePageContractSummary, ...]


def normalize_home_page_section_limit(limit: int | None) -> int:
    """Validate and normalize one homepage section size limit."""
    if limit is None:
        return DEFAULT_HOME_PAGE_SECTION_LIMIT
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("Homepage section limit must be a positive integer.")
    return limit


def build_empty_home_page_snapshot() -> HomePageSnapshot:
    """Return a stable empty snapshot for first-run or fallback rendering."""
    return HomePageSnapshot(
        featured_contracts=(),
        trending_contracts=(),
        recently_updated_contracts=(),
        recently_deployed_contracts=(),
    )


def load_public_home_page_snapshot(
    *,
    session: Session,
    limit: int | None = None,
) -> HomePageSnapshot:
    """Load all published homepage sections from the repository layer."""
    resolved_limit = normalize_home_page_section_limit(limit)
    repository = ContractRepository(session)
    return HomePageSnapshot(
        featured_contracts=tuple(
            _build_home_page_contract_summary(record)
            for record in repository.list_featured_contract_highlights(limit=resolved_limit)
        ),
        trending_contracts=tuple(
            _build_home_page_contract_summary(record)
            for record in repository.list_trending_contract_highlights(limit=resolved_limit)
        ),
        recently_updated_contracts=tuple(
            _build_home_page_contract_summary(record)
            for record in repository.list_recently_updated_contract_highlights(limit=resolved_limit)
        ),
        recently_deployed_contracts=tuple(
            _build_home_page_contract_summary(record)
            for record in repository.list_recently_deployed_contract_highlights(
                limit=resolved_limit
            )
        ),
    )


def load_public_home_page_snapshot_safe(
    *,
    limit: int | None = None,
) -> HomePageSnapshot:
    """Load homepage data while tolerating an unmigrated or missing local database."""
    resolved_limit = normalize_home_page_section_limit(limit)
    try:
        with session_scope() as session:
            return load_public_home_page_snapshot(session=session, limit=resolved_limit)
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_home_page_snapshot()


def _build_home_page_contract_summary(
    record: ContractHighlightRecord,
) -> HomePageContractSummary:
    contract = record.contract
    categories = tuple(link.category.name for link in contract.category_links)
    primary_category_name = next(
        (
            link.category.name
            for link in sorted(contract.category_links, key=lambda current: current.sort_order)
            if link.is_primary
        ),
        categories[0] if categories else None,
    )
    latest_version = contract.latest_published_version
    author_name = contract.author_label
    if contract.author is not None and contract.author.profile is not None:
        author_name = contract.author.profile.display_name or contract.author.profile.username

    return HomePageContractSummary(
        slug=contract.slug,
        contract_name=contract.contract_name,
        display_name=contract.display_name,
        short_summary=contract.short_summary,
        status=contract.status,
        featured=contract.featured,
        semantic_version=latest_version.semantic_version if latest_version is not None else None,
        author_name=author_name,
        primary_category_name=primary_category_name,
        category_names=categories,
        tag_names=tuple(contract.tags),
        updated_at=_coerce_utc_datetime(contract.updated_at),
        published_at=(
            _coerce_utc_datetime(latest_version.published_at)
            if latest_version is not None and latest_version.published_at is not None
            else None
        ),
        star_count=record.star_count,
        rating_count=record.rating_count,
        average_rating=record.average_rating,
        deployment_count=record.deployment_count,
        latest_deployment_at=_coerce_utc_datetime(record.latest_deployment_at),
    )


def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "DEFAULT_HOME_PAGE_SECTION_LIMIT",
    "HomePageContractSummary",
    "HomePageSnapshot",
    "build_empty_home_page_snapshot",
    "load_public_home_page_snapshot",
    "load_public_home_page_snapshot_safe",
    "normalize_home_page_section_limit",
]
