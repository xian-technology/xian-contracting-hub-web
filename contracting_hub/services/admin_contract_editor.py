"""Admin contract-editor services for metadata and taxonomy management."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

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
    ContractNetwork,
    PublicationStatus,
    User,
    UserStatus,
)
from contracting_hub.services.auth import require_admin_user
from contracting_hub.services.contract_metadata import (
    ContractMetadataValidationError,
    validate_contract_name,
    validate_contract_slug,
)
from contracting_hub.services.contract_search import rebuild_contract_search_document
from contracting_hub.services.contract_versions import PUBLIC_VERSION_STATUSES
from contracting_hub.utils.meta import build_contract_detail_path

MAX_CONTRACT_DISPLAY_NAME_LENGTH = 128
MAX_CONTRACT_SHORT_SUMMARY_LENGTH = 280
MAX_CONTRACT_AUTHOR_LABEL_LENGTH = 128
MAX_CONTRACT_LICENSE_NAME_LENGTH = 64
MAX_CONTRACT_URL_LENGTH = 500
ALLOWED_CONTRACT_URL_SCHEMES = frozenset({"http", "https"})


class AdminContractEditorMode(StrEnum):
    """Supported admin editor modes."""

    CREATE = "create"
    EDIT = "edit"


class AdminContractEditorServiceErrorCode(StrEnum):
    """Stable admin contract-editor failures exposed to callers."""

    CONTRACT_NOT_FOUND = "contract_not_found"
    DUPLICATE_CONTRACT_NAME = "duplicate_contract_name"
    DUPLICATE_SLUG = "duplicate_slug"
    INVALID_AUTHOR = "invalid_author"
    INVALID_CATEGORY = "invalid_category"
    INVALID_CONTRACT_NAME = "invalid_contract_name"
    INVALID_DISPLAY_NAME = "invalid_display_name"
    INVALID_LICENSE_NAME = "invalid_license_name"
    INVALID_NETWORK = "invalid_network"
    INVALID_SHORT_SUMMARY = "invalid_short_summary"
    INVALID_SLUG = "invalid_slug"
    INVALID_URL = "invalid_url"
    AUTHOR_REQUIRED = "author_required"
    LONG_DESCRIPTION_REQUIRED = "long_description_required"


class AdminContractEditorServiceError(ValueError):
    """Structured service error for admin contract-metadata workflows."""

    def __init__(
        self,
        code: AdminContractEditorServiceErrorCode,
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
        """Serialize the service failure for UI or API responses."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True)
class AdminContractEditorAuthorOption:
    """Selectable author option rendered in the admin editor."""

    user_id: int
    username: str
    display_label: str
    secondary_label: str


@dataclass(frozen=True)
class AdminContractEditorCategoryOption:
    """Selectable taxonomy option rendered in the admin editor."""

    category_id: int
    slug: str
    name: str
    description: str | None


@dataclass(frozen=True)
class AdminContractEditorSnapshot:
    """Loaded editor data for creating or editing one contract."""

    mode: AdminContractEditorMode
    contract_id: int | None
    slug: str
    contract_name: str
    display_name: str
    short_summary: str
    long_description: str
    author_user_id: int | None
    author_label: str
    featured: bool
    license_name: str
    documentation_url: str
    source_repository_url: str
    network: ContractNetwork | None
    primary_category_id: int | None
    secondary_category_ids: tuple[int, ...]
    tags_text: str
    status: PublicationStatus
    latest_public_version: str | None
    public_detail_href: str | None
    author_options: tuple[AdminContractEditorAuthorOption, ...]
    category_options: tuple[AdminContractEditorCategoryOption, ...]


def build_empty_admin_contract_editor_snapshot(
    *,
    contract_slug: str | None = None,
) -> AdminContractEditorSnapshot:
    """Return a stable empty editor snapshot."""
    normalized_slug = str(contract_slug or "").strip().lower()
    mode = AdminContractEditorMode.EDIT if normalized_slug else AdminContractEditorMode.CREATE
    return AdminContractEditorSnapshot(
        mode=mode,
        contract_id=None,
        slug=normalized_slug,
        contract_name="",
        display_name="",
        short_summary="",
        long_description="",
        author_user_id=None,
        author_label="",
        featured=False,
        license_name="",
        documentation_url="",
        source_repository_url="",
        network=None,
        primary_category_id=None,
        secondary_category_ids=(),
        tags_text="",
        status=PublicationStatus.DRAFT,
        latest_public_version=None,
        public_detail_href=None,
        author_options=(),
        category_options=(),
    )


def load_admin_contract_editor_snapshot(
    *,
    session: Session,
    contract_slug: str | None = None,
) -> AdminContractEditorSnapshot:
    """Load editor data for a new contract or an existing contract slug."""
    author_options = _load_author_options(session)
    category_options = _load_category_options(session)
    normalized_slug = str(contract_slug or "").strip().lower()
    if not normalized_slug:
        return AdminContractEditorSnapshot(
            mode=AdminContractEditorMode.CREATE,
            contract_id=None,
            slug="",
            contract_name="",
            display_name="",
            short_summary="",
            long_description="",
            author_user_id=None,
            author_label="",
            featured=False,
            license_name="",
            documentation_url="",
            source_repository_url="",
            network=None,
            primary_category_id=(category_options[0].category_id if category_options else None),
            secondary_category_ids=(),
            tags_text="",
            status=PublicationStatus.DRAFT,
            latest_public_version=None,
            public_detail_href=None,
            author_options=author_options,
            category_options=category_options,
        )

    contract = _require_contract_for_editor(session, contract_slug=normalized_slug)
    ordered_categories = _sorted_contract_category_links(contract)
    primary_category_id = next(
        (link.category_id for link in ordered_categories if link.is_primary),
        None,
    )
    secondary_category_ids = tuple(
        link.category_id for link in ordered_categories if not link.is_primary
    )
    latest_public_version = (
        contract.latest_published_version.semantic_version
        if contract.latest_published_version is not None
        else None
    )
    return AdminContractEditorSnapshot(
        mode=AdminContractEditorMode.EDIT,
        contract_id=contract.id,
        slug=contract.slug,
        contract_name=contract.contract_name,
        display_name=contract.display_name,
        short_summary=contract.short_summary,
        long_description=contract.long_description,
        author_user_id=contract.author_user_id,
        author_label=contract.author_label or "",
        featured=contract.featured,
        license_name=contract.license_name or "",
        documentation_url=contract.documentation_url or "",
        source_repository_url=contract.source_repository_url or "",
        network=contract.network,
        primary_category_id=primary_category_id,
        secondary_category_ids=secondary_category_ids,
        tags_text=", ".join(contract.tags),
        status=contract.status,
        latest_public_version=latest_public_version,
        public_detail_href=(
            build_contract_detail_path(contract.slug)
            if contract.status in PUBLIC_VERSION_STATUSES and latest_public_version is not None
            else None
        ),
        author_options=author_options,
        category_options=category_options,
    )


def load_admin_contract_editor_snapshot_safe(
    *,
    contract_slug: str | None = None,
) -> AdminContractEditorSnapshot:
    """Load the editor snapshot while tolerating a missing or unmigrated database."""
    try:
        with session_scope() as session:
            return load_admin_contract_editor_snapshot(
                session=session,
                contract_slug=contract_slug,
            )
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_admin_contract_editor_snapshot(contract_slug=contract_slug)


def create_admin_contract_metadata(
    *,
    session: Session,
    session_token: str | None,
    slug: str,
    contract_name: str,
    display_name: str,
    short_summary: str,
    long_description: str,
    author_user_id: int | str | None = None,
    author_label: str | None = None,
    featured: bool | str | None = None,
    license_name: str | None = None,
    documentation_url: str | None = None,
    source_repository_url: str | None = None,
    network: ContractNetwork | str | None = None,
    primary_category_id: int | str | None = None,
    secondary_category_ids: tuple[int | str, ...] | list[int | str] = (),
    tags_text: str | None = None,
) -> Contract:
    """Create a draft contract and persist its editor-managed metadata."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    normalized = _normalize_editor_payload(
        session=session,
        slug=slug,
        contract_name=contract_name,
        display_name=display_name,
        short_summary=short_summary,
        long_description=long_description,
        author_user_id=author_user_id,
        author_label=author_label,
        featured=featured,
        license_name=license_name,
        documentation_url=documentation_url,
        source_repository_url=source_repository_url,
        network=network,
        primary_category_id=primary_category_id,
        secondary_category_ids=secondary_category_ids,
        tags_text=tags_text,
    )
    _assert_unique_contract_identity(
        session,
        slug=normalized.slug,
        contract_name=normalized.contract_name,
    )

    contract = Contract(
        slug=normalized.slug,
        contract_name=normalized.contract_name,
        display_name=normalized.display_name,
        short_summary=normalized.short_summary,
        long_description=normalized.long_description,
        author_user_id=normalized.author_user_id,
        author_label=normalized.author_label,
        status=PublicationStatus.DRAFT,
        featured=normalized.featured,
        license_name=normalized.license_name,
        documentation_url=normalized.documentation_url,
        source_repository_url=normalized.source_repository_url,
        network=normalized.network,
        tags=list(normalized.tags),
    )
    contract.category_links = list(_build_category_links(normalized.category_ids))
    session.add(contract)
    session.flush()
    contract_id = _require_persisted_id(contract.id, label="contract")
    _rebuild_search_document(session, contract_id=contract_id)
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="create_contract",
            entity_type="contract",
            entity_id=contract_id,
            summary=f"Created contract {contract.slug}.",
            details={
                "slug": contract.slug,
                "contract_name": contract.contract_name,
                "category_ids": list(normalized.category_ids),
                "featured": normalized.featured,
            },
        )
    )
    _commit_editor_transaction(
        session,
        slug=normalized.slug,
        contract_name=normalized.contract_name,
    )
    session.refresh(contract)
    return contract


def update_admin_contract_metadata(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
    slug: str,
    contract_name: str,
    display_name: str,
    short_summary: str,
    long_description: str,
    author_user_id: int | str | None = None,
    author_label: str | None = None,
    featured: bool | str | None = None,
    license_name: str | None = None,
    documentation_url: str | None = None,
    source_repository_url: str | None = None,
    network: ContractNetwork | str | None = None,
    primary_category_id: int | str | None = None,
    secondary_category_ids: tuple[int | str, ...] | list[int | str] = (),
    tags_text: str | None = None,
) -> Contract:
    """Update one contract's editor-managed metadata without touching versions."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    contract = _require_contract_for_editor(session, contract_slug=contract_slug)
    normalized = _normalize_editor_payload(
        session=session,
        slug=slug,
        contract_name=contract_name,
        display_name=display_name,
        short_summary=short_summary,
        long_description=long_description,
        author_user_id=author_user_id,
        author_label=author_label,
        featured=featured,
        license_name=license_name,
        documentation_url=documentation_url,
        source_repository_url=source_repository_url,
        network=network,
        primary_category_id=primary_category_id,
        secondary_category_ids=secondary_category_ids,
        tags_text=tags_text,
    )
    contract_id = _require_persisted_id(contract.id, label="contract")
    previous_slug = contract.slug
    previous_contract_name = contract.contract_name
    _assert_unique_contract_identity(
        session,
        slug=normalized.slug,
        contract_name=normalized.contract_name,
        excluded_contract_id=contract_id,
    )

    contract.slug = normalized.slug
    contract.contract_name = normalized.contract_name
    contract.display_name = normalized.display_name
    contract.short_summary = normalized.short_summary
    contract.long_description = normalized.long_description
    contract.author_user_id = normalized.author_user_id
    contract.author_label = normalized.author_label
    contract.featured = normalized.featured
    contract.license_name = normalized.license_name
    contract.documentation_url = normalized.documentation_url
    contract.source_repository_url = normalized.source_repository_url
    contract.network = normalized.network
    contract.tags = list(normalized.tags)
    contract.category_links.clear()
    session.flush()
    contract.category_links.extend(_build_category_links(normalized.category_ids))
    session.add(contract)
    _rebuild_search_document(session, contract_id=contract_id)
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="update_contract_metadata",
            entity_type="contract",
            entity_id=contract_id,
            summary=f"Updated contract {contract.slug}.",
            details={
                "slug": contract.slug,
                "previous_slug": previous_slug,
                "previous_contract_name": previous_contract_name,
                "contract_name": contract.contract_name,
                "category_ids": list(normalized.category_ids),
                "featured": normalized.featured,
            },
        )
    )
    _commit_editor_transaction(
        session,
        slug=normalized.slug,
        contract_name=normalized.contract_name,
    )
    session.refresh(contract)
    return contract


@dataclass(frozen=True)
class _NormalizedEditorPayload:
    slug: str
    contract_name: str
    display_name: str
    short_summary: str
    long_description: str
    author_user_id: int | None
    author_label: str | None
    featured: bool
    license_name: str | None
    documentation_url: str | None
    source_repository_url: str | None
    network: ContractNetwork | None
    category_ids: tuple[int, ...]
    tags: tuple[str, ...]


def _normalize_editor_payload(
    *,
    session: Session,
    slug: str,
    contract_name: str,
    display_name: str,
    short_summary: str,
    long_description: str,
    author_user_id: int | str | None,
    author_label: str | None,
    featured: bool | str | None,
    license_name: str | None,
    documentation_url: str | None,
    source_repository_url: str | None,
    network: ContractNetwork | str | None,
    primary_category_id: int | str | None,
    secondary_category_ids: tuple[int | str, ...] | list[int | str],
    tags_text: str | None,
) -> _NormalizedEditorPayload:
    normalized_slug = _normalize_contract_slug(slug)
    normalized_contract_name = _normalize_contract_name(contract_name)
    normalized_display_name = _normalize_display_name(display_name)
    normalized_short_summary = _normalize_short_summary(short_summary)
    normalized_long_description = _normalize_long_description(long_description)
    normalized_author_user_id, normalized_author_label = _normalize_author_assignment(
        session=session,
        author_user_id=author_user_id,
        author_label=author_label,
    )
    normalized_category_ids = _normalize_category_assignments(
        session=session,
        primary_category_id=primary_category_id,
        secondary_category_ids=secondary_category_ids,
    )
    return _NormalizedEditorPayload(
        slug=normalized_slug,
        contract_name=normalized_contract_name,
        display_name=normalized_display_name,
        short_summary=normalized_short_summary,
        long_description=normalized_long_description,
        author_user_id=normalized_author_user_id,
        author_label=normalized_author_label,
        featured=_normalize_featured_flag(featured),
        license_name=_normalize_license_name(license_name),
        documentation_url=_normalize_contract_url(
            documentation_url,
            field="documentation_url",
        ),
        source_repository_url=_normalize_contract_url(
            source_repository_url,
            field="source_repository_url",
        ),
        network=_normalize_contract_network(network),
        category_ids=normalized_category_ids,
        tags=_normalize_contract_tags(tags_text),
    )


def _normalize_contract_slug(value: str) -> str:
    try:
        return validate_contract_slug(value)
    except ContractMetadataValidationError as error:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_SLUG,
            str(error),
            field=error.field,
            details=error.details,
        ) from error


def _normalize_contract_name(value: str) -> str:
    try:
        return validate_contract_name(value)
    except ContractMetadataValidationError as error:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_CONTRACT_NAME,
            str(error),
            field=error.field,
            details=error.details,
        ) from error


def _normalize_display_name(value: str) -> str:
    if not isinstance(value, str):
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_DISPLAY_NAME,
            "Display name must be a string.",
            field="display_name",
            details={"expected_type": "str"},
        )
    normalized = " ".join(value.split()).strip()
    if not normalized:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_DISPLAY_NAME,
            "Display name is required.",
            field="display_name",
        )
    if len(normalized) > MAX_CONTRACT_DISPLAY_NAME_LENGTH:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_DISPLAY_NAME,
            "Display name must be 128 characters or fewer.",
            field="display_name",
            details={"max_length": MAX_CONTRACT_DISPLAY_NAME_LENGTH},
        )
    return normalized


def _normalize_short_summary(value: str) -> str:
    if not isinstance(value, str):
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_SHORT_SUMMARY,
            "Short summary must be a string.",
            field="short_summary",
            details={"expected_type": "str"},
        )
    normalized = " ".join(value.split()).strip()
    if not normalized:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_SHORT_SUMMARY,
            "Short summary is required.",
            field="short_summary",
        )
    if len(normalized) > MAX_CONTRACT_SHORT_SUMMARY_LENGTH:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_SHORT_SUMMARY,
            "Short summary must be 280 characters or fewer.",
            field="short_summary",
            details={"max_length": MAX_CONTRACT_SHORT_SUMMARY_LENGTH},
        )
    return normalized


def _normalize_long_description(value: str) -> str:
    if not isinstance(value, str):
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.LONG_DESCRIPTION_REQUIRED,
            "Long description must be a string.",
            field="long_description",
            details={"expected_type": "str"},
        )
    normalized = value.strip()
    if normalized:
        return normalized
    raise AdminContractEditorServiceError(
        AdminContractEditorServiceErrorCode.LONG_DESCRIPTION_REQUIRED,
        "Long description is required.",
        field="long_description",
    )


def _normalize_author_assignment(
    *,
    session: Session,
    author_user_id: int | str | None,
    author_label: str | None,
) -> tuple[int | None, str | None]:
    normalized_author_user_id = _normalize_optional_int(author_user_id, field="author_user_id")
    if normalized_author_user_id is not None:
        author = session.get(User, normalized_author_user_id)
        if author is None or author.status is not UserStatus.ACTIVE or author.profile is None:
            raise AdminContractEditorServiceError(
                AdminContractEditorServiceErrorCode.INVALID_AUTHOR,
                "Choose a valid active author profile.",
                field="author_user_id",
                details={"author_user_id": normalized_author_user_id},
            )
        return normalized_author_user_id, None

    normalized_label = " ".join(str(author_label or "").split()).strip() or None
    if normalized_label is None:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.AUTHOR_REQUIRED,
            "Assign an internal author or provide a fallback author label.",
            field="author_assignment",
        )
    if len(normalized_label) > MAX_CONTRACT_AUTHOR_LABEL_LENGTH:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.AUTHOR_REQUIRED,
            "Author label must be 128 characters or fewer.",
            field="author_label",
            details={"max_length": MAX_CONTRACT_AUTHOR_LABEL_LENGTH},
        )
    return None, normalized_label


def _normalize_featured_flag(value: bool | str | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on", "featured"}


def _normalize_license_name(value: str | None) -> str | None:
    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        return None
    if len(normalized) > MAX_CONTRACT_LICENSE_NAME_LENGTH:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_LICENSE_NAME,
            "License must be 64 characters or fewer.",
            field="license_name",
            details={"max_length": MAX_CONTRACT_LICENSE_NAME_LENGTH},
        )
    return normalized


def _normalize_contract_url(value: str | None, *, field: str) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) > MAX_CONTRACT_URL_LENGTH:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_URL,
            "URL values must be 500 characters or fewer.",
            field=field,
            details={"max_length": MAX_CONTRACT_URL_LENGTH},
        )
    parsed = urlparse(normalized)
    if parsed.scheme not in ALLOWED_CONTRACT_URL_SCHEMES or not parsed.netloc:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_URL,
            "URLs must use http or https.",
            field=field,
            details={"allowed_schemes": sorted(ALLOWED_CONTRACT_URL_SCHEMES)},
        )
    return normalized


def _normalize_contract_network(
    value: ContractNetwork | str | None,
) -> ContractNetwork | None:
    if value is None:
        return None
    if isinstance(value, ContractNetwork):
        return value
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    try:
        return ContractNetwork(normalized)
    except ValueError as error:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_NETWORK,
            "Choose a supported network value.",
            field="network",
            details={"allowed_values": [member.value for member in ContractNetwork]},
        ) from error


def _normalize_category_assignments(
    *,
    session: Session,
    primary_category_id: int | str | None,
    secondary_category_ids: tuple[int | str, ...] | list[int | str],
) -> tuple[int, ...]:
    normalized_primary_id = _normalize_optional_int(
        primary_category_id,
        field="primary_category_id",
        required=True,
    )
    category = session.get(Category, normalized_primary_id)
    if category is None:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_CATEGORY,
            "Choose a valid primary category.",
            field="primary_category_id",
            details={"category_id": normalized_primary_id},
        )

    secondary_ids: list[int] = []
    seen_ids = {normalized_primary_id}
    for value in secondary_category_ids:
        normalized_id = _normalize_optional_int(value, field="secondary_category_ids")
        if normalized_id is None or normalized_id in seen_ids:
            continue
        secondary_category = session.get(Category, normalized_id)
        if secondary_category is None:
            raise AdminContractEditorServiceError(
                AdminContractEditorServiceErrorCode.INVALID_CATEGORY,
                "Choose valid secondary categories.",
                field="secondary_category_ids",
                details={"category_id": normalized_id},
            )
        seen_ids.add(normalized_id)
        secondary_ids.append(normalized_id)

    return (normalized_primary_id, *secondary_ids)


def _normalize_contract_tags(value: str | None) -> tuple[str, ...]:
    normalized_tags: list[str] = []
    seen_tags: set[str] = set()
    for fragment in str(value or "").replace("\n", ",").split(","):
        normalized = " ".join(fragment.split()).strip().lower()
        if not normalized or normalized in seen_tags:
            continue
        seen_tags.add(normalized)
        normalized_tags.append(normalized)
    return tuple(normalized_tags)


def _normalize_optional_int(
    value: int | str | None,
    *,
    field: str,
    required: bool = False,
) -> int | None:
    if value is None:
        if required:
            raise AdminContractEditorServiceError(
                AdminContractEditorServiceErrorCode.INVALID_CATEGORY,
                "This field is required.",
                field=field,
            )
        return None
    if isinstance(value, bool):
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.INVALID_CATEGORY,
            "Expected a numeric identifier.",
            field=field,
            details={"expected_type": "int"},
        )
    if isinstance(value, int):
        return value
    normalized = str(value).strip()
    if not normalized:
        if required:
            raise AdminContractEditorServiceError(
                AdminContractEditorServiceErrorCode.INVALID_CATEGORY,
                "This field is required.",
                field=field,
            )
        return None
    if normalized.isdigit():
        return int(normalized)
    raise AdminContractEditorServiceError(
        AdminContractEditorServiceErrorCode.INVALID_CATEGORY,
        "Expected a numeric identifier.",
        field=field,
        details={"expected_type": "int"},
    )


def _assert_unique_contract_identity(
    session: Session,
    *,
    slug: str,
    contract_name: str,
    excluded_contract_id: int | None = None,
) -> None:
    duplicate_slug = session.exec(select(Contract).where(Contract.slug == slug)).first()
    if duplicate_slug is not None and duplicate_slug.id != excluded_contract_id:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.DUPLICATE_SLUG,
            "This slug is already in use.",
            field="slug",
            details={"slug": slug},
        )
    duplicate_name = session.exec(
        select(Contract).where(Contract.contract_name == contract_name)
    ).first()
    if duplicate_name is not None and duplicate_name.id != excluded_contract_id:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.DUPLICATE_CONTRACT_NAME,
            "This contract name is already in use.",
            field="contract_name",
            details={"contract_name": contract_name},
        )


def _load_author_options(session: Session) -> tuple[AdminContractEditorAuthorOption, ...]:
    statement = (
        select(User)
        .options(selectinload(User.profile))
        .where(User.status == UserStatus.ACTIVE)
        .order_by(User.email.asc())
    )
    users = [user for user in session.exec(statement).all() if user.profile is not None]
    options = [
        AdminContractEditorAuthorOption(
            user_id=_require_persisted_id(user.id, label="user"),
            username=user.profile.username,
            display_label=user.profile.display_name or f"@{user.profile.username}",
            secondary_label=user.email,
        )
        for user in users
    ]
    return tuple(
        sorted(
            options,
            key=lambda option: (
                option.display_label.lower(),
                option.username.lower(),
                option.secondary_label.lower(),
            ),
        )
    )


def _load_category_options(session: Session) -> tuple[AdminContractEditorCategoryOption, ...]:
    statement = select(Category).order_by(Category.sort_order.asc(), Category.name.asc())
    return tuple(
        AdminContractEditorCategoryOption(
            category_id=_require_persisted_id(category.id, label="category"),
            slug=category.slug,
            name=category.name,
            description=category.description,
        )
        for category in session.exec(statement).all()
    )


def _require_contract_for_editor(session: Session, *, contract_slug: str) -> Contract:
    statement = (
        select(Contract)
        .options(
            selectinload(Contract.author).selectinload(User.profile),
            selectinload(Contract.latest_published_version),
            selectinload(Contract.category_links).selectinload(ContractCategoryLink.category),
        )
        .where(Contract.slug == contract_slug)
    )
    contract = session.exec(statement).first()
    if contract is not None:
        return contract
    raise AdminContractEditorServiceError(
        AdminContractEditorServiceErrorCode.CONTRACT_NOT_FOUND,
        "The requested contract could not be found.",
        field="contract_slug",
        details={"contract_slug": contract_slug},
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


def _build_category_links(category_ids: tuple[int, ...]) -> tuple[ContractCategoryLink, ...]:
    return tuple(
        ContractCategoryLink(
            category_id=category_id,
            is_primary=index == 0,
            sort_order=index,
        )
        for index, category_id in enumerate(category_ids)
    )


def _rebuild_search_document(session: Session, *, contract_id: int) -> None:
    try:
        rebuild_contract_search_document(session, contract_id=contract_id)
    except sa.exc.OperationalError:
        pass


def _commit_editor_transaction(
    session: Session,
    *,
    slug: str,
    contract_name: str,
) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        _raise_duplicate_identity_error(
            error,
            slug=slug,
            contract_name=contract_name,
        )
        raise


def _raise_duplicate_identity_error(
    error: IntegrityError,
    *,
    slug: str,
    contract_name: str,
) -> None:
    message = str(error.orig).lower()
    if "contracts.slug" in message:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.DUPLICATE_SLUG,
            "This slug is already in use.",
            field="slug",
            details={"slug": slug},
        ) from error
    if "contracts.contract_name" in message:
        raise AdminContractEditorServiceError(
            AdminContractEditorServiceErrorCode.DUPLICATE_CONTRACT_NAME,
            "This contract name is already in use.",
            field="contract_name",
            details={"contract_name": contract_name},
        ) from error


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is not None:
        return value
    raise AdminContractEditorServiceError(
        AdminContractEditorServiceErrorCode.CONTRACT_NOT_FOUND,
        f"The expected {label} record is missing a persisted identifier.",
        field=f"{label}_id",
    )


__all__ = [
    "ALLOWED_CONTRACT_URL_SCHEMES",
    "MAX_CONTRACT_DISPLAY_NAME_LENGTH",
    "MAX_CONTRACT_LICENSE_NAME_LENGTH",
    "MAX_CONTRACT_SHORT_SUMMARY_LENGTH",
    "MAX_CONTRACT_URL_LENGTH",
    "AdminContractEditorAuthorOption",
    "AdminContractEditorCategoryOption",
    "AdminContractEditorMode",
    "AdminContractEditorServiceError",
    "AdminContractEditorServiceErrorCode",
    "AdminContractEditorSnapshot",
    "build_empty_admin_contract_editor_snapshot",
    "create_admin_contract_metadata",
    "load_admin_contract_editor_snapshot",
    "load_admin_contract_editor_snapshot_safe",
    "update_admin_contract_metadata",
]
