"""Admin helpers for directional contract-relation management."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import aliased, selectinload
from sqlmodel import Session, select

from contracting_hub.database import session_scope
from contracting_hub.models import (
    AdminAuditLog,
    Contract,
    ContractRelation,
    ContractRelationType,
    PublicationStatus,
)
from contracting_hub.services.auth import require_admin_user
from contracting_hub.services.contract_metadata import (
    ContractMetadataValidationError,
    validate_relation_type,
)
from contracting_hub.services.contract_versions import PUBLIC_VERSION_STATUSES
from contracting_hub.utils.meta import (
    build_admin_contract_edit_path,
    build_admin_contract_relations_path,
    build_admin_contract_versions_path,
    build_contract_detail_path,
)

MAX_RELATION_NOTE_LENGTH = 255


class AdminContractRelationManagerServiceErrorCode(StrEnum):
    """Stable admin relation-manager failures exposed to callers."""

    CONTRACT_NOT_FOUND = "contract_not_found"
    DUPLICATE_RELATION = "duplicate_relation"
    INVALID_NOTE = "invalid_note"
    INVALID_RELATION_ID = "invalid_relation_id"
    INVALID_RELATION_TYPE = "invalid_relation_type"
    INVALID_TARGET_CONTRACT = "invalid_target_contract"
    RELATION_NOT_FOUND = "relation_not_found"
    SELF_RELATION = "self_relation"


class AdminContractRelationManagerServiceError(ValueError):
    """Structured service error for admin relation-management workflows."""

    def __init__(
        self,
        code: AdminContractRelationManagerServiceErrorCode,
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
class AdminContractRelationTargetOption:
    """Selectable target contract rendered in the admin relation form."""

    contract_id: int
    slug: str
    display_name: str
    contract_name: str
    status: PublicationStatus


@dataclass(frozen=True)
class AdminContractRelationEntry:
    """One directional relation row rendered in the admin manager."""

    relation_id: int
    relation_type: ContractRelationType
    relation_label: str
    note: str | None
    counterpart_contract_id: int
    counterpart_slug: str
    counterpart_display_name: str
    counterpart_contract_name: str
    counterpart_status: PublicationStatus
    public_detail_href: str | None
    relation_manager_href: str


@dataclass(frozen=True)
class AdminContractRelationManagerSnapshot:
    """Loaded relation-manager data for one contract."""

    contract_id: int | None
    slug: str
    display_name: str
    contract_name: str
    contract_status: PublicationStatus
    latest_public_version: str | None
    public_detail_href: str | None
    edit_href: str
    versions_href: str
    outgoing_relations: tuple[AdminContractRelationEntry, ...]
    incoming_relations: tuple[AdminContractRelationEntry, ...]
    target_options: tuple[AdminContractRelationTargetOption, ...]


def build_empty_admin_contract_relation_manager_snapshot(
    *,
    contract_slug: str | None = None,
) -> AdminContractRelationManagerSnapshot:
    """Return a stable empty relation-manager snapshot."""
    normalized_slug = str(contract_slug or "").strip().lower()
    return AdminContractRelationManagerSnapshot(
        contract_id=None,
        slug=normalized_slug,
        display_name="",
        contract_name="",
        contract_status=PublicationStatus.DRAFT,
        latest_public_version=None,
        public_detail_href=None,
        edit_href=build_admin_contract_edit_path(normalized_slug),
        versions_href=build_admin_contract_versions_path(normalized_slug),
        outgoing_relations=(),
        incoming_relations=(),
        target_options=(),
    )


def load_admin_contract_relation_manager_snapshot(
    *,
    session: Session,
    contract_slug: str,
) -> AdminContractRelationManagerSnapshot:
    """Load directional relation data for the supplied contract slug."""
    contract = _require_contract_for_relation_manager(session, contract_slug=contract_slug)
    latest_public_version = (
        contract.latest_published_version.semantic_version
        if contract.latest_published_version is not None
        else None
    )
    return AdminContractRelationManagerSnapshot(
        contract_id=contract.id,
        slug=contract.slug,
        display_name=contract.display_name,
        contract_name=contract.contract_name,
        contract_status=contract.status,
        latest_public_version=latest_public_version,
        public_detail_href=_build_public_detail_href(contract),
        edit_href=build_admin_contract_edit_path(contract.slug),
        versions_href=build_admin_contract_versions_path(contract.slug),
        outgoing_relations=_load_outgoing_relations(session, contract_id=contract.id),
        incoming_relations=_load_incoming_relations(session, contract_id=contract.id),
        target_options=_load_target_options(session, current_contract_id=contract.id),
    )


def load_admin_contract_relation_manager_snapshot_safe(
    *,
    contract_slug: str | None = None,
) -> AdminContractRelationManagerSnapshot:
    """Load the relation manager while tolerating a missing or unmigrated database."""
    try:
        with session_scope() as session:
            return load_admin_contract_relation_manager_snapshot(
                session=session,
                contract_slug=str(contract_slug or "").strip().lower(),
            )
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_admin_contract_relation_manager_snapshot(contract_slug=contract_slug)


def create_admin_contract_relation(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
    target_contract_id: int | str | None,
    relation_type: ContractRelationType | str,
    note: str | None = None,
) -> ContractRelation:
    """Create one outgoing typed relation from the supplied contract."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    source_contract = _require_contract_for_relation_manager(session, contract_slug=contract_slug)
    target_contract = _require_target_contract(
        session,
        current_contract=source_contract,
        target_contract_id=target_contract_id,
    )
    normalized_relation_type = _normalize_relation_type(relation_type)
    normalized_note = normalize_admin_contract_relation_note(note)
    _assert_relation_is_unique(
        session,
        source_contract_id=source_contract.id,
        target_contract_id=target_contract.id,
        relation_type=normalized_relation_type,
    )

    relation = ContractRelation(
        source_contract_id=source_contract.id,
        target_contract_id=target_contract.id,
        relation_type=normalized_relation_type,
        note=normalized_note,
    )
    session.add(relation)
    session.flush()
    relation_id = _require_persisted_id(relation.id, label="relation")
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="create_contract_relation",
            entity_type="contract_relation",
            entity_id=relation_id,
            summary=(
                f"Added {normalized_relation_type.value} relation from "
                f"{source_contract.slug} to {target_contract.slug}."
            ),
            details={
                "source_contract_slug": source_contract.slug,
                "target_contract_slug": target_contract.slug,
                "relation_type": normalized_relation_type.value,
                "note": normalized_note,
            },
        )
    )
    session.commit()
    session.refresh(relation)
    return relation


def update_admin_contract_relation(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
    relation_id: int | str,
    target_contract_id: int | str | None,
    relation_type: ContractRelationType | str,
    note: str | None = None,
) -> ContractRelation:
    """Update one existing outgoing typed relation for the supplied contract."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    source_contract = _require_contract_for_relation_manager(session, contract_slug=contract_slug)
    relation = _require_relation(
        session,
        source_contract_id=source_contract.id,
        relation_id=relation_id,
    )
    target_contract = _require_target_contract(
        session,
        current_contract=source_contract,
        target_contract_id=target_contract_id,
    )
    normalized_relation_type = _normalize_relation_type(relation_type)
    normalized_note = normalize_admin_contract_relation_note(note)
    _assert_relation_is_unique(
        session,
        source_contract_id=source_contract.id,
        target_contract_id=target_contract.id,
        relation_type=normalized_relation_type,
        excluded_relation_id=relation.id,
    )

    previous_target_slug = relation.target_contract.slug
    previous_relation_type = relation.relation_type.value
    previous_note = relation.note

    relation.target_contract_id = target_contract.id
    relation.relation_type = normalized_relation_type
    relation.note = normalized_note
    session.add(relation)
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="update_contract_relation",
            entity_type="contract_relation",
            entity_id=relation.id,
            summary=(f"Updated relation from {source_contract.slug} to {target_contract.slug}."),
            details={
                "source_contract_slug": source_contract.slug,
                "previous_target_contract_slug": previous_target_slug,
                "target_contract_slug": target_contract.slug,
                "previous_relation_type": previous_relation_type,
                "relation_type": normalized_relation_type.value,
                "previous_note": previous_note,
                "note": normalized_note,
            },
        )
    )
    session.commit()
    session.refresh(relation)
    return relation


def delete_admin_contract_relation(
    *,
    session: Session,
    session_token: str | None,
    contract_slug: str,
    relation_id: int | str,
) -> None:
    """Delete one existing outgoing typed relation for the supplied contract."""
    admin_user = require_admin_user(session=session, session_token=session_token)
    source_contract = _require_contract_for_relation_manager(session, contract_slug=contract_slug)
    relation = _require_relation(
        session,
        source_contract_id=source_contract.id,
        relation_id=relation_id,
    )
    target_contract_slug = relation.target_contract.slug
    relation_type = relation.relation_type.value
    note = relation.note
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="delete_contract_relation",
            entity_type="contract_relation",
            entity_id=relation.id,
            summary=(
                f"Removed {relation_type} relation from {source_contract.slug} "
                f"to {target_contract_slug}."
            ),
            details={
                "source_contract_slug": source_contract.slug,
                "target_contract_slug": target_contract_slug,
                "relation_type": relation_type,
                "note": note,
            },
        )
    )
    session.delete(relation)
    session.commit()


def normalize_admin_contract_relation_note(note: str | None) -> str | None:
    """Normalize one optional admin relation note for storage."""
    if note is None:
        return None
    if not isinstance(note, str):
        raise AdminContractRelationManagerServiceError(
            AdminContractRelationManagerServiceErrorCode.INVALID_NOTE,
            "Relation note must be a string.",
            field="note",
            details={"expected_type": "str"},
        )
    normalized = " ".join(note.split()).strip()
    if not normalized:
        return None
    if len(normalized) > MAX_RELATION_NOTE_LENGTH:
        raise AdminContractRelationManagerServiceError(
            AdminContractRelationManagerServiceErrorCode.INVALID_NOTE,
            f"Relation note must be {MAX_RELATION_NOTE_LENGTH} characters or fewer.",
            field="note",
            details={"max_length": MAX_RELATION_NOTE_LENGTH},
        )
    return normalized


def format_admin_contract_relation_type_label(relation_type: ContractRelationType) -> str:
    """Return the human-readable label for one directional relation type."""
    labels = {
        ContractRelationType.COMPANION: "Companion",
        ContractRelationType.DEPENDS_ON: "Depends on",
        ContractRelationType.EXAMPLE_FOR: "Example for",
        ContractRelationType.EXTENDS: "Extends",
        ContractRelationType.SUPERSEDES: "Supersedes",
    }
    return labels[relation_type]


def _require_contract_for_relation_manager(
    session: Session,
    *,
    contract_slug: str,
) -> Contract:
    statement = (
        select(Contract)
        .where(Contract.slug == str(contract_slug).strip().lower())
        .options(selectinload(Contract.latest_published_version))
    )
    contract = session.exec(statement).first()
    if contract is not None:
        return contract
    raise AdminContractRelationManagerServiceError(
        AdminContractRelationManagerServiceErrorCode.CONTRACT_NOT_FOUND,
        f"Contract {contract_slug!r} could not be found.",
        field="contract_slug",
        details={"contract_slug": contract_slug},
    )


def _load_outgoing_relations(
    session: Session,
    *,
    contract_id: int,
) -> tuple[AdminContractRelationEntry, ...]:
    target_contract = aliased(Contract)
    statement = (
        select(ContractRelation)
        .join(target_contract, target_contract.id == ContractRelation.target_contract_id)
        .where(ContractRelation.source_contract_id == contract_id)
        .options(
            selectinload(ContractRelation.target_contract).selectinload(
                Contract.latest_published_version
            )
        )
        .order_by(
            ContractRelation.relation_type.asc(),
            target_contract.display_name.asc(),
            ContractRelation.id.asc(),
        )
    )
    return tuple(
        _build_relation_entry(
            relation,
            counterpart_contract=relation.target_contract,
        )
        for relation in session.exec(statement).all()
    )


def _load_incoming_relations(
    session: Session,
    *,
    contract_id: int,
) -> tuple[AdminContractRelationEntry, ...]:
    source_contract = aliased(Contract)
    statement = (
        select(ContractRelation)
        .join(source_contract, source_contract.id == ContractRelation.source_contract_id)
        .where(ContractRelation.target_contract_id == contract_id)
        .options(
            selectinload(ContractRelation.source_contract).selectinload(
                Contract.latest_published_version
            )
        )
        .order_by(
            ContractRelation.relation_type.asc(),
            source_contract.display_name.asc(),
            ContractRelation.id.asc(),
        )
    )
    return tuple(
        _build_relation_entry(
            relation,
            counterpart_contract=relation.source_contract,
        )
        for relation in session.exec(statement).all()
    )


def _load_target_options(
    session: Session,
    *,
    current_contract_id: int,
) -> tuple[AdminContractRelationTargetOption, ...]:
    statement = (
        select(Contract)
        .where(Contract.id != current_contract_id)
        .order_by(Contract.display_name.asc(), Contract.contract_name.asc())
    )
    return tuple(
        AdminContractRelationTargetOption(
            contract_id=contract.id,
            slug=contract.slug,
            display_name=contract.display_name,
            contract_name=contract.contract_name,
            status=contract.status,
        )
        for contract in session.exec(statement).all()
    )


def _build_relation_entry(
    relation: ContractRelation,
    *,
    counterpart_contract: Contract,
) -> AdminContractRelationEntry:
    return AdminContractRelationEntry(
        relation_id=_require_persisted_id(relation.id, label="relation"),
        relation_type=relation.relation_type,
        relation_label=format_admin_contract_relation_type_label(relation.relation_type),
        note=relation.note,
        counterpart_contract_id=_require_persisted_id(
            counterpart_contract.id,
            label="counterpart_contract",
        ),
        counterpart_slug=counterpart_contract.slug,
        counterpart_display_name=counterpart_contract.display_name,
        counterpart_contract_name=counterpart_contract.contract_name,
        counterpart_status=counterpart_contract.status,
        public_detail_href=_build_public_detail_href(counterpart_contract),
        relation_manager_href=build_admin_contract_relations_path(counterpart_contract.slug),
    )


def _build_public_detail_href(contract: Contract) -> str | None:
    if contract.status not in PUBLIC_VERSION_STATUSES:
        return None
    if contract.latest_published_version is None:
        return None
    return build_contract_detail_path(contract.slug)


def _require_target_contract(
    session: Session,
    *,
    current_contract: Contract,
    target_contract_id: int | str | None,
) -> Contract:
    normalized_target_contract_id = _normalize_contract_id(
        target_contract_id,
        field="target_contract_id",
    )
    if normalized_target_contract_id == current_contract.id:
        raise AdminContractRelationManagerServiceError(
            AdminContractRelationManagerServiceErrorCode.SELF_RELATION,
            "Contracts cannot be related to themselves.",
            field="target_contract_id",
            details={"contract_slug": current_contract.slug},
        )
    statement = (
        select(Contract)
        .where(Contract.id == normalized_target_contract_id)
        .options(selectinload(Contract.latest_published_version))
    )
    target_contract = session.exec(statement).first()
    if target_contract is not None:
        return target_contract
    raise AdminContractRelationManagerServiceError(
        AdminContractRelationManagerServiceErrorCode.INVALID_TARGET_CONTRACT,
        "Select a valid related contract.",
        field="target_contract_id",
        details={"target_contract_id": normalized_target_contract_id},
    )


def _require_relation(
    session: Session,
    *,
    source_contract_id: int,
    relation_id: int | str,
) -> ContractRelation:
    normalized_relation_id = _normalize_contract_id(relation_id, field="relation_id")
    statement = (
        select(ContractRelation)
        .where(ContractRelation.id == normalized_relation_id)
        .where(ContractRelation.source_contract_id == source_contract_id)
        .options(selectinload(ContractRelation.target_contract))
    )
    relation = session.exec(statement).first()
    if relation is not None:
        return relation
    raise AdminContractRelationManagerServiceError(
        AdminContractRelationManagerServiceErrorCode.RELATION_NOT_FOUND,
        "The requested outgoing relation could not be found.",
        field="relation_id",
        details={"relation_id": normalized_relation_id},
    )


def _normalize_contract_id(value: int | str | None, *, field: str) -> int:
    if isinstance(value, int):
        if value > 0:
            return value
    elif isinstance(value, str):
        normalized = value.strip()
        if normalized.isdigit() and int(normalized) > 0:
            return int(normalized)
    raise AdminContractRelationManagerServiceError(
        (
            AdminContractRelationManagerServiceErrorCode.INVALID_RELATION_ID
            if field == "relation_id"
            else AdminContractRelationManagerServiceErrorCode.INVALID_TARGET_CONTRACT
        ),
        "Select a valid relation record." if field == "relation_id" else "Select a contract.",
        field=field,
    )


def _normalize_relation_type(
    relation_type: ContractRelationType | str,
) -> ContractRelationType:
    try:
        return validate_relation_type(relation_type)
    except ContractMetadataValidationError as error:
        raise AdminContractRelationManagerServiceError(
            AdminContractRelationManagerServiceErrorCode.INVALID_RELATION_TYPE,
            str(error),
            field=error.field,
            details=error.details,
        ) from error


def _assert_relation_is_unique(
    session: Session,
    *,
    source_contract_id: int,
    target_contract_id: int,
    relation_type: ContractRelationType,
    excluded_relation_id: int | None = None,
) -> None:
    statement = (
        select(ContractRelation)
        .where(ContractRelation.source_contract_id == source_contract_id)
        .where(ContractRelation.target_contract_id == target_contract_id)
        .where(ContractRelation.relation_type == relation_type)
    )
    if excluded_relation_id is not None:
        statement = statement.where(ContractRelation.id != excluded_relation_id)
    duplicate = session.exec(statement).first()
    if duplicate is None:
        return
    raise AdminContractRelationManagerServiceError(
        AdminContractRelationManagerServiceErrorCode.DUPLICATE_RELATION,
        "That typed relation already exists for this contract pair.",
        field="relation_type",
        details={
            "source_contract_id": source_contract_id,
            "target_contract_id": target_contract_id,
            "relation_type": relation_type.value,
        },
    )


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is None:
        raise RuntimeError(f"Expected {label} to have a persisted id.")
    return value


__all__ = [
    "AdminContractRelationEntry",
    "AdminContractRelationManagerServiceError",
    "AdminContractRelationManagerServiceErrorCode",
    "AdminContractRelationManagerSnapshot",
    "AdminContractRelationTargetOption",
    "MAX_RELATION_NOTE_LENGTH",
    "build_empty_admin_contract_relation_manager_snapshot",
    "create_admin_contract_relation",
    "delete_admin_contract_relation",
    "format_admin_contract_relation_type_label",
    "load_admin_contract_relation_manager_snapshot",
    "load_admin_contract_relation_manager_snapshot_safe",
    "normalize_admin_contract_relation_note",
    "update_admin_contract_relation",
]
