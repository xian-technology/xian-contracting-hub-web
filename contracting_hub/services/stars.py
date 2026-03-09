"""Service helpers for contract star and favorite workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from contracting_hub.models import PublicationStatus, Star, UserStatus
from contracting_hub.repositories import StarRepository

STARABLE_CONTRACT_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)


@dataclass(frozen=True)
class ContractStarToggleResult:
    """Result payload returned after a contract star state changes."""

    contract_id: int
    contract_slug: str
    star_count: int
    starred_by_user: bool


class ContractStarServiceErrorCode(StrEnum):
    """Stable star-service failures exposed to callers."""

    CONTRACT_NOT_FOUND = "contract_not_found"
    CONTRACT_NOT_STARABLE = "contract_not_starable"
    USER_DISABLED = "user_disabled"
    USER_NOT_FOUND = "user_not_found"


class ContractStarServiceError(ValueError):
    """Structured service error for contract favorite workflows."""

    def __init__(
        self,
        code: ContractStarServiceErrorCode,
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


def toggle_contract_star(
    *,
    session: Session,
    user_id: int,
    contract_slug: str,
) -> ContractStarToggleResult:
    """Toggle the current user's favorite state for one public contract."""
    repository = StarRepository(session)
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise ContractStarServiceError(
            ContractStarServiceErrorCode.USER_NOT_FOUND,
            f"User {user_id!r} does not exist.",
            field="user_id",
            details={"user_id": user_id},
        )
    if user.status is not UserStatus.ACTIVE:
        raise ContractStarServiceError(
            ContractStarServiceErrorCode.USER_DISABLED,
            "Only active users can star contracts.",
            field="user_id",
            details={"user_id": user_id, "status": user.status.value},
        )

    contract = repository.get_contract_by_slug(contract_slug)
    if contract is None:
        raise ContractStarServiceError(
            ContractStarServiceErrorCode.CONTRACT_NOT_FOUND,
            f"Contract {contract_slug!r} does not exist.",
            field="contract_slug",
            details={"contract_slug": contract_slug},
        )
    if not contract_status_supports_stars(contract.status):
        raise ContractStarServiceError(
            ContractStarServiceErrorCode.CONTRACT_NOT_STARABLE,
            "Only public contracts can be starred.",
            field="contract_slug",
            details={
                "contract_slug": contract_slug,
                "status": contract.status.value,
            },
        )

    contract_id = _require_persisted_id(contract.id, label="contract")
    persisted_user_id = _require_persisted_id(user.id, label="user")
    existing_star = repository.get_star(user_id=persisted_user_id, contract_id=contract_id)
    if existing_star is not None:
        repository.delete_star(existing_star)
        session.commit()
        return _build_toggle_result(
            repository,
            contract_id=contract_id,
            contract_slug=contract.slug,
            starred_by_user=False,
        )

    try:
        repository.add_star(Star(user_id=persisted_user_id, contract_id=contract_id))
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _looks_like_duplicate_star_violation(error):
            recovered_star = repository.get_star(user_id=persisted_user_id, contract_id=contract_id)
            if recovered_star is not None:
                return _build_toggle_result(
                    repository,
                    contract_id=contract_id,
                    contract_slug=contract.slug,
                    starred_by_user=True,
                )
        raise

    return _build_toggle_result(
        repository,
        contract_id=contract_id,
        contract_slug=contract.slug,
        starred_by_user=True,
    )


def contract_status_supports_stars(status: PublicationStatus) -> bool:
    """Return whether a contract in the given status accepts favorites."""
    return status in STARABLE_CONTRACT_STATUSES


def _build_toggle_result(
    repository: StarRepository,
    *,
    contract_id: int,
    contract_slug: str,
    starred_by_user: bool,
) -> ContractStarToggleResult:
    return ContractStarToggleResult(
        contract_id=contract_id,
        contract_slug=contract_slug,
        star_count=repository.count_contract_stars(contract_id),
        starred_by_user=starred_by_user,
    )


def _looks_like_duplicate_star_violation(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return "uq_stars_user_contract" in message or "stars.user_id, stars.contract_id" in message


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is None:
        raise RuntimeError(f"{label} must be persisted before star toggles run.")
    return value


__all__ = [
    "ContractStarServiceError",
    "ContractStarServiceErrorCode",
    "ContractStarToggleResult",
    "STARABLE_CONTRACT_STATUSES",
    "contract_status_supports_stars",
    "toggle_contract_star",
]
