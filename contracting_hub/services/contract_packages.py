"""Service helpers for package release curation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from contracting_hub.models import (
    ContractPackage,
    ContractPackageKind,
    ContractPackageRelease,
    ContractPackageReleaseArtifact,
    PublicationStatus,
    utc_now,
)
from contracting_hub.repositories import ContractPackageRepository
from contracting_hub.services.contract_metadata import (
    ContractMetadataValidationError,
    validate_contract_slug,
    validate_publication_status,
    validate_semantic_version,
)
from contracting_hub.services.contract_versions import PUBLIC_VERSION_STATUSES

MAX_PACKAGE_DISPLAY_NAME_LENGTH = 128
MAX_PACKAGE_SHORT_SUMMARY_LENGTH = 280
MAX_PACKAGE_AUTHOR_LABEL_LENGTH = 128
MAX_PACKAGE_URL_LENGTH = 500
MAX_ARTIFACT_ROLE_LENGTH = 64
MAX_SOURCE_PATH_LENGTH = 500
MAX_SOURCE_COMMIT_LENGTH = 80
MAX_SOURCE_TAG_LENGTH = 128
MAX_SOURCE_HASH_LENGTH = 64
ALLOWED_PACKAGE_URL_SCHEMES = frozenset({"http", "https"})


class ContractPackageServiceErrorCode(StrEnum):
    """Stable package-service failures exposed to callers."""

    PACKAGE_NOT_FOUND = "package_not_found"
    RELEASE_NOT_FOUND = "release_not_found"
    CONTRACT_VERSION_NOT_FOUND = "contract_version_not_found"
    DUPLICATE_PACKAGE = "duplicate_package"
    DUPLICATE_RELEASE = "duplicate_release"
    DUPLICATE_ARTIFACT = "duplicate_artifact"
    HASH_MISMATCH = "hash_mismatch"
    INVALID_AUTHOR_LABEL = "invalid_author_label"
    INVALID_DEFAULT_CHI = "invalid_default_chi"
    INVALID_DEPLOY_ORDER = "invalid_deploy_order"
    INVALID_DISPLAY_NAME = "invalid_display_name"
    INVALID_KIND = "invalid_kind"
    INVALID_LONG_DESCRIPTION = "invalid_long_description"
    INVALID_MANIFEST_METADATA = "invalid_manifest_metadata"
    INVALID_RELEASE_NOTES = "invalid_release_notes"
    INVALID_ROLE = "invalid_role"
    INVALID_SHORT_SUMMARY = "invalid_short_summary"
    INVALID_SOURCE_COMMIT = "invalid_source_commit"
    INVALID_SOURCE_HASH = "invalid_source_hash"
    INVALID_SOURCE_PATH = "invalid_source_path"
    INVALID_SOURCE_TAG = "invalid_source_tag"
    INVALID_TAGS = "invalid_tags"
    INVALID_URL = "invalid_url"


class ContractPackageServiceError(ValueError):
    """Structured service error for package release workflows."""

    def __init__(
        self,
        code: ContractPackageServiceErrorCode,
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
        """Serialize one service failure for UI, import jobs, or API callers."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True)
class ContractPackageReleaseArtifactSnapshot:
    """One contract artifact included in a package release snapshot."""

    role: str | None
    contract_slug: str
    contract_name: str
    semantic_version: str
    source_path: str | None
    source_hash_sha256: str
    deploy_order: int
    default_chi: int | None
    deploy_default: bool
    manifest_metadata: dict[str, object]


@dataclass(frozen=True)
class ContractPackageReleaseSnapshot:
    """Loaded package, release, and artifact metadata."""

    found: bool
    package_slug: str | None
    package_display_name: str
    semantic_version: str | None
    status: PublicationStatus | None
    source_repository_url: str | None
    source_commit: str | None
    source_tag: str | None
    manifest_path: str | None
    manifest_hash_sha256: str | None
    release_notes: str | None
    artifacts: tuple[ContractPackageReleaseArtifactSnapshot, ...]


def create_contract_package(
    *,
    session: Session,
    slug: str,
    display_name: str,
    short_summary: str,
    long_description: str,
    kind: ContractPackageKind | str = ContractPackageKind.STANDALONE,
    status: PublicationStatus | str = PublicationStatus.DRAFT,
    author_user_id: int | None = None,
    author_label: str | None = None,
    documentation_url: str | None = None,
    source_repository_url: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    auto_commit: bool = True,
) -> ContractPackage:
    """Create a stable package record for a curated contract source owner."""
    repository = ContractPackageRepository(session)
    normalized_slug = validate_contract_slug(slug)
    if repository.get_package_by_slug(normalized_slug) is not None:
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.DUPLICATE_PACKAGE,
            f"Package {normalized_slug!r} already exists.",
            field="slug",
            details={"slug": normalized_slug},
        )

    package = ContractPackage(
        slug=normalized_slug,
        display_name=_normalize_required_text(
            display_name,
            field="display_name",
            code=ContractPackageServiceErrorCode.INVALID_DISPLAY_NAME,
            max_length=MAX_PACKAGE_DISPLAY_NAME_LENGTH,
        ),
        short_summary=_normalize_required_text(
            short_summary,
            field="short_summary",
            code=ContractPackageServiceErrorCode.INVALID_SHORT_SUMMARY,
            max_length=MAX_PACKAGE_SHORT_SUMMARY_LENGTH,
        ),
        long_description=_normalize_required_text(
            long_description,
            field="long_description",
            code=ContractPackageServiceErrorCode.INVALID_LONG_DESCRIPTION,
        ),
        kind=_normalize_package_kind(kind),
        status=validate_publication_status(status),
        author_user_id=author_user_id,
        author_label=_normalize_optional_text(
            author_label,
            field="author_label",
            code=ContractPackageServiceErrorCode.INVALID_AUTHOR_LABEL,
            max_length=MAX_PACKAGE_AUTHOR_LABEL_LENGTH,
        ),
        documentation_url=_normalize_optional_url(documentation_url, field="documentation_url"),
        source_repository_url=_normalize_optional_url(
            source_repository_url,
            field="source_repository_url",
        ),
        tags=_normalize_tags(tags),
    )
    return _add_with_integrity_handling(
        session=session,
        entity=package,
        add=repository.add_package,
        duplicate_code=ContractPackageServiceErrorCode.DUPLICATE_PACKAGE,
        duplicate_field="slug",
        auto_commit=auto_commit,
    )


def create_contract_package_release(
    *,
    session: Session,
    package_slug: str,
    semantic_version: str,
    status: PublicationStatus | str = PublicationStatus.DRAFT,
    source_repository_url: str | None = None,
    source_commit: str | None = None,
    source_tag: str | None = None,
    manifest_path: str | None = None,
    manifest_hash_sha256: str | None = None,
    release_notes: str | None = None,
    auto_commit: bool = True,
) -> ContractPackageRelease:
    """Create an immutable release row for a curated package."""
    repository = ContractPackageRepository(session)
    normalized_package_slug = validate_contract_slug(package_slug)
    package = repository.get_package_by_slug(normalized_package_slug)
    if package is None:
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.PACKAGE_NOT_FOUND,
            f"Package {normalized_package_slug!r} does not exist.",
            field="package_slug",
            details={"package_slug": normalized_package_slug},
        )

    normalized_version = validate_semantic_version(semantic_version)
    if repository.get_package_release(package.id, normalized_version) is not None:
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.DUPLICATE_RELEASE,
            f"Package {package.slug!r} already has release {normalized_version!r}.",
            field="semantic_version",
            details={"package_slug": package.slug, "semantic_version": normalized_version},
        )

    normalized_status = validate_publication_status(status)
    release = ContractPackageRelease(
        package_id=package.id,
        semantic_version=normalized_version,
        status=normalized_status,
        source_repository_url=_normalize_optional_url(
            source_repository_url or package.source_repository_url,
            field="source_repository_url",
        ),
        source_commit=_normalize_optional_text(
            source_commit,
            field="source_commit",
            code=ContractPackageServiceErrorCode.INVALID_SOURCE_COMMIT,
            max_length=MAX_SOURCE_COMMIT_LENGTH,
        ),
        source_tag=_normalize_optional_text(
            source_tag,
            field="source_tag",
            code=ContractPackageServiceErrorCode.INVALID_SOURCE_TAG,
            max_length=MAX_SOURCE_TAG_LENGTH,
        ),
        manifest_path=_normalize_optional_text(
            manifest_path,
            field="manifest_path",
            code=ContractPackageServiceErrorCode.INVALID_SOURCE_PATH,
            max_length=MAX_SOURCE_PATH_LENGTH,
        ),
        manifest_hash_sha256=_normalize_optional_sha256(
            manifest_hash_sha256,
            field="manifest_hash_sha256",
        ),
        release_notes=_normalize_optional_text(
            release_notes,
            field="release_notes",
            code=ContractPackageServiceErrorCode.INVALID_RELEASE_NOTES,
        ),
        published_at=utc_now() if normalized_status in PUBLIC_VERSION_STATUSES else None,
    )
    try:
        repository.add_release(release)
        if normalized_status in PUBLIC_VERSION_STATUSES:
            package.latest_published_release = release
        if auto_commit:
            session.commit()
            session.refresh(release)
        else:
            session.flush()
        return release
    except IntegrityError as error:
        session.rollback()
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.DUPLICATE_RELEASE,
            "Package release already exists.",
            field="semantic_version",
        ) from error


def attach_contract_version_to_package_release(
    *,
    session: Session,
    release_id: int,
    contract_version_id: int,
    role: str | None = None,
    source_path: str | None = None,
    source_hash_sha256: str | None = None,
    deploy_order: int = 0,
    default_chi: int | None = None,
    deploy_default: bool = True,
    manifest_metadata: dict[str, object] | None = None,
    auto_commit: bool = True,
) -> ContractPackageReleaseArtifact:
    """Attach an immutable contract version as one artifact in a package release."""
    repository = ContractPackageRepository(session)
    release = repository.get_package_release_by_id(release_id)
    if release is None:
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.RELEASE_NOT_FOUND,
            f"Package release id {release_id!r} does not exist.",
            field="release_id",
            details={"release_id": release_id},
        )
    contract_version = repository.get_contract_version_by_id(contract_version_id)
    if contract_version is None:
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.CONTRACT_VERSION_NOT_FOUND,
            f"Contract version id {contract_version_id!r} does not exist.",
            field="contract_version_id",
            details={"contract_version_id": contract_version_id},
        )

    normalized_hash = _normalize_optional_sha256(
        source_hash_sha256,
        field="source_hash_sha256",
    )
    if normalized_hash is not None and normalized_hash != contract_version.source_hash_sha256:
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.HASH_MISMATCH,
            "Package artifact source hash must match the stored contract version hash.",
            field="source_hash_sha256",
            details={
                "expected_hash": contract_version.source_hash_sha256,
                "provided_hash": normalized_hash,
            },
        )

    artifact = ContractPackageReleaseArtifact(
        release_id=release.id,
        contract_version_id=contract_version.id,
        role=_normalize_optional_text(
            role,
            field="role",
            code=ContractPackageServiceErrorCode.INVALID_ROLE,
            max_length=MAX_ARTIFACT_ROLE_LENGTH,
        ),
        source_path=_normalize_optional_text(
            source_path,
            field="source_path",
            code=ContractPackageServiceErrorCode.INVALID_SOURCE_PATH,
            max_length=MAX_SOURCE_PATH_LENGTH,
        ),
        source_hash_sha256=normalized_hash or contract_version.source_hash_sha256,
        deploy_order=_normalize_deploy_order(deploy_order),
        default_chi=_normalize_default_chi(default_chi),
        deploy_default=bool(deploy_default),
        manifest_metadata=_normalize_manifest_metadata(manifest_metadata),
    )
    return _add_with_integrity_handling(
        session=session,
        entity=artifact,
        add=repository.add_release_artifact,
        duplicate_code=ContractPackageServiceErrorCode.DUPLICATE_ARTIFACT,
        duplicate_field="contract_version_id",
        auto_commit=auto_commit,
    )


def load_contract_package_release_snapshot(
    *,
    session: Session,
    package_slug: str,
    semantic_version: str | None = None,
) -> ContractPackageReleaseSnapshot:
    """Load one package release with package and contract artifact context."""
    repository = ContractPackageRepository(session)
    normalized_package_slug = validate_contract_slug(package_slug)
    normalized_version = (
        validate_semantic_version(semantic_version) if semantic_version is not None else None
    )
    release = repository.get_package_release_detail(
        normalized_package_slug,
        semantic_version=normalized_version,
    )
    if release is None:
        return ContractPackageReleaseSnapshot(
            found=False,
            package_slug=normalized_package_slug,
            package_display_name="",
            semantic_version=normalized_version,
            status=None,
            source_repository_url=None,
            source_commit=None,
            source_tag=None,
            manifest_path=None,
            manifest_hash_sha256=None,
            release_notes=None,
            artifacts=(),
        )

    ordered_artifacts = sorted(
        release.artifacts,
        key=lambda artifact: (
            artifact.deploy_order,
            artifact.role or "",
            artifact.contract_version.contract.contract_name,
        ),
    )
    return ContractPackageReleaseSnapshot(
        found=True,
        package_slug=release.package.slug,
        package_display_name=release.package.display_name,
        semantic_version=release.semantic_version,
        status=release.status,
        source_repository_url=release.source_repository_url,
        source_commit=release.source_commit,
        source_tag=release.source_tag,
        manifest_path=release.manifest_path,
        manifest_hash_sha256=release.manifest_hash_sha256,
        release_notes=release.release_notes,
        artifacts=tuple(
            ContractPackageReleaseArtifactSnapshot(
                role=artifact.role,
                contract_slug=artifact.contract_version.contract.slug,
                contract_name=artifact.contract_version.contract.contract_name,
                semantic_version=artifact.contract_version.semantic_version,
                source_path=artifact.source_path,
                source_hash_sha256=(
                    artifact.source_hash_sha256 or artifact.contract_version.source_hash_sha256
                ),
                deploy_order=artifact.deploy_order,
                default_chi=artifact.default_chi,
                deploy_default=artifact.deploy_default,
                manifest_metadata=dict(artifact.manifest_metadata),
            )
            for artifact in ordered_artifacts
        ),
    )


def _normalize_required_text(
    value: str,
    *,
    field: str,
    code: ContractPackageServiceErrorCode,
    max_length: int | None = None,
) -> str:
    if not isinstance(value, str):
        raise ContractPackageServiceError(
            code,
            f"{field.replace('_', ' ').capitalize()} must be a string.",
            field=field,
            details={"expected_type": "str"},
        )

    normalized = value.strip()
    if not normalized:
        raise ContractPackageServiceError(
            code,
            f"{field.replace('_', ' ').capitalize()} is required.",
            field=field,
        )
    if max_length is not None and len(normalized) > max_length:
        raise ContractPackageServiceError(
            code,
            f"{field.replace('_', ' ').capitalize()} is too long.",
            field=field,
            details={"max_length": max_length},
        )
    return normalized


def _normalize_optional_text(
    value: str | None,
    *,
    field: str,
    code: ContractPackageServiceErrorCode,
    max_length: int | None = None,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractPackageServiceError(
            code,
            f"{field.replace('_', ' ').capitalize()} must be a string.",
            field=field,
            details={"expected_type": "str"},
        )

    normalized = value.strip()
    if not normalized:
        return None
    if max_length is not None and len(normalized) > max_length:
        raise ContractPackageServiceError(
            code,
            f"{field.replace('_', ' ').capitalize()} is too long.",
            field=field,
            details={"max_length": max_length},
        )
    return normalized


def _normalize_optional_url(value: str | None, *, field: str) -> str | None:
    normalized = _normalize_optional_text(
        value,
        field=field,
        code=ContractPackageServiceErrorCode.INVALID_URL,
        max_length=MAX_PACKAGE_URL_LENGTH,
    )
    if normalized is None:
        return None

    parsed = urlparse(normalized)
    if parsed.scheme in ALLOWED_PACKAGE_URL_SCHEMES and parsed.netloc:
        return normalized

    raise ContractPackageServiceError(
        ContractPackageServiceErrorCode.INVALID_URL,
        "URLs must use http or https.",
        field=field,
        details={"allowed_schemes": sorted(ALLOWED_PACKAGE_URL_SCHEMES)},
    )


def _normalize_optional_sha256(value: str | None, *, field: str) -> str | None:
    normalized = _normalize_optional_text(
        value,
        field=field,
        code=ContractPackageServiceErrorCode.INVALID_SOURCE_HASH,
        max_length=MAX_SOURCE_HASH_LENGTH,
    )
    if normalized is None:
        return None
    if len(normalized) == MAX_SOURCE_HASH_LENGTH and all(
        char in "0123456789abcdef" for char in normalized.lower()
    ):
        return normalized.lower()

    raise ContractPackageServiceError(
        ContractPackageServiceErrorCode.INVALID_SOURCE_HASH,
        "Source hashes must be 64-character SHA-256 hex digests.",
        field=field,
    )


def _normalize_package_kind(kind: ContractPackageKind | str) -> ContractPackageKind:
    if isinstance(kind, ContractPackageKind):
        return kind
    if not isinstance(kind, str):
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.INVALID_KIND,
            "Package kind must be a string.",
            field="kind",
            details={
                "allowed_values": [member.value for member in ContractPackageKind],
                "expected_type": "str",
            },
        )

    normalized = kind.strip().lower()
    try:
        return ContractPackageKind(normalized)
    except ValueError as error:
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.INVALID_KIND,
            "Unsupported package kind.",
            field="kind",
            details={"allowed_values": [member.value for member in ContractPackageKind]},
        ) from error


def _normalize_tags(tags: list[str] | tuple[str, ...] | None) -> list[str]:
    if tags is None:
        return []
    if not isinstance(tags, (list, tuple)):
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.INVALID_TAGS,
            "Tags must be a list of strings.",
            field="tags",
            details={"expected_type": "list[str]"},
        )

    normalized_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            raise ContractPackageServiceError(
                ContractPackageServiceErrorCode.INVALID_TAGS,
                "Tags must be strings.",
                field="tags",
                details={"expected_type": "str"},
            )
        normalized = tag.strip().lower()
        if normalized and normalized not in seen:
            normalized_tags.append(normalized)
            seen.add(normalized)
    return normalized_tags


def _normalize_deploy_order(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.INVALID_DEPLOY_ORDER,
            "Deploy order must be an integer.",
            field="deploy_order",
            details={"expected_type": "int"},
        )
    return value


def _normalize_default_chi(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContractPackageServiceError(
            ContractPackageServiceErrorCode.INVALID_DEFAULT_CHI,
            "Default chi must be a positive integer.",
            field="default_chi",
            details={"expected_type": "positive int"},
        )
    return value


def _normalize_manifest_metadata(value: dict[str, object] | None) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)

    raise ContractPackageServiceError(
        ContractPackageServiceErrorCode.INVALID_MANIFEST_METADATA,
        "Manifest metadata must be a dictionary.",
        field="manifest_metadata",
        details={"expected_type": "dict"},
    )


def _add_with_integrity_handling[T](
    *,
    session: Session,
    entity: T,
    add,
    duplicate_code: ContractPackageServiceErrorCode,
    duplicate_field: str,
    auto_commit: bool,
) -> T:
    try:
        add(entity)
        if auto_commit:
            session.commit()
            session.refresh(entity)
        else:
            session.flush()
        return entity
    except IntegrityError as error:
        session.rollback()
        raise ContractPackageServiceError(
            duplicate_code,
            "Package, release, or artifact already exists.",
            field=duplicate_field,
        ) from error
    except ContractMetadataValidationError:
        session.rollback()
        raise


__all__ = [
    "ALLOWED_PACKAGE_URL_SCHEMES",
    "ContractPackageReleaseArtifactSnapshot",
    "ContractPackageReleaseSnapshot",
    "ContractPackageServiceError",
    "ContractPackageServiceErrorCode",
    "attach_contract_version_to_package_release",
    "create_contract_package",
    "create_contract_package_release",
    "load_contract_package_release_snapshot",
]
