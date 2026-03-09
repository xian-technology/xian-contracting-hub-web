"""Service helpers for the public contract detail header."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Session

from contracting_hub.database import session_scope
from contracting_hub.models import ContractNetwork, PublicationStatus
from contracting_hub.repositories import ContractRepository, RatingRepository, StarRepository


@dataclass(frozen=True)
class ContractDetailAuthorSummary:
    """Pure author summary rendered inside the public contract header."""

    display_name: str
    username: str | None
    bio: str | None
    website_url: str | None
    github_url: str | None
    xian_profile_url: str | None


@dataclass(frozen=True)
class ContractDetailSnapshot:
    """Header-ready public contract detail data."""

    found: bool
    slug: str | None
    display_name: str
    contract_name: str
    short_summary: str
    long_description: str
    contract_status: PublicationStatus | None
    featured: bool
    network: ContractNetwork | None
    license_name: str | None
    documentation_url: str | None
    source_repository_url: str | None
    author: ContractDetailAuthorSummary
    primary_category_name: str | None
    category_names: tuple[str, ...]
    tag_names: tuple[str, ...]
    selected_version: str | None
    selected_version_status: PublicationStatus | None
    selected_version_source_code: str
    selected_version_published_at: datetime | None
    updated_at: datetime | None
    star_count: int
    rating_count: int
    average_rating: float | None


def normalize_contract_detail_slug(slug: str | None) -> str | None:
    """Normalize one public contract-detail slug from route params."""
    if slug is None:
        return None
    normalized = slug.strip().lower()
    return normalized or None


def build_empty_contract_detail_snapshot(*, slug: str | None = None) -> ContractDetailSnapshot:
    """Return a stable empty snapshot for loading failures or unknown slugs."""
    return ContractDetailSnapshot(
        found=False,
        slug=normalize_contract_detail_slug(slug),
        display_name="",
        contract_name="",
        short_summary="",
        long_description="",
        contract_status=None,
        featured=False,
        network=None,
        license_name=None,
        documentation_url=None,
        source_repository_url=None,
        author=ContractDetailAuthorSummary(
            display_name="Curated entry",
            username=None,
            bio=None,
            website_url=None,
            github_url=None,
            xian_profile_url=None,
        ),
        primary_category_name=None,
        category_names=(),
        tag_names=(),
        selected_version=None,
        selected_version_status=None,
        selected_version_source_code="",
        selected_version_published_at=None,
        updated_at=None,
        star_count=0,
        rating_count=0,
        average_rating=None,
    )


def load_public_contract_detail_snapshot(
    *,
    session: Session,
    slug: str | None,
) -> ContractDetailSnapshot:
    """Load one published contract into a header-ready detail snapshot."""
    normalized_slug = normalize_contract_detail_slug(slug)
    if normalized_slug is None:
        return build_empty_contract_detail_snapshot()

    repository = ContractRepository(session)
    detail = repository.get_contract_detail(normalized_slug)
    if detail is None:
        return build_empty_contract_detail_snapshot(slug=normalized_slug)

    contract = detail.contract
    contract_id = contract.id
    if contract_id is None:
        return build_empty_contract_detail_snapshot(slug=normalized_slug)

    star_count = StarRepository(session).count_contract_stars(contract_id)
    rating_count, average_rating = RatingRepository(session).get_contract_rating_stats(contract_id)

    ordered_categories = tuple(
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
    category_names = tuple(link.category.name for link in ordered_categories)
    primary_category_name = next(
        (link.category.name for link in ordered_categories if link.is_primary),
        category_names[0] if category_names else None,
    )
    selected_version = contract.latest_published_version or (
        detail.versions[0] if detail.versions else None
    )

    return ContractDetailSnapshot(
        found=True,
        slug=contract.slug,
        display_name=contract.display_name,
        contract_name=contract.contract_name,
        short_summary=contract.short_summary,
        long_description=contract.long_description,
        contract_status=contract.status,
        featured=contract.featured,
        network=contract.network,
        license_name=contract.license_name,
        documentation_url=contract.documentation_url,
        source_repository_url=contract.source_repository_url,
        author=_build_contract_detail_author(contract),
        primary_category_name=primary_category_name,
        category_names=category_names,
        tag_names=tuple(contract.tags),
        selected_version=(
            selected_version.semantic_version if selected_version is not None else None
        ),
        selected_version_status=selected_version.status if selected_version is not None else None,
        selected_version_source_code=selected_version.source_code if selected_version else "",
        selected_version_published_at=_coerce_utc_datetime(
            selected_version.published_at if selected_version is not None else None
        ),
        updated_at=_coerce_utc_datetime(contract.updated_at),
        star_count=star_count,
        rating_count=rating_count,
        average_rating=average_rating,
    )


def load_public_contract_detail_snapshot_safe(
    *,
    slug: str | None,
) -> ContractDetailSnapshot:
    """Load one public contract detail while tolerating an unmigrated database."""
    normalized_slug = normalize_contract_detail_slug(slug)
    try:
        with session_scope() as session:
            return load_public_contract_detail_snapshot(session=session, slug=normalized_slug)
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_contract_detail_snapshot(slug=normalized_slug)


def _build_contract_detail_author(contract) -> ContractDetailAuthorSummary:
    profile = contract.author.profile if contract.author is not None else None
    display_name = contract.author_label or "Curated entry"
    username = None
    bio = None
    website_url = None
    github_url = None
    xian_profile_url = None

    if profile is not None:
        username = profile.username
        display_name = profile.display_name or profile.username
        bio = profile.bio
        website_url = profile.website_url
        github_url = profile.github_url
        xian_profile_url = profile.xian_profile_url

    return ContractDetailAuthorSummary(
        display_name=display_name,
        username=username,
        bio=bio,
        website_url=website_url,
        github_url=github_url,
        xian_profile_url=xian_profile_url,
    )


def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "ContractDetailAuthorSummary",
    "ContractDetailSnapshot",
    "build_empty_contract_detail_snapshot",
    "load_public_contract_detail_snapshot",
    "load_public_contract_detail_snapshot_safe",
    "normalize_contract_detail_slug",
]
