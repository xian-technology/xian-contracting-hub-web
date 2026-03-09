import pytest

from contracting_hub.models import PublicationStatus
from contracting_hub.services.ratings import (
    ContractRatingServiceError,
    ContractRatingServiceErrorCode,
    contract_status_supports_ratings,
    normalize_contract_rating_note,
    normalize_contract_rating_score,
)


@pytest.mark.parametrize(
    ("status", "supports_ratings"),
    [
        (PublicationStatus.PUBLISHED, True),
        (PublicationStatus.DEPRECATED, True),
        (PublicationStatus.DRAFT, False),
        (PublicationStatus.ARCHIVED, False),
    ],
)
def test_contract_status_supports_ratings_only_for_public_contracts(
    status: PublicationStatus,
    supports_ratings: bool,
) -> None:
    assert contract_status_supports_ratings(status) is supports_ratings


@pytest.mark.parametrize(
    ("score", "normalized_score"),
    [
        (1, 1),
        (5, 5),
        (" 4 ", 4),
    ],
)
def test_normalize_contract_rating_score_accepts_valid_inputs(
    score: int | str,
    normalized_score: int,
) -> None:
    assert normalize_contract_rating_score(score) == normalized_score


@pytest.mark.parametrize("score", [0, 6, "0", "6", "4.5", "", False, object()])
def test_normalize_contract_rating_score_rejects_out_of_range_or_invalid_types(
    score: object,
) -> None:
    with pytest.raises(ContractRatingServiceError) as error:
        normalize_contract_rating_score(score)  # type: ignore[arg-type]

    assert error.value.code is ContractRatingServiceErrorCode.INVALID_SCORE
    assert error.value.field == "score"


def test_normalize_contract_rating_note_trims_blank_values_to_none() -> None:
    assert normalize_contract_rating_note(None) is None
    assert normalize_contract_rating_note("   ") is None
    assert normalize_contract_rating_note("  Useful in production.  ") == "Useful in production."


def test_normalize_contract_rating_note_rejects_invalid_types_and_lengths() -> None:
    with pytest.raises(ContractRatingServiceError) as invalid_type_error:
        normalize_contract_rating_note(123)  # type: ignore[arg-type]

    with pytest.raises(ContractRatingServiceError) as invalid_length_error:
        normalize_contract_rating_note("x" * 501)

    assert invalid_type_error.value.code is ContractRatingServiceErrorCode.INVALID_NOTE
    assert invalid_length_error.value.code is ContractRatingServiceErrorCode.INVALID_NOTE


def test_contract_rating_service_error_serializes_stable_payload() -> None:
    error = ContractRatingServiceError(
        ContractRatingServiceErrorCode.CONTRACT_NOT_RATEABLE,
        "Only public contracts can be rated.",
        field="contract_slug",
        details={"contract_slug": "escrow"},
    )

    assert error.as_payload() == {
        "code": "contract_not_rateable",
        "field": "contract_slug",
        "message": "Only public contracts can be rated.",
        "details": {"contract_slug": "escrow"},
    }
