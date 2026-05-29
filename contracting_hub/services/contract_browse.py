"""Public browse-page helpers for the contract catalog."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import ceil
from urllib.parse import urlencode

import sqlalchemy as sa
from sqlmodel import Session

from contracting_hub.database import session_scope
from contracting_hub.repositories import ContractHighlightRecord, ContractRepository
from contracting_hub.services.contract_search import (
    normalize_contract_search_query,
    search_contract_catalog,
)
from contracting_hub.utils.meta import BROWSE_ROUTE

DEFAULT_CONTRACT_BROWSE_PAGE_SIZE = 9


class ContractBrowseSort(str, Enum):
    """Supported browse ordering values."""

    RELEVANCE = "relevance"
    FEATURED = "featured"
    NEWEST = "newest"
    RECENTLY_UPDATED = "recently_updated"
    MOST_STARRED = "most_starred"
    TOP_RATED = "top_rated"
    ALPHABETICAL = "alphabetical"


@dataclass(frozen=True)
class ContractBrowseFilterOption:
    """One category or tag option rendered in the browse filters."""

    value: str
    label: str
    count: int


@dataclass(frozen=True)
class ContractBrowseSummary:
    """Pure data summary rendered by the public browse page."""

    slug: str
    contract_name: str
    display_name: str
    short_summary: str
    featured: bool
    semantic_version: str | None
    author_name: str
    primary_category_name: str
    category_names: tuple[str, ...]
    tag_names: tuple[str, ...]
    updated_at: datetime
    published_at: datetime | None
    star_count: int
    rating_count: int
    average_rating: float | None


@dataclass(frozen=True)
class ContractBrowseSnapshot:
    """Browse-ready contract collection plus normalized filter state."""

    results: tuple[ContractBrowseSummary, ...]
    available_categories: tuple[ContractBrowseFilterOption, ...]
    available_tags: tuple[ContractBrowseFilterOption, ...]
    query: str
    category_slug: str | None
    tag: str | None
    sort: ContractBrowseSort
    current_page: int
    page_size: int
    total_results: int
    total_pages: int


def normalize_contract_browse_category_slug(category_slug: str | None) -> str | None:
    """Normalize one category slug from query params or forms."""
    if category_slug is None:
        return None
    normalized = category_slug.strip().lower()
    return normalized or None


def normalize_contract_browse_tag(tag: str | None) -> str | None:
    """Normalize one tag filter value from query params or forms."""
    if tag is None:
        return None
    normalized = " ".join(tag.split()).strip().lower()
    return normalized or None


def normalize_contract_browse_page(page: int | str | None) -> int:
    """Normalize one user-supplied browse-page number."""
    if page is None:
        return 1
    if isinstance(page, bool):
        return 1
    if isinstance(page, int):
        return page if page > 0 else 1
    if isinstance(page, str) and page.strip().isdigit():
        return max(int(page.strip()), 1)
    return 1


def normalize_contract_browse_sort(
    sort: ContractBrowseSort | str | None,
    *,
    has_query: bool = False,
) -> ContractBrowseSort:
    """Normalize browse sort input from URL params or form data."""
    if sort is None:
        return ContractBrowseSort.RELEVANCE if has_query else ContractBrowseSort.FEATURED
    if isinstance(sort, ContractBrowseSort):
        return sort
    if isinstance(sort, str):
        normalized_sort = sort.strip().lower()
        if normalized_sort:
            try:
                return ContractBrowseSort(normalized_sort)
            except ValueError:
                pass
    return ContractBrowseSort.RELEVANCE if has_query else ContractBrowseSort.FEATURED


def build_empty_contract_browse_snapshot(
    *,
    query: str | None = None,
    category_slug: str | None = None,
    tag: str | None = None,
    sort: ContractBrowseSort | str | None = None,
    page: int | str | None = None,
    page_size: int = DEFAULT_CONTRACT_BROWSE_PAGE_SIZE,
) -> ContractBrowseSnapshot:
    """Return a stable empty browse snapshot for first-run or fallback rendering."""
    normalized_query = normalize_contract_search_query(query)
    return ContractBrowseSnapshot(
        results=(),
        available_categories=(),
        available_tags=(),
        query=normalized_query,
        category_slug=normalize_contract_browse_category_slug(category_slug),
        tag=normalize_contract_browse_tag(tag),
        sort=normalize_contract_browse_sort(sort, has_query=bool(normalized_query)),
        current_page=normalize_contract_browse_page(page),
        page_size=page_size,
        total_results=0,
        total_pages=1,
    )


def build_contract_browse_path(
    *,
    query: str | None = None,
    category_slug: str | None = None,
    tag: str | None = None,
    sort: ContractBrowseSort | str | None = None,
    page: int | str | None = None,
) -> str:
    """Build a canonical browse URL for the current public query state."""
    normalized_query = normalize_contract_search_query(query)
    normalized_category = normalize_contract_browse_category_slug(category_slug)
    normalized_tag = normalize_contract_browse_tag(tag)
    normalized_page = normalize_contract_browse_page(page)
    normalized_sort = normalize_contract_browse_sort(sort, has_query=bool(normalized_query))
    default_sort = normalize_contract_browse_sort(None, has_query=bool(normalized_query))

    params: dict[str, str] = {}
    if normalized_query:
        params["query"] = normalized_query
    if normalized_category is not None:
        params["category"] = normalized_category
    if normalized_tag is not None:
        params["tag"] = normalized_tag
    if normalized_sort is not default_sort:
        params["sort"] = normalized_sort.value
    if normalized_page > 1:
        params["page"] = str(normalized_page)

    if not params:
        return BROWSE_ROUTE
    return f"{BROWSE_ROUTE}?{urlencode(params)}"


def load_public_contract_browse_snapshot(
    *,
    session: Session,
    query: str | None = None,
    category_slug: str | None = None,
    tag: str | None = None,
    sort: ContractBrowseSort | str | None = None,
    page: int | str | None = None,
    page_size: int = DEFAULT_CONTRACT_BROWSE_PAGE_SIZE,
) -> ContractBrowseSnapshot:
    """Load the public browse page snapshot from repository and search services."""
    normalized_query = normalize_contract_search_query(query)
    normalized_category = normalize_contract_browse_category_slug(category_slug)
    normalized_tag = normalize_contract_browse_tag(tag)
    normalized_sort = normalize_contract_browse_sort(sort, has_query=bool(normalized_query))
    normalized_page = normalize_contract_browse_page(page)

    repository = ContractRepository(session)
    all_records = repository.list_recently_updated_contract_highlights(limit=None)
    filtered_records = list(all_records)
    search_order_by_contract_id: dict[int, int] | None = None

    if normalized_query:
        search_results = search_contract_catalog(session=session, query=normalized_query)
        search_order_by_contract_id = {
            result.contract.id: index
            for index, result in enumerate(search_results)
            if result.contract.id is not None
        }
        filtered_records = [
            record
            for record in filtered_records
            if record.contract.id is not None and record.contract.id in search_order_by_contract_id
        ]
        filtered_records.sort(
            key=lambda record: search_order_by_contract_id.get(record.contract.id or -1, 10**9)
        )

    if normalized_category is not None:
        filtered_records = [
            record
            for record in filtered_records
            if _record_matches_category(record, category_slug=normalized_category)
        ]
    if normalized_tag is not None:
        filtered_records = [
            record for record in filtered_records if _record_matches_tag(record, tag=normalized_tag)
        ]

    sorted_records = _sort_browse_records(
        filtered_records,
        sort=normalized_sort,
        search_order_by_contract_id=search_order_by_contract_id,
    )

    total_results = len(sorted_records)
    total_pages = max(1, ceil(total_results / page_size)) if total_results else 1
    current_page = min(normalized_page, total_pages)
    page_start = (current_page - 1) * page_size
    page_end = page_start + page_size

    return ContractBrowseSnapshot(
        results=tuple(
            _build_contract_browse_summary(record) for record in sorted_records[page_start:page_end]
        ),
        available_categories=_build_browse_category_options(all_records),
        available_tags=_build_browse_tag_options(all_records),
        query=normalized_query,
        category_slug=normalized_category,
        tag=normalized_tag,
        sort=normalized_sort,
        current_page=current_page,
        page_size=page_size,
        total_results=total_results,
        total_pages=total_pages,
    )


def load_public_contract_browse_snapshot_safe(
    *,
    query: str | None = None,
    category_slug: str | None = None,
    tag: str | None = None,
    sort: ContractBrowseSort | str | None = None,
    page: int | str | None = None,
    page_size: int = DEFAULT_CONTRACT_BROWSE_PAGE_SIZE,
) -> ContractBrowseSnapshot:
    """Load browse data while tolerating an unmigrated or missing local database."""
    try:
        with session_scope() as session:
            return load_public_contract_browse_snapshot(
                session=session,
                query=query,
                category_slug=category_slug,
                tag=tag,
                sort=sort,
                page=page,
                page_size=page_size,
            )
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_contract_browse_snapshot(
            query=query,
            category_slug=category_slug,
            tag=tag,
            sort=sort,
            page=page,
            page_size=page_size,
        )


def _record_matches_category(record: ContractHighlightRecord, *, category_slug: str) -> bool:
    return any(
        link.category.slug.lower() == category_slug for link in record.contract.category_links
    )


def _record_matches_tag(record: ContractHighlightRecord, *, tag: str) -> bool:
    return any(current_tag.strip().lower() == tag for current_tag in record.contract.tags)


def _sort_browse_records(
    records: list[ContractHighlightRecord],
    *,
    sort: ContractBrowseSort,
    search_order_by_contract_id: dict[int, int] | None,
) -> list[ContractHighlightRecord]:
    if sort is ContractBrowseSort.RELEVANCE and search_order_by_contract_id is not None:
        return records
    if sort is ContractBrowseSort.FEATURED:
        return sorted(records, key=_featured_sort_key)
    if sort is ContractBrowseSort.NEWEST:
        return sorted(records, key=_newest_sort_key)
    if sort is ContractBrowseSort.RECENTLY_UPDATED:
        return sorted(records, key=_recently_updated_sort_key)
    if sort is ContractBrowseSort.MOST_STARRED:
        return sorted(records, key=_most_starred_sort_key)
    if sort is ContractBrowseSort.TOP_RATED:
        return sorted(records, key=_top_rated_sort_key)
    if sort is ContractBrowseSort.ALPHABETICAL:
        return sorted(records, key=_alphabetical_sort_key)
    return records


def _featured_sort_key(record: ContractHighlightRecord) -> tuple[object, ...]:
    contract = record.contract
    return (
        not contract.featured,
        -_datetime_sort_value(contract.updated_at),
        -record.star_count,
        contract.display_name.lower(),
    )


def _newest_sort_key(record: ContractHighlightRecord) -> tuple[object, ...]:
    published_at = (
        record.contract.latest_published_version.published_at
        if record.contract.latest_published_version is not None
        else None
    )
    return (
        -_datetime_sort_value(published_at),
        -_datetime_sort_value(record.contract.updated_at),
        record.contract.display_name.lower(),
    )


def _recently_updated_sort_key(record: ContractHighlightRecord) -> tuple[object, ...]:
    return (
        -_datetime_sort_value(record.contract.updated_at),
        not record.contract.featured,
        record.contract.display_name.lower(),
    )


def _most_starred_sort_key(record: ContractHighlightRecord) -> tuple[object, ...]:
    return (
        -record.star_count,
        not record.contract.featured,
        -_datetime_sort_value(record.contract.updated_at),
        record.contract.display_name.lower(),
    )


def _top_rated_sort_key(record: ContractHighlightRecord) -> tuple[object, ...]:
    average_rating = record.average_rating or 0.0
    return (
        record.rating_count == 0,
        -average_rating,
        -record.rating_count,
        -record.star_count,
        -_datetime_sort_value(record.contract.updated_at),
        record.contract.display_name.lower(),
    )


def _alphabetical_sort_key(record: ContractHighlightRecord) -> tuple[object, ...]:
    return (
        record.contract.display_name.lower(),
        -_datetime_sort_value(record.contract.updated_at),
    )


def _build_browse_category_options(
    records: list[ContractHighlightRecord],
) -> tuple[ContractBrowseFilterOption, ...]:
    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}
    sort_orders: dict[str, int] = {}

    for record in records:
        seen: set[str] = set()
        for link in record.contract.category_links:
            slug = link.category.slug.lower()
            if slug in seen:
                continue
            seen.add(slug)
            counts[slug] += 1
            labels.setdefault(slug, link.category.name)
            sort_orders.setdefault(slug, link.category.sort_order)

    return tuple(
        ContractBrowseFilterOption(
            value=slug,
            label=labels[slug],
            count=counts[slug],
        )
        for slug in sorted(
            counts,
            key=lambda current_slug: (
                sort_orders[current_slug],
                labels[current_slug].lower(),
                current_slug,
            ),
        )
    )


def _build_browse_tag_options(
    records: list[ContractHighlightRecord],
) -> tuple[ContractBrowseFilterOption, ...]:
    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}

    for record in records:
        seen: set[str] = set()
        for current_tag in record.contract.tags:
            normalized_tag = normalize_contract_browse_tag(current_tag)
            if normalized_tag is None or normalized_tag in seen:
                continue
            seen.add(normalized_tag)
            counts[normalized_tag] += 1
            labels.setdefault(normalized_tag, current_tag.strip())

    return tuple(
        ContractBrowseFilterOption(
            value=tag,
            label=labels[tag],
            count=counts[tag],
        )
        for tag in sorted(
            counts,
            key=lambda current_tag: (
                -counts[current_tag],
                labels[current_tag].lower(),
                current_tag,
            ),
        )
    )


def _build_contract_browse_summary(record: ContractHighlightRecord) -> ContractBrowseSummary:
    contract = record.contract
    categories = tuple(link.category.name for link in contract.category_links)
    primary_category_name = next(
        (
            link.category.name
            for link in sorted(contract.category_links, key=lambda current: current.sort_order)
            if link.is_primary
        ),
        categories[0] if categories else "Uncategorized",
    )
    latest_version = contract.latest_published_version
    author_name = contract.author_label or "Curated entry"
    if contract.author is not None and contract.author.profile is not None:
        author_name = contract.author.profile.display_name or contract.author.profile.username

    return ContractBrowseSummary(
        slug=contract.slug,
        contract_name=contract.contract_name,
        display_name=contract.display_name,
        short_summary=contract.short_summary,
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
    )


def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _datetime_sort_value(value: datetime | None) -> float:
    coerced = _coerce_utc_datetime(value)
    if coerced is None:
        return 0.0
    return coerced.timestamp()


__all__ = [
    "ContractBrowseFilterOption",
    "ContractBrowseSnapshot",
    "ContractBrowseSort",
    "ContractBrowseSummary",
    "DEFAULT_CONTRACT_BROWSE_PAGE_SIZE",
    "build_contract_browse_path",
    "build_empty_contract_browse_snapshot",
    "load_public_contract_browse_snapshot",
    "load_public_contract_browse_snapshot_safe",
    "normalize_contract_browse_category_slug",
    "normalize_contract_browse_page",
    "normalize_contract_browse_sort",
    "normalize_contract_browse_tag",
]
