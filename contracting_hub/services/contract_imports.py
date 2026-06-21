"""Import curated package releases from owner-repo manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sqlmodel import Session, select

from contracting_hub.database import session_scope
from contracting_hub.models import (
    Contract,
    ContractPackageKind,
    ContractPackageRelease,
    ContractPackageReleaseArtifact,
    ContractVersion,
    PublicationStatus,
)
from contracting_hub.repositories import ContractPackageRepository, ContractVersionRepository
from contracting_hub.services.contract_metadata import (
    ContractMetadataValidationError,
    validate_contract_name,
    validate_contract_slug,
    validate_publication_status,
    validate_semantic_version,
)
from contracting_hub.services.contract_packages import (
    attach_contract_version_to_package_release,
    create_contract_package,
    create_contract_package_release,
)
from contracting_hub.services.contract_search import rebuild_contract_search_document
from contracting_hub.services.contract_versions import build_source_hash, create_contract_version

BUNDLE_MANIFEST_SCHEMA = "xian.contract_bundle.v1"
BUNDLE_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_IMPORT_AUTHOR_LABEL = "Xian Core"
PACKAGE_IMPORT_TAG = "imported"


class ContractImportErrorCode(StrEnum):
    """Stable import failures exposed by manifest import workflows."""

    ARTIFACT_CONFLICT = "artifact_conflict"
    CONTRACT_VERSION_CONFLICT = "contract_version_conflict"
    INVALID_CONTRACT_ENTRY = "invalid_contract_entry"
    INVALID_MANIFEST = "invalid_manifest"
    MANIFEST_NOT_FOUND = "manifest_not_found"
    PACKAGE_RELEASE_CONFLICT = "package_release_conflict"
    SOURCE_HASH_MISMATCH = "source_hash_mismatch"
    SOURCE_NOT_FOUND = "source_not_found"


class ContractImportError(ValueError):
    """Structured error raised when an owner-repo manifest cannot be imported."""

    def __init__(
        self,
        code: ContractImportErrorCode,
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
        """Serialize one manifest import failure."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True)
class BundleManifestContract:
    """Validated source artifact loaded from a bundle manifest."""

    name: str
    role: str | None
    path: str
    source_code: str
    source_hash_sha256: str
    deploy_order: int
    default_chi: int | None
    deploy_default: bool
    metadata: dict[str, object]


@dataclass(frozen=True)
class BundleManifest:
    """Validated package-release manifest."""

    path: Path
    root: Path
    manifest_hash_sha256: str
    package_slug: str
    package_display_name: str
    semantic_version: str
    description: str
    source_repository_url: str | None
    source_commit: str | None
    contracts: tuple[BundleManifestContract, ...]


@dataclass(frozen=True)
class ContractBundleManifestImportReport:
    """Summary of one manifest import run."""

    manifest_path: Path
    package_slug: str
    semantic_version: str
    package_created: bool
    release_created: bool
    contracts_created: int
    contracts_existing: int
    versions_created: int
    versions_existing: int
    artifacts_created: int
    artifacts_existing: int
    warnings: tuple[str, ...] = ()


def import_contract_bundle_manifest(
    *,
    session: Session,
    manifest_path: str | Path,
    package_kind: ContractPackageKind | str = ContractPackageKind.PRODUCT,
    package_status: PublicationStatus | str = PublicationStatus.PUBLISHED,
    release_status: PublicationStatus | str = PublicationStatus.PUBLISHED,
    contract_status: PublicationStatus | str = PublicationStatus.PUBLISHED,
    auto_commit: bool = True,
) -> ContractBundleManifestImportReport:
    """Import a local ``xian.contract_bundle.v1`` manifest into the catalog."""
    manifest = load_contract_bundle_manifest(manifest_path)
    normalized_package_kind = _normalize_package_kind(package_kind)
    normalized_package_status = validate_publication_status(package_status)
    normalized_release_status = validate_publication_status(release_status)
    normalized_contract_status = validate_publication_status(contract_status)

    package_repository = ContractPackageRepository(session)
    version_repository = ContractVersionRepository(session)
    warnings: list[str] = []
    package_created = False
    release_created = False
    contracts_created = 0
    contracts_existing = 0
    versions_created = 0
    versions_existing = 0
    artifacts_created = 0
    artifacts_existing = 0

    try:
        package = package_repository.get_package_by_slug(manifest.package_slug)
        if package is None:
            package = create_contract_package(
                session=session,
                slug=manifest.package_slug,
                display_name=manifest.package_display_name,
                short_summary=_bounded_text(manifest.description, max_length=280),
                long_description=manifest.description,
                kind=normalized_package_kind,
                status=normalized_package_status,
                author_label=DEFAULT_IMPORT_AUTHOR_LABEL,
                source_repository_url=manifest.source_repository_url,
                tags=_package_tags(manifest.package_slug),
                auto_commit=False,
            )
            package_created = True
        else:
            _warn_if_different(
                warnings,
                label="package source repository",
                stored=package.source_repository_url,
                imported=manifest.source_repository_url,
            )

        release = package_repository.get_package_release(package.id, manifest.semantic_version)
        if release is None:
            release = create_contract_package_release(
                session=session,
                package_slug=package.slug,
                semantic_version=manifest.semantic_version,
                status=normalized_release_status,
                source_repository_url=manifest.source_repository_url,
                source_commit=manifest.source_commit,
                manifest_path=_relative_manifest_path(manifest),
                manifest_hash_sha256=manifest.manifest_hash_sha256,
                release_notes=f"Imported from {manifest.path.name}.",
                auto_commit=False,
            )
            release_created = True
        else:
            _assert_existing_release_matches(release, manifest)

        for contract_definition in manifest.contracts:
            contract, created_contract = _get_or_create_manifest_contract(
                session=session,
                manifest=manifest,
                contract_definition=contract_definition,
                status=normalized_contract_status,
            )
            if created_contract:
                contracts_created += 1
            else:
                contracts_existing += 1

            version = version_repository.get_contract_version(
                contract.id,
                manifest.semantic_version,
            )
            if version is None:
                version = create_contract_version(
                    session=session,
                    contract_slug=contract.slug,
                    semantic_version=manifest.semantic_version,
                    source_code=contract_definition.source_code,
                    changelog=f"Imported from {manifest.path.name}.",
                    status=normalized_contract_status,
                    auto_commit=False,
                )
                versions_created += 1
            else:
                _assert_existing_version_matches(version, contract_definition)
                versions_existing += 1

            artifact = _get_release_artifact(
                session=session,
                release_id=release.id,
                contract_version_id=version.id,
            )
            if artifact is None:
                attach_contract_version_to_package_release(
                    session=session,
                    release_id=release.id,
                    contract_version_id=version.id,
                    role=contract_definition.role,
                    source_path=contract_definition.path,
                    source_hash_sha256=contract_definition.source_hash_sha256,
                    deploy_order=contract_definition.deploy_order,
                    default_chi=contract_definition.default_chi,
                    deploy_default=contract_definition.deploy_default,
                    manifest_metadata=contract_definition.metadata,
                    auto_commit=False,
                )
                artifacts_created += 1
            else:
                _assert_existing_artifact_matches(artifact, contract_definition)
                artifacts_existing += 1

        if auto_commit:
            session.commit()
        else:
            session.flush()

    except Exception:
        session.rollback()
        raise

    return ContractBundleManifestImportReport(
        manifest_path=manifest.path,
        package_slug=manifest.package_slug,
        semantic_version=manifest.semantic_version,
        package_created=package_created,
        release_created=release_created,
        contracts_created=contracts_created,
        contracts_existing=contracts_existing,
        versions_created=versions_created,
        versions_existing=versions_existing,
        artifacts_created=artifacts_created,
        artifacts_existing=artifacts_existing,
        warnings=tuple(warnings),
    )


def load_contract_bundle_manifest(manifest_path: str | Path) -> BundleManifest:
    """Load and validate a local ``xian.contract_bundle.v1`` manifest."""
    resolved_path = Path(manifest_path).expanduser().resolve()
    if not resolved_path.exists():
        raise ContractImportError(
            ContractImportErrorCode.MANIFEST_NOT_FOUND,
            f"Manifest does not exist: {resolved_path}",
            field="manifest_path",
            details={"manifest_path": str(resolved_path)},
        )
    if not resolved_path.is_file():
        raise ContractImportError(
            ContractImportErrorCode.INVALID_MANIFEST,
            f"Manifest path is not a file: {resolved_path}",
            field="manifest_path",
            details={"manifest_path": str(resolved_path)},
        )

    try:
        raw_bytes = resolved_path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_MANIFEST,
            "Manifest must be readable UTF-8 JSON.",
            field="manifest_path",
            details={"manifest_path": str(resolved_path)},
        ) from error

    if not isinstance(payload, dict):
        raise ContractImportError(
            ContractImportErrorCode.INVALID_MANIFEST,
            "Manifest root must be a JSON object.",
            field="manifest",
        )
    if payload.get("schema") != BUNDLE_MANIFEST_SCHEMA:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_MANIFEST,
            "Unsupported manifest schema.",
            field="schema",
            details={"expected_schema": BUNDLE_MANIFEST_SCHEMA},
        )
    if payload.get("schema_version") != BUNDLE_MANIFEST_SCHEMA_VERSION:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_MANIFEST,
            "Unsupported manifest schema version.",
            field="schema_version",
            details={"expected_schema_version": BUNDLE_MANIFEST_SCHEMA_VERSION},
        )

    root = resolved_path.parent
    package_slug = _validate_manifest_slug(
        _required_string(payload, "name", field="name"),
        field="name",
        code=ContractImportErrorCode.INVALID_MANIFEST,
    )
    package_display_name = _optional_string(payload, "display_name") or _title_from_slug(
        package_slug
    )
    semantic_version = _validate_manifest_semantic_version(
        _required_string(payload, "version", field="version"),
        field="version",
        code=ContractImportErrorCode.INVALID_MANIFEST,
    )
    description = (
        _optional_string(payload, "description")
        or f"Imported contract package {package_display_name}."
    )
    source_payload = _optional_object(payload, "source")
    source_repository_url = _optional_string(source_payload, "repo") if source_payload else None
    source_commit = _optional_string(source_payload, "commit") if source_payload else None
    contract_payloads = payload.get("contracts")
    if not isinstance(contract_payloads, list) or not contract_payloads:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_MANIFEST,
            "Manifest contracts must be a non-empty list.",
            field="contracts",
        )

    contract_names: set[str] = set()
    contracts: list[BundleManifestContract] = []
    for index, contract_payload in enumerate(contract_payloads):
        contract = _load_manifest_contract(
            root=root,
            payload=contract_payload,
            index=index,
            seen_names=contract_names,
        )
        contracts.append(contract)

    return BundleManifest(
        path=resolved_path,
        root=root,
        manifest_hash_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        package_slug=package_slug,
        package_display_name=package_display_name,
        semantic_version=semantic_version,
        description=description,
        source_repository_url=source_repository_url,
        source_commit=source_commit,
        contracts=tuple(contracts),
    )


def _load_manifest_contract(
    *,
    root: Path,
    payload: object,
    index: int,
    seen_names: set[str],
) -> BundleManifestContract:
    if not isinstance(payload, dict):
        raise ContractImportError(
            ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
            "Manifest contract entries must be objects.",
            field=f"contracts[{index}]",
        )

    contract_name = _validate_manifest_contract_name(
        _required_string(
            payload,
            "name",
            field=f"contracts[{index}].name",
            code=ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
        ),
        field=f"contracts[{index}].name",
    )
    if contract_name in seen_names:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
            f"Manifest has duplicate contract name {contract_name!r}.",
            field=f"contracts[{index}].name",
            details={"contract_name": contract_name},
        )
    seen_names.add(contract_name)

    source_path = _required_string(
        payload,
        "path",
        field=f"contracts[{index}].path",
        code=ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
    )
    source_file = (root / source_path).resolve()
    try:
        source_file.relative_to(root)
    except ValueError as error:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
            "Contract source path escapes the manifest directory.",
            field=f"contracts[{index}].path",
            details={"path": source_path},
        ) from error
    if not source_file.exists() or not source_file.is_file():
        raise ContractImportError(
            ContractImportErrorCode.SOURCE_NOT_FOUND,
            f"Contract source does not exist: {source_path}",
            field=f"contracts[{index}].path",
            details={"path": source_path},
        )

    try:
        source_code = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
            f"Contract source must be readable UTF-8 text: {source_path}",
            field=f"contracts[{index}].path",
            details={"path": source_path},
        ) from error
    actual_hash = build_source_hash(source_code)
    expected_hash = _required_string(
        payload,
        "sha256",
        field=f"contracts[{index}].sha256",
        code=ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
    )
    if actual_hash != expected_hash:
        raise ContractImportError(
            ContractImportErrorCode.SOURCE_HASH_MISMATCH,
            f"Source hash mismatch for {contract_name}.",
            field=f"contracts[{index}].sha256",
            details={
                "contract_name": contract_name,
                "path": source_path,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            },
        )

    role = _optional_string(payload, "role")
    deploy_order = _optional_int(payload, "deploy_order", default=0)
    default_chi = _optional_positive_int(payload, "default_chi")
    deploy_default = _optional_bool(payload, "deploy_default", default=True)
    return BundleManifestContract(
        name=contract_name,
        role=role,
        path=source_path,
        source_code=source_code,
        source_hash_sha256=actual_hash,
        deploy_order=deploy_order,
        default_chi=default_chi,
        deploy_default=deploy_default,
        metadata={
            key: value
            for key, value in payload.items()
            if key
            not in {
                "name",
                "path",
                "sha256",
                "deploy_order",
                "default_chi",
                "deploy_default",
            }
        },
    )


def _get_or_create_manifest_contract(
    *,
    session: Session,
    manifest: BundleManifest,
    contract_definition: BundleManifestContract,
    status: PublicationStatus,
) -> tuple[Contract, bool]:
    contract = _get_contract_by_name(session, contract_definition.name)
    if contract is not None:
        return contract, False

    contract_slug = _derive_contract_slug(
        manifest=manifest,
        contract_definition=contract_definition,
    )
    existing_slug = session.exec(select(Contract).where(Contract.slug == contract_slug)).first()
    if existing_slug is not None:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
            f"Derived contract slug {contract_slug!r} already exists.",
            field="contract.slug",
            details={
                "slug": contract_slug,
                "contract_name": contract_definition.name,
            },
        )

    contract = Contract(
        slug=contract_slug,
        contract_name=contract_definition.name,
        display_name=_contract_display_name(manifest, contract_definition),
        short_summary=_contract_short_summary(manifest, contract_definition),
        long_description=_contract_long_description(manifest, contract_definition),
        author_label=DEFAULT_IMPORT_AUTHOR_LABEL,
        status=status,
        source_repository_url=manifest.source_repository_url,
        tags=_contract_tags(manifest, contract_definition),
    )
    session.add(contract)
    session.flush()
    rebuild_contract_search_document(session, contract_id=contract.id)
    return contract, True


def _get_contract_by_name(session: Session, contract_name: str) -> Contract | None:
    statement = select(Contract).where(Contract.contract_name == contract_name)
    return session.exec(statement).first()


def _get_release_artifact(
    *,
    session: Session,
    release_id: int,
    contract_version_id: int,
) -> ContractPackageReleaseArtifact | None:
    statement = (
        select(ContractPackageReleaseArtifact)
        .where(ContractPackageReleaseArtifact.release_id == release_id)
        .where(ContractPackageReleaseArtifact.contract_version_id == contract_version_id)
    )
    return session.exec(statement).first()


def _assert_existing_release_matches(
    release: ContractPackageRelease,
    manifest: BundleManifest,
) -> None:
    mismatches: dict[str, tuple[object, object]] = {}
    if (
        release.manifest_hash_sha256
        and release.manifest_hash_sha256 != manifest.manifest_hash_sha256
    ):
        mismatches["manifest_hash_sha256"] = (
            release.manifest_hash_sha256,
            manifest.manifest_hash_sha256,
        )
    if (
        release.source_commit
        and manifest.source_commit
        and release.source_commit != manifest.source_commit
    ):
        mismatches["source_commit"] = (release.source_commit, manifest.source_commit)
    if mismatches:
        raise ContractImportError(
            ContractImportErrorCode.PACKAGE_RELEASE_CONFLICT,
            "Existing package release does not match the manifest being imported.",
            field="release",
            details={"mismatches": mismatches},
        )


def _assert_existing_version_matches(
    version: ContractVersion,
    contract_definition: BundleManifestContract,
) -> None:
    if version.source_hash_sha256 == contract_definition.source_hash_sha256:
        return

    raise ContractImportError(
        ContractImportErrorCode.CONTRACT_VERSION_CONFLICT,
        "Existing contract version source hash does not match the manifest.",
        field="contract_version",
        details={
            "contract_name": version.contract.contract_name if version.contract else None,
            "semantic_version": version.semantic_version,
            "expected_hash": contract_definition.source_hash_sha256,
            "stored_hash": version.source_hash_sha256,
        },
    )


def _assert_existing_artifact_matches(
    artifact: ContractPackageReleaseArtifact,
    contract_definition: BundleManifestContract,
) -> None:
    expected = {
        "role": contract_definition.role,
        "source_path": contract_definition.path,
        "source_hash_sha256": contract_definition.source_hash_sha256,
        "deploy_order": contract_definition.deploy_order,
        "default_chi": contract_definition.default_chi,
        "deploy_default": contract_definition.deploy_default,
        "manifest_metadata": contract_definition.metadata,
    }
    stored = {
        "role": artifact.role,
        "source_path": artifact.source_path,
        "source_hash_sha256": artifact.source_hash_sha256,
        "deploy_order": artifact.deploy_order,
        "default_chi": artifact.default_chi,
        "deploy_default": artifact.deploy_default,
        "manifest_metadata": dict(artifact.manifest_metadata),
    }
    mismatches = {
        field: (stored[field], expected[field])
        for field in expected
        if stored[field] != expected[field]
    }
    if not mismatches:
        return

    raise ContractImportError(
        ContractImportErrorCode.ARTIFACT_CONFLICT,
        "Existing package release artifact does not match the manifest.",
        field="artifact",
        details={"mismatches": mismatches},
    )


def _required_string(
    payload: dict[str, object],
    key: str,
    *,
    field: str,
    code: ContractImportErrorCode = ContractImportErrorCode.INVALID_MANIFEST,
) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ContractImportError(
        code,
        f"{field} must be a non-empty string.",
        field=field,
    )


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    raise ContractImportError(
        ContractImportErrorCode.INVALID_MANIFEST,
        f"{key} must be a string.",
        field=key,
        details={"expected_type": "str"},
    )


def _optional_object(payload: dict[str, object], key: str) -> dict[str, object] | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    raise ContractImportError(
        ContractImportErrorCode.INVALID_MANIFEST,
        f"{key} must be an object.",
        field=key,
        details={"expected_type": "object"},
    )


def _optional_int(payload: dict[str, object], key: str, *, default: int) -> int:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractImportError(
            ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
            f"{key} must be an integer.",
            field=key,
            details={"expected_type": "int"},
        )
    return value


def _optional_positive_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
            f"{key} must be a positive integer.",
            field=key,
            details={"expected_type": "positive int"},
        )
    return value


def _optional_bool(payload: dict[str, object], key: str, *, default: bool) -> bool:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ContractImportError(
        ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
        f"{key} must be a boolean.",
        field=key,
        details={"expected_type": "bool"},
    )


def _normalize_package_kind(kind: ContractPackageKind | str) -> ContractPackageKind:
    if isinstance(kind, ContractPackageKind):
        return kind
    if isinstance(kind, str):
        try:
            return ContractPackageKind(kind.strip().lower())
        except ValueError as error:
            raise ContractImportError(
                ContractImportErrorCode.INVALID_MANIFEST,
                "Unsupported package kind.",
                field="package_kind",
                details={"allowed_values": [member.value for member in ContractPackageKind]},
            ) from error
    raise ContractImportError(
        ContractImportErrorCode.INVALID_MANIFEST,
        "Package kind must be a string.",
        field="package_kind",
        details={"expected_type": "str"},
    )


def _derive_contract_slug(
    *,
    manifest: BundleManifest,
    contract_definition: BundleManifestContract,
) -> str:
    if _manifest_has_single_contract(manifest):
        return _validate_manifest_slug(
            manifest.package_slug,
            field="contract.slug",
            code=ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
        )

    suffix_source = contract_definition.role or contract_definition.name.removeprefix("con_")
    suffix = re.sub(r"[^a-z0-9]+", "-", suffix_source.lower()).strip("-")
    return _validate_manifest_slug(
        f"{manifest.package_slug}-{suffix}",
        field="contract.slug",
        code=ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
    )


def _manifest_has_single_contract(manifest: BundleManifest) -> bool:
    return len(manifest.contracts) == 1


def _validate_manifest_contract_name(value: str, *, field: str) -> str:
    try:
        return validate_contract_name(value)
    except ContractMetadataValidationError as error:
        raise ContractImportError(
            ContractImportErrorCode.INVALID_CONTRACT_ENTRY,
            str(error),
            field=field,
            details={"validation": error.as_payload()},
        ) from error


def _validate_manifest_slug(
    value: str,
    *,
    field: str,
    code: ContractImportErrorCode,
) -> str:
    try:
        return validate_contract_slug(value)
    except ContractMetadataValidationError as error:
        raise ContractImportError(
            code,
            str(error),
            field=field,
            details={"validation": error.as_payload()},
        ) from error


def _validate_manifest_semantic_version(
    value: str,
    *,
    field: str,
    code: ContractImportErrorCode,
) -> str:
    try:
        return validate_semantic_version(value)
    except ContractMetadataValidationError as error:
        raise ContractImportError(
            code,
            str(error),
            field=field,
            details={"validation": error.as_payload()},
        ) from error


def _contract_display_name(
    manifest: BundleManifest,
    contract_definition: BundleManifestContract,
) -> str:
    if _manifest_has_single_contract(manifest):
        return _bounded_text(manifest.package_display_name, max_length=128)

    suffix = contract_definition.role or contract_definition.name.removeprefix("con_")
    return _bounded_text(
        f"{manifest.package_display_name} {_title_from_slug(suffix)}",
        max_length=128,
    )


def _contract_short_summary(
    manifest: BundleManifest,
    contract_definition: BundleManifestContract,
) -> str:
    if _manifest_has_single_contract(manifest):
        return _bounded_text(manifest.description, max_length=280)

    role_label = contract_definition.role or contract_definition.name
    return _bounded_text(
        f"{role_label.replace('_', ' ').title()} contract from {manifest.package_display_name}.",
        max_length=280,
    )


def _contract_long_description(
    manifest: BundleManifest,
    contract_definition: BundleManifestContract,
) -> str:
    if _manifest_has_single_contract(manifest):
        return (
            f"{manifest.description}\n\n"
            f"Imported source `{contract_definition.name}` from `{contract_definition.path}`."
        )

    role_label = contract_definition.role or contract_definition.name
    return (
        f"{manifest.description}\n\n"
        f"Imported artifact `{contract_definition.name}` "
        f"({role_label}) from `{contract_definition.path}`."
    )


def _package_tags(package_slug: str) -> list[str]:
    return [PACKAGE_IMPORT_TAG, *package_slug.split("-")]


def _contract_tags(
    manifest: BundleManifest,
    contract_definition: BundleManifestContract,
) -> list[str]:
    tags = _package_tags(manifest.package_slug)
    if contract_definition.role is not None:
        tags.append(contract_definition.role.replace("_", "-"))
    return _dedupe_tags(tags)


def _dedupe_tags(tags: list[str]) -> list[str]:
    normalized_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = tag.strip().lower()
        if normalized and normalized not in seen:
            normalized_tags.append(normalized)
            seen.add(normalized)
    return normalized_tags


def _title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_\s]+", slug) if part)


def _bounded_text(value: str, *, max_length: int) -> str:
    normalized = " ".join(value.split()).strip()
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "..."


def _relative_manifest_path(manifest: BundleManifest) -> str:
    try:
        return str(manifest.path.relative_to(manifest.root))
    except ValueError:
        return manifest.path.name


def _warn_if_different(
    warnings: list[str],
    *,
    label: str,
    stored: str | None,
    imported: str | None,
) -> None:
    if stored and imported and stored != imported:
        warnings.append(f"Existing {label} {stored!r} differs from manifest value {imported!r}.")


def _format_import_report(report: ContractBundleManifestImportReport) -> str:
    lines = [
        f"manifest_path={report.manifest_path}",
        f"package_slug={report.package_slug}",
        f"semantic_version={report.semantic_version}",
        f"package_created={report.package_created}",
        f"release_created={report.release_created}",
        f"contracts_created={report.contracts_created}",
        f"contracts_existing={report.contracts_existing}",
        f"versions_created={report.versions_created}",
        f"versions_existing={report.versions_existing}",
        f"artifacts_created={report.artifacts_created}",
        f"artifacts_existing={report.artifacts_existing}",
    ]
    lines.extend(f"warning={warning}" for warning in report.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Import a local owner-repo manifest and print a concise summary."""
    parser = argparse.ArgumentParser(
        prog="python -m contracting_hub.services.contract_imports",
        description="Import a local xian.contract_bundle.v1 manifest into the catalog.",
    )
    parser.add_argument("manifest_path", help="Path to a contract-bundle.json manifest.")
    parser.add_argument(
        "--package-kind",
        default=ContractPackageKind.PRODUCT.value,
        choices=[member.value for member in ContractPackageKind],
        help="Package kind to use when the package must be created.",
    )
    parser.add_argument(
        "--status",
        default=PublicationStatus.PUBLISHED.value,
        choices=[member.value for member in PublicationStatus],
        help="Publication status for newly imported package, release, and contract versions.",
    )
    args = parser.parse_args(argv)

    with session_scope() as session:
        report = import_contract_bundle_manifest(
            session=session,
            manifest_path=args.manifest_path,
            package_kind=args.package_kind,
            package_status=args.status,
            release_status=args.status,
            contract_status=args.status,
        )
    print(_format_import_report(report))
    return 0


__all__ = [
    "BUNDLE_MANIFEST_SCHEMA",
    "BUNDLE_MANIFEST_SCHEMA_VERSION",
    "BundleManifest",
    "BundleManifestContract",
    "ContractBundleManifestImportReport",
    "ContractImportError",
    "ContractImportErrorCode",
    "import_contract_bundle_manifest",
    "load_contract_bundle_manifest",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
