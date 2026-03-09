import pytest

from contracting_hub.models import PublicationStatus
from contracting_hub.services.stars import (
    ContractStarServiceError,
    ContractStarServiceErrorCode,
    contract_status_supports_stars,
)


@pytest.mark.parametrize(
    ("status", "supports_stars"),
    [
        (PublicationStatus.PUBLISHED, True),
        (PublicationStatus.DEPRECATED, True),
        (PublicationStatus.DRAFT, False),
        (PublicationStatus.ARCHIVED, False),
    ],
)
def test_contract_status_supports_stars_only_for_public_contracts(
    status: PublicationStatus,
    supports_stars: bool,
) -> None:
    assert contract_status_supports_stars(status) is supports_stars


def test_contract_star_service_error_serializes_stable_payload() -> None:
    error = ContractStarServiceError(
        ContractStarServiceErrorCode.CONTRACT_NOT_STARABLE,
        "Only public contracts can be starred.",
        field="contract_slug",
        details={"contract_slug": "escrow"},
    )

    assert error.as_payload() == {
        "code": "contract_not_starable",
        "field": "contract_slug",
        "message": "Only public contracts can be starred.",
        "details": {"contract_slug": "escrow"},
    }
