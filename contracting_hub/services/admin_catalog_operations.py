"""Admin services for catalog operations beyond per-contract editing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import timezone
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.database import session_scope
from contracting_hub.models import (
    AdminAuditLog,
    Category,
    Contract,
    ContractCategoryLink,
    Profile,
    User,
)
from contracting_hub.repositories import ContractRepository
from contracting_hub.services.auth import require_admin_user
from contracting_hub.services.contract_search import rebuild_contract_search_document
from contracting_hub.services.contract_versions import PUBLIC_VERSION_STATUSES
from contracting_hub.utils.meta import build_admin_contract_edit_path, build_contract_detail_path

MAX_CATEGORY_SLUG_LENGTH = 64
MAX_CATEGORY_NAME_LENGTH = 128
MAX_CATEGORY_DESCRIPTION_LENGTH = 512
MAX_AUDIT_LOG_ENTRIES = 18
CATEGORY_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


class AdminCatalogOperationsErrorCode(StrEnum):
    """Stable service failures surfaced to admin catalog callers."""

    CATEGORY_NOT_FOUND = "category_not_found"
    CONTRACT_NOT_FOUND = "contract_not_found"
    CATEGORY_DELETE_NOT_ALLOWED = "category_delete_not_allowed"
    DUPLICATE_CATEGORY_NAME = "duplicate_category_name"
    DUPLICATE_CATEGORY_SLUG = "duplicate_category_slug"
    FEATURED_CONTRACT_NOT_ALLOWED = "featured_contract_not_allowed"
    INVALID_CATEGORY_DESCRIPTION = "invalid_category_description"
    INVALID_CATEGORY_NAME = "invalid_category_name"
    INVALID_CATEGORY_SLUG = "invalid_category_slug"
    INVALID_CATEGORY_SORT_ORDER = "invalid_category_sort_order"


class AdminCatalogOperationsError(ValueError):
    """Structured service error for catalog-operations workflows."""

    def __init__(
        self,
        code: AdminCatalogOperationsErrorCode,
        message: str,
        *,
        field: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.details = details or {}

    def as_payload(self) -> dict[str, object]:
        """Serialize one service failure for UI or API responses."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True)
class AdminCategoryManagementEntry:
    """One category row rendered in the admin operations workspace."""

    category_id: int
    slug: str
    name: str
    description: str | None
    sort_order: int
    contract_count: int
    updated_at_label: str
    can_delete: bool


@dataclass(frozen=True)
class AdminFeaturedContractEntry:
    """One public contract available for featured-content curation."""

    contract_id: int
    slug: str
    display_name: str
    contract_name: str
    author_name: str
    categories_label: str
    latest_public_version: str
    status_label: str
    status: str
    is_featured: bool
    updated_at_label: str
    public_detail_href: str | None
    edit_href: str


@dataclass(frozen=True)
class AdminAuditLogInspectionEntry:
    """One immutable audit-log entry rendered in the admin workspace."""

    audit_log_id: int
    created_at_label: str
    admin_label: str
    action: str
    action_label: str
    entity_type_label: str
    summary: str
    details_pretty_json: str
    has_details: bool


@dataclass(frozen=True)
class AdminCatalogOperationsSnapshot:
    """Loaded data required by the admin catalog-operations page."""

    categories: tuple[AdminCategoryManagementEntry, ...]
    featured_contracts: tuple[AdminFeaturedContractEntry, ...]
    audit_logs: tuple[AdminAuditLogInspectionEntry, ...]


def build_empty_admin_catalog_operations_snapshot() -> AdminCatalogOperationsSnapshot:
    """Return a stable empty admin operations snapshot."""
    return AdminCatalogOperationsSnapshot(
        categories=(),
        featured_contracts=(),
        audit_logs=(),
    )


def load_admin_catalog_operations_snapshot(*, session: Session) -> AdminCatalogOperationsSnapshot:
    """Load categories, featured-candidate contracts, and audit logs."""
    return AdminCatalogOperationsSnapshot(
        categories=_load_category_entries(session),
        featured_contracts=_load_featured_contract_entries(session),
        audit_logs=_load_audit_log_entries(session),
    )


def load_admin_catalog_operations_snapshot_safe() -> AdminCatalogOperationsSnapshot:
    """Load admin operations data while tolerating an unmigrated database."""
    try:
        with session_scope() as session:
            return load_admin_catalog_operations_snapshot(session=session)
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_admin_catalog_operations_snapshot()


def create_admin_category(
    *,
    session: Session,
    session_token: str | None,
    slug: str,
    name: str,
    description: str | None = None,
    sort_order: int | str | None = None,
) -> Category:
    """Create one category for browse taxonomy management."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    normalized_slug = normalize_admin_category_slug(slug)
    normalized_name = normalize_admin_category_name(name)
    normalized_description = normalize_admin_category_description(description)
    normalized_sort_order = normalize_admin_category_sort_order(sort_order)
    _ensure_unique_category_values(
        session=session,
        slug=normalized_slug,
        name=normalized_name,
    )

    category = Category(
        slug=normalized_slug,
        name=normalized_name,
        description=normalized_description,
        sort_order=normalized_sort_order,
    )
    session.add(category)
    try:
        session.flush()
    except IntegrityError as error:
        raise _category_integrity_error(normalized_slug, normalized_name) from error

    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="create_category",
            entity_type="category",
            entity_id=category.id,
            summary=f"Created category {category.slug}.",
            details={
                "slug": category.slug,
                "name": category.name,
                "sort_order": category.sort_order,
            },
        )
    )
    session.commit()
    session.refresh(category)
    return category


def update_admin_category(
    *,
    session: Session,
    session_token: str | None,
    category_id: int,
    slug: str,
    name: str,
    description: str | None = None,
    sort_order: int | str | None = None,
) -> Category:
    """Update one category and refresh linked search documents."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    category = _require_category(session=session, category_id=category_id)
    normalized_slug = normalize_admin_category_slug(slug)
    normalized_name = normalize_admin_category_name(name)
    normalized_description = normalize_admin_category_description(description)
    normalized_sort_order = normalize_admin_category_sort_order(sort_order)
    _ensure_unique_category_values(
        session=session,
        slug=normalized_slug,
        name=normalized_name,
        exclude_category_id=category.id,
    )

    previous_slug = category.slug
    previous_name = category.name
    previous_description = category.description
    previous_sort_order = category.sort_order
    linked_contract_ids = _linked_contract_ids_for_category(
        session=session,
        category_id=category.id,
    )

    category.slug = normalized_slug
    category.name = normalized_name
    category.description = normalized_description
    category.sort_order = normalized_sort_order
    session.add(category)
    try:
        session.flush()
    except IntegrityError as error:
        raise _category_integrity_error(normalized_slug, normalized_name) from error

    for contract_id in linked_contract_ids:
        rebuild_contract_search_document(session, contract_id=contract_id)

    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="update_category",
            entity_type="category",
            entity_id=category.id,
            summary=f"Updated category {category.slug}.",
            details={
                "previous_slug": previous_slug,
                "next_slug": category.slug,
                "previous_name": previous_name,
                "next_name": category.name,
                "previous_description": previous_description,
                "next_description": category.description,
                "previous_sort_order": previous_sort_order,
                "next_sort_order": category.sort_order,
                "linked_contract_ids": linked_contract_ids,
            },
        )
    )
    session.commit()
    session.refresh(category)
    return category


def delete_admin_category(
    *,
    session: Session,
    session_token: str | None,
    category_id: int,
) -> None:
    """Delete one category when it is not linked to any contract."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    category = _require_category(session=session, category_id=category_id)
    linked_contract_ids = _linked_contract_ids_for_category(
        session=session,
        category_id=category.id,
    )
    if linked_contract_ids:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.CATEGORY_DELETE_NOT_ALLOWED,
            "Remove contracts from this category before deleting it.",
            field="category",
            details={
                "category_id": category.id,
                "contract_count": len(linked_contract_ids),
            },
        )

    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="delete_category",
            entity_type="category",
            entity_id=category.id,
            summary=f"Deleted category {category.slug}.",
            details={
                "slug": category.slug,
                "name": category.name,
                "sort_order": category.sort_order,
            },
        )
    )
    session.delete(category)
    session.commit()


def set_admin_contract_featured_state(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
    featured: bool,
) -> Contract:
    """Toggle whether a public contract appears in featured catalog placements."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    contract = _require_contract(session=session, contract_slug=contract_slug)
    if featured and (
        contract.status not in PUBLIC_VERSION_STATUSES
        or contract.latest_published_version_id is None
    ):
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.FEATURED_CONTRACT_NOT_ALLOWED,
            "Only contracts with a public release can be featured.",
            field="contract",
            details={"contract_slug": contract.slug},
        )

    previous_featured = contract.featured
    if previous_featured is featured:
        return contract

    contract.featured = featured
    session.add(contract)
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="set_contract_featured_state",
            entity_type="contract",
            entity_id=contract.id,
            summary=(
                f"Marked contract {contract.slug} as featured."
                if featured
                else f"Removed contract {contract.slug} from featured content."
            ),
            details={
                "slug": contract.slug,
                "previous_featured": previous_featured,
                "next_featured": featured,
            },
        )
    )
    session.commit()
    session.refresh(contract)
    return contract


def normalize_admin_category_slug(slug: str) -> str:
    """Normalize and validate a category slug."""
    normalized_slug = str(slug or "").strip().lower()
    if not normalized_slug or len(normalized_slug) > MAX_CATEGORY_SLUG_LENGTH:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_SLUG,
            "Category slugs must be 1-64 characters.",
            field="slug",
        )
    if not CATEGORY_SLUG_PATTERN.fullmatch(normalized_slug):
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_SLUG,
            "Use lowercase letters, numbers, hyphens, or underscores for category slugs.",
            field="slug",
        )
    return normalized_slug


def normalize_admin_category_name(name: str) -> str:
    """Normalize and validate a category display name."""
    normalized_name = " ".join(str(name or "").split())
    if not normalized_name:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_NAME,
            "Enter a category name.",
            field="name",
        )
    if len(normalized_name) > MAX_CATEGORY_NAME_LENGTH:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_NAME,
            "Category names must be 128 characters or fewer.",
            field="name",
        )
    return normalized_name


def normalize_admin_category_description(description: str | None) -> str | None:
    """Normalize the optional category description field."""
    normalized_description = str(description or "").strip() or None
    if (
        normalized_description is not None
        and len(normalized_description) > MAX_CATEGORY_DESCRIPTION_LENGTH
    ):
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_DESCRIPTION,
            "Category descriptions must be 512 characters or fewer.",
            field="description",
        )
    return normalized_description


def normalize_admin_category_sort_order(sort_order: int | str | None) -> int:
    """Normalize the optional category sort-order field."""
    if sort_order is None:
        return 0
    normalized_text = str(sort_order).strip()
    if not normalized_text:
        return 0
    try:
        return int(normalized_text)
    except ValueError as error:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.INVALID_CATEGORY_SORT_ORDER,
            "Category sort order must be a whole number.",
            field="sort_order",
        ) from error


def _load_category_entries(session: Session) -> tuple[AdminCategoryManagementEntry, ...]:
    statement = (
        select(Category, sa.func.count(ContractCategoryLink.contract_id))
        .outerjoin(ContractCategoryLink, ContractCategoryLink.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.sort_order.asc(), Category.name.asc())
    )
    return tuple(
        AdminCategoryManagementEntry(
            category_id=category.id,
            slug=category.slug,
            name=category.name,
            description=category.description,
            sort_order=category.sort_order,
            contract_count=contract_count,
            updated_at_label=_format_admin_timestamp(category.updated_at),
            can_delete=contract_count == 0,
        )
        for category, contract_count in session.exec(statement).all()
        if category.id is not None
    )


def _load_featured_contract_entries(session: Session) -> tuple[AdminFeaturedContractEntry, ...]:
    repository = ContractRepository(session)
    contracts = repository.list_contracts(
        include_unpublished=True,
        statuses=PUBLIC_VERSION_STATUSES,
    )
    return tuple(_build_featured_contract_entry(contract) for contract in contracts if contract.id)


def _load_audit_log_entries(session: Session) -> tuple[AdminAuditLogInspectionEntry, ...]:
    statement = (
        select(AdminAuditLog)
        .options(selectinload(AdminAuditLog.admin_user).selectinload(User.profile))
        .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
        .limit(MAX_AUDIT_LOG_ENTRIES)
    )
    return tuple(
        AdminAuditLogInspectionEntry(
            audit_log_id=entry.id,
            created_at_label=_format_admin_timestamp(entry.created_at),
            admin_label=_resolve_admin_label(entry.admin_user),
            action=entry.action,
            action_label=entry.action.replace("_", " ").title(),
            entity_type_label=entry.entity_type.replace("_", " ").title(),
            summary=entry.summary or "No summary provided.",
            details_pretty_json=_serialize_audit_details(entry.details),
            has_details=bool(entry.details),
        )
        for entry in session.exec(statement).all()
        if entry.id is not None
    )


def _build_featured_contract_entry(contract: Contract) -> AdminFeaturedContractEntry:
    latest_public_version = (
        contract.latest_published_version.semantic_version
        if contract.latest_published_version is not None
        else "No public version yet"
    )
    ordered_categories = _sorted_contract_category_links(contract)
    category_names = tuple(
        link.category.name for link in ordered_categories if link.category is not None
    )
    return AdminFeaturedContractEntry(
        contract_id=contract.id,
        slug=contract.slug,
        display_name=contract.display_name,
        contract_name=contract.contract_name,
        author_name=_resolve_author_name(contract),
        categories_label=", ".join(category_names) or "Uncategorized",
        latest_public_version=latest_public_version,
        status_label=contract.status.value.replace("_", " ").title(),
        status=contract.status.value,
        is_featured=contract.featured,
        updated_at_label=_format_admin_timestamp(contract.updated_at),
        public_detail_href=build_contract_detail_path(contract.slug),
        edit_href=build_admin_contract_edit_path(contract.slug),
    )


def _ensure_unique_category_values(
    *,
    session: Session,
    slug: str,
    name: str,
    exclude_category_id: int | None = None,
) -> None:
    slug_statement = select(Category).where(Category.slug == slug)
    name_statement = select(Category).where(Category.name == name)
    if exclude_category_id is not None:
        slug_statement = slug_statement.where(Category.id != exclude_category_id)
        name_statement = name_statement.where(Category.id != exclude_category_id)

    if session.exec(slug_statement).first() is not None:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.DUPLICATE_CATEGORY_SLUG,
            "Choose a different category slug.",
            field="slug",
            details={"slug": slug},
        )
    if session.exec(name_statement).first() is not None:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.DUPLICATE_CATEGORY_NAME,
            "Choose a different category name.",
            field="name",
            details={"name": name},
        )


def _category_integrity_error(slug: str, name: str) -> AdminCatalogOperationsError:
    return AdminCatalogOperationsError(
        AdminCatalogOperationsErrorCode.DUPLICATE_CATEGORY_SLUG,
        "Category slugs and names must remain unique.",
        field="slug",
        details={"slug": slug, "name": name},
    )


def _linked_contract_ids_for_category(*, session: Session, category_id: int) -> list[int]:
    statement = select(ContractCategoryLink.contract_id).where(
        ContractCategoryLink.category_id == category_id
    )
    return list(session.exec(statement).all())


def _require_category(*, session: Session, category_id: int) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.CATEGORY_NOT_FOUND,
            "The requested category could not be found.",
            field="category",
            details={"category_id": category_id},
        )
    return category


def _require_contract(*, session: Session, contract_slug: str) -> Contract:
    normalized_slug = str(contract_slug or "").strip().lower()
    if not normalized_slug:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.CONTRACT_NOT_FOUND,
            "The requested contract could not be found.",
            field="contract",
        )

    statement = select(Contract).where(Contract.slug == normalized_slug)
    contract = session.exec(statement).first()
    if contract is None:
        raise AdminCatalogOperationsError(
            AdminCatalogOperationsErrorCode.CONTRACT_NOT_FOUND,
            "The requested contract could not be found.",
            field="contract",
            details={"contract_slug": normalized_slug},
        )
    return contract


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


def _resolve_admin_label(admin_user: User | None) -> str:
    if admin_user is None:
        return "Unknown admin"
    profile: Profile | None = admin_user.profile
    if profile is not None and profile.display_name:
        return profile.display_name
    if profile is not None and profile.username:
        return f"@{profile.username}"
    return admin_user.email


def _serialize_audit_details(details: dict[str, object]) -> str:
    if not details:
        return "{}"
    return json.dumps(details, indent=2, sort_keys=True, default=str)


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


def _format_admin_timestamp(value) -> str:
    if value is None:
        return "No updates yet"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d")


__all__ = [
    "AdminAuditLogInspectionEntry",
    "AdminCatalogOperationsError",
    "AdminCatalogOperationsErrorCode",
    "AdminCatalogOperationsSnapshot",
    "AdminCategoryManagementEntry",
    "AdminFeaturedContractEntry",
    "build_empty_admin_catalog_operations_snapshot",
    "create_admin_category",
    "delete_admin_category",
    "load_admin_catalog_operations_snapshot",
    "load_admin_catalog_operations_snapshot_safe",
    "normalize_admin_category_description",
    "normalize_admin_category_name",
    "normalize_admin_category_slug",
    "normalize_admin_category_sort_order",
    "set_admin_contract_featured_state",
    "update_admin_category",
]
