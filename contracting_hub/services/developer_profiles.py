"""Service helpers for public developer-profile pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Session

from contracting_hub.database import session_scope
from contracting_hub.models import Profile, PublicationStatus
from contracting_hub.repositories import AuthRepository, ContractHighlightRecord, ContractRepository
from contracting_hub.services.auth import AuthServiceError, normalize_username
from contracting_hub.services.developer_kpis import (
    DeveloperKPIAggregate,
    build_developer_activity_window_start,
    get_developer_kpi_snapshot,
    normalize_developer_activity_window_days,
)


@dataclass(frozen=True)
class PublicDeveloperContractSummary:
    """Public authored-contract content rendered on one developer profile."""

    slug: str
    contract_name: str
    display_name: str
    short_summary: str
    status: PublicationStatus
    featured: bool
    semantic_version: str | None
    primary_category_name: str | None
    category_names: tuple[str, ...]
    tag_names: tuple[str, ...]
    updated_at: datetime
    published_at: datetime | None
    star_count: int
    rating_count: int
    average_rating: float | None
    deployment_count: int


@dataclass(frozen=True)
class PublicDeveloperProfileSnapshot:
    """Public developer identity, KPI, and authored-contract snapshot."""

    found: bool
    username: str | None
    display_name: str
    bio: str | None
    avatar_path: str | None
    website_url: str | None
    github_url: str | None
    xian_profile_url: str | None
    published_contract_count: int
    total_stars_received: int
    weighted_average_rating: float | None
    total_rating_count: int
    total_deployment_count: int
    recent_publish_count: int
    recent_stars_received: int
    recent_rating_count: int
    recent_deployment_count: int
    recent_activity_count: int
    activity_window_days: int
    activity_since: datetime
    authored_contracts: tuple[PublicDeveloperContractSummary, ...]


def normalize_public_developer_username(username: str | None) -> str | None:
    """Normalize one public developer username from a route param or link target."""
    if username is None:
        return None
    try:
        return normalize_username(username.strip().lstrip("@"))
    except AuthServiceError:
        return None


def build_empty_public_developer_profile_snapshot(
    *,
    username: str | None = None,
    activity_window_days: int | None = None,
) -> PublicDeveloperProfileSnapshot:
    """Return a stable empty snapshot for unknown developers or cold starts."""
    resolved_window_days = normalize_developer_activity_window_days(activity_window_days)
    normalized_username = normalize_public_developer_username(username)
    return PublicDeveloperProfileSnapshot(
        found=False,
        username=normalized_username,
        display_name="Developer profile",
        bio=None,
        avatar_path=None,
        website_url=None,
        github_url=None,
        xian_profile_url=None,
        published_contract_count=0,
        total_stars_received=0,
        weighted_average_rating=None,
        total_rating_count=0,
        total_deployment_count=0,
        recent_publish_count=0,
        recent_stars_received=0,
        recent_rating_count=0,
        recent_deployment_count=0,
        recent_activity_count=0,
        activity_window_days=resolved_window_days,
        activity_since=build_developer_activity_window_start(window_days=resolved_window_days),
        authored_contracts=(),
    )


def load_public_developer_profile_snapshot(
    *,
    session: Session,
    username: str | None,
    activity_window_days: int | None = None,
    now: datetime | None = None,
) -> PublicDeveloperProfileSnapshot:
    """Load one public developer profile and their public authored contracts."""
    normalized_username = normalize_public_developer_username(username)
    resolved_window_days = normalize_developer_activity_window_days(activity_window_days)
    if normalized_username is None:
        return build_empty_public_developer_profile_snapshot(
            activity_window_days=resolved_window_days
        )

    repository = AuthRepository(session)
    profile = repository.get_profile_by_username(normalized_username)
    if profile is None:
        return build_empty_public_developer_profile_snapshot(
            username=normalized_username,
            activity_window_days=resolved_window_days,
        )

    kpi_snapshot = get_developer_kpi_snapshot(
        session=session,
        username=normalized_username,
        activity_window_days=resolved_window_days,
        now=now,
    ) or _build_zero_kpi_aggregate(profile, activity_window_days=resolved_window_days, now=now)
    authored_contracts = tuple(
        _build_public_developer_contract_summary(record)
        for record in ContractRepository(session).list_authored_contract_highlights(
            author_user_id=profile.user_id
        )
    )

    return PublicDeveloperProfileSnapshot(
        found=True,
        username=profile.username,
        display_name=profile.display_name or profile.username,
        bio=profile.bio,
        avatar_path=profile.avatar_path,
        website_url=profile.website_url,
        github_url=profile.github_url,
        xian_profile_url=profile.xian_profile_url,
        published_contract_count=kpi_snapshot.published_contract_count,
        total_stars_received=kpi_snapshot.total_stars_received,
        weighted_average_rating=kpi_snapshot.weighted_average_rating,
        total_rating_count=kpi_snapshot.total_rating_count,
        total_deployment_count=kpi_snapshot.total_deployment_count,
        recent_publish_count=kpi_snapshot.recent_publish_count,
        recent_stars_received=kpi_snapshot.recent_stars_received,
        recent_rating_count=kpi_snapshot.recent_rating_count,
        recent_deployment_count=kpi_snapshot.recent_deployment_count,
        recent_activity_count=kpi_snapshot.recent_activity_count,
        activity_window_days=kpi_snapshot.activity_window_days,
        activity_since=kpi_snapshot.activity_since,
        authored_contracts=authored_contracts,
    )


def load_public_developer_profile_snapshot_safe(
    *,
    username: str | None,
    activity_window_days: int | None = None,
    now: datetime | None = None,
) -> PublicDeveloperProfileSnapshot:
    """Load a public developer profile while tolerating an unmigrated database."""
    normalized_username = normalize_public_developer_username(username)
    resolved_window_days = normalize_developer_activity_window_days(activity_window_days)
    try:
        with session_scope() as session:
            return load_public_developer_profile_snapshot(
                session=session,
                username=normalized_username,
                activity_window_days=resolved_window_days,
                now=now,
            )
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_public_developer_profile_snapshot(
            username=normalized_username,
            activity_window_days=resolved_window_days,
        )


def _build_zero_kpi_aggregate(
    profile: Profile,
    *,
    activity_window_days: int,
    now: datetime | None,
) -> DeveloperKPIAggregate:
    activity_since = build_developer_activity_window_start(
        window_days=activity_window_days,
        now=now,
    )
    return DeveloperKPIAggregate(
        user_id=profile.user_id,
        username=profile.username,
        display_name=profile.display_name,
        avatar_path=profile.avatar_path,
        published_contract_count=0,
        total_stars_received=0,
        weighted_average_rating=None,
        total_rating_count=0,
        total_deployment_count=0,
        recent_published_contract_count=0,
        recent_publish_count=0,
        recent_stars_received=0,
        recent_weighted_average_rating=None,
        recent_rating_count=0,
        recent_deployment_count=0,
        activity_window_days=activity_window_days,
        activity_since=activity_since,
    )


def _build_public_developer_contract_summary(
    record: ContractHighlightRecord,
) -> PublicDeveloperContractSummary:
    contract = record.contract
    categories = tuple(link.category.name for link in _sorted_contract_category_links(contract))
    latest_version = contract.latest_published_version
    return PublicDeveloperContractSummary(
        slug=contract.slug,
        contract_name=contract.contract_name,
        display_name=contract.display_name,
        short_summary=contract.short_summary,
        status=contract.status,
        featured=contract.featured,
        semantic_version=latest_version.semantic_version if latest_version is not None else None,
        primary_category_name=_build_primary_category_name(contract),
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
    )


def _sorted_contract_category_links(contract) -> tuple[object, ...]:
    return tuple(
        sorted(
            contract.category_links,
            key=lambda link: (
                link.sort_order,
                link.category.sort_order,
                link.category.name.lower(),
                link.category.slug,
            ),
        )
    )


def _build_primary_category_name(contract) -> str | None:
    ordered_categories = _sorted_contract_category_links(contract)
    category_names = tuple(link.category.name for link in ordered_categories)
    return next(
        (link.category.name for link in ordered_categories if link.is_primary),
        category_names[0] if category_names else None,
    )


def _coerce_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "PublicDeveloperContractSummary",
    "PublicDeveloperProfileSnapshot",
    "build_empty_public_developer_profile_snapshot",
    "load_public_developer_profile_snapshot",
    "load_public_developer_profile_snapshot_safe",
    "normalize_public_developer_username",
]
