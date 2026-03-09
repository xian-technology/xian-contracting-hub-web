"""Service helpers for contract rating workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from contracting_hub.models import PublicationStatus, Rating, UserStatus
from contracting_hub.repositories import RatingRepository

MAX_CONTRACT_RATING_NOTE_LENGTH = 500
MIN_CONTRACT_RATING_SCORE = 1
MAX_CONTRACT_RATING_SCORE = 5
RATEABLE_CONTRACT_STATUSES: tuple[PublicationStatus, ...] = (
    PublicationStatus.PUBLISHED,
    PublicationStatus.DEPRECATED,
)


@dataclass(frozen=True)
class ContractRatingSubmissionResult:
    """Result payload returned after a contract rating is created or updated."""

    contract_id: int
    contract_slug: str
    score: int
    note: str | None
    rating_count: int
    average_score: float | None
    updated_existing: bool


class ContractRatingServiceErrorCode(StrEnum):
    """Stable rating-service failures exposed to callers."""

    CONTRACT_NOT_FOUND = "contract_not_found"
    CONTRACT_NOT_RATEABLE = "contract_not_rateable"
    INVALID_NOTE = "invalid_note"
    INVALID_SCORE = "invalid_score"
    USER_DISABLED = "user_disabled"
    USER_NOT_FOUND = "user_not_found"


class ContractRatingServiceError(ValueError):
    """Structured service error for contract rating workflows."""

    def __init__(
        self,
        code: ContractRatingServiceErrorCode,
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


def submit_contract_rating(
    *,
    session: Session,
    user_id: int,
    contract_slug: str,
    score: int | str,
    note: str | None = None,
) -> ContractRatingSubmissionResult:
    """Create or update the current user's rating for one public contract."""
    repository = RatingRepository(session)
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise ContractRatingServiceError(
            ContractRatingServiceErrorCode.USER_NOT_FOUND,
            f"User {user_id!r} does not exist.",
            field="user_id",
            details={"user_id": user_id},
        )
    if user.status is not UserStatus.ACTIVE:
        raise ContractRatingServiceError(
            ContractRatingServiceErrorCode.USER_DISABLED,
            "Only active users can rate contracts.",
            field="user_id",
            details={"user_id": user_id, "status": user.status.value},
        )

    contract = repository.get_contract_by_slug(contract_slug)
    if contract is None:
        raise ContractRatingServiceError(
            ContractRatingServiceErrorCode.CONTRACT_NOT_FOUND,
            f"Contract {contract_slug!r} does not exist.",
            field="contract_slug",
            details={"contract_slug": contract_slug},
        )
    if not contract_status_supports_ratings(contract.status):
        raise ContractRatingServiceError(
            ContractRatingServiceErrorCode.CONTRACT_NOT_RATEABLE,
            "Only public contracts can be rated.",
            field="contract_slug",
            details={
                "contract_slug": contract_slug,
                "status": contract.status.value,
            },
        )

    normalized_score = normalize_contract_rating_score(score)
    normalized_note = normalize_contract_rating_note(note)
    contract_id = _require_persisted_id(contract.id, label="contract")
    persisted_user_id = _require_persisted_id(user.id, label="user")
    existing_rating = repository.get_rating(user_id=persisted_user_id, contract_id=contract_id)
    if existing_rating is not None:
        existing_rating.score = normalized_score
        existing_rating.note = normalized_note
        session.commit()
        return _build_submission_result(
            repository,
            contract_id=contract_id,
            contract_slug=contract.slug,
            score=normalized_score,
            note=normalized_note,
            updated_existing=True,
        )

    try:
        repository.add_rating(
            Rating(
                user_id=persisted_user_id,
                contract_id=contract_id,
                score=normalized_score,
                note=normalized_note,
            )
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _looks_like_duplicate_rating_violation(error):
            recovered_rating = repository.get_rating(
                user_id=persisted_user_id,
                contract_id=contract_id,
            )
            if recovered_rating is not None:
                recovered_rating.score = normalized_score
                recovered_rating.note = normalized_note
                session.commit()
                return _build_submission_result(
                    repository,
                    contract_id=contract_id,
                    contract_slug=contract.slug,
                    score=normalized_score,
                    note=normalized_note,
                    updated_existing=True,
                )
        raise

    return _build_submission_result(
        repository,
        contract_id=contract_id,
        contract_slug=contract.slug,
        score=normalized_score,
        note=normalized_note,
        updated_existing=False,
    )


def contract_status_supports_ratings(status: PublicationStatus) -> bool:
    """Return whether a contract in the given status accepts ratings."""
    return status in RATEABLE_CONTRACT_STATUSES


def normalize_contract_rating_score(score: int | str) -> int:
    """Validate and normalize a rating score from UI or API input."""
    normalized_score: int
    if isinstance(score, bool):
        raise _invalid_score_error(score)
    if isinstance(score, int):
        normalized_score = score
    elif isinstance(score, str):
        stripped_score = score.strip()
        if not stripped_score.isdigit():
            raise _invalid_score_error(score)
        normalized_score = int(stripped_score)
    else:
        raise _invalid_score_error(score)

    if MIN_CONTRACT_RATING_SCORE <= normalized_score <= MAX_CONTRACT_RATING_SCORE:
        return normalized_score
    raise _invalid_score_error(score)


def normalize_contract_rating_note(note: str | None) -> str | None:
    """Trim an optional rating note and enforce the stored length limit."""
    if note is None:
        return None
    if not isinstance(note, str):
        raise ContractRatingServiceError(
            ContractRatingServiceErrorCode.INVALID_NOTE,
            "Rating note must be a string.",
            field="note",
            details={"expected_type": "str"},
        )

    normalized_note = note.strip()
    if not normalized_note:
        return None
    if len(normalized_note) <= MAX_CONTRACT_RATING_NOTE_LENGTH:
        return normalized_note

    raise ContractRatingServiceError(
        ContractRatingServiceErrorCode.INVALID_NOTE,
        "Rating note must be 500 characters or fewer.",
        field="note",
        details={"max_length": MAX_CONTRACT_RATING_NOTE_LENGTH},
    )


def _build_submission_result(
    repository: RatingRepository,
    *,
    contract_id: int,
    contract_slug: str,
    score: int,
    note: str | None,
    updated_existing: bool,
) -> ContractRatingSubmissionResult:
    rating_count, average_score = repository.get_contract_rating_stats(contract_id)
    return ContractRatingSubmissionResult(
        contract_id=contract_id,
        contract_slug=contract_slug,
        score=score,
        note=note,
        rating_count=rating_count,
        average_score=average_score,
        updated_existing=updated_existing,
    )


def _invalid_score_error(score: object) -> ContractRatingServiceError:
    return ContractRatingServiceError(
        ContractRatingServiceErrorCode.INVALID_SCORE,
        "Rating score must be an integer between 1 and 5.",
        field="score",
        details={
            "score": score,
            "min": MIN_CONTRACT_RATING_SCORE,
            "max": MAX_CONTRACT_RATING_SCORE,
        },
    )


def _looks_like_duplicate_rating_violation(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return "uq_ratings_user_contract" in message or (
        "ratings.user_id, ratings.contract_id" in message
    )


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is None:
        raise RuntimeError(f"{label} must be persisted before ratings run.")
    return value


__all__ = [
    "ContractRatingServiceError",
    "ContractRatingServiceErrorCode",
    "ContractRatingSubmissionResult",
    "MAX_CONTRACT_RATING_NOTE_LENGTH",
    "MAX_CONTRACT_RATING_SCORE",
    "MIN_CONTRACT_RATING_SCORE",
    "RATEABLE_CONTRACT_STATUSES",
    "contract_status_supports_ratings",
    "normalize_contract_rating_note",
    "normalize_contract_rating_score",
    "submit_contract_rating",
]
