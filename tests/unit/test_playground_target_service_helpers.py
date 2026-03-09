import pytest

from contracting_hub.services.playground_targets import (
    PlaygroundTargetServiceError,
    PlaygroundTargetServiceErrorCode,
    normalize_playground_target_label,
    normalize_saved_playground_id,
)


def test_normalize_playground_target_label_trims_and_rejects_blank_values() -> None:
    assert normalize_playground_target_label("  Sandbox  ") == "Sandbox"

    with pytest.raises(PlaygroundTargetServiceError) as error:
        normalize_playground_target_label("   ")

    assert error.value.code is PlaygroundTargetServiceErrorCode.INVALID_LABEL
    assert error.value.field == "label"


def test_normalize_playground_target_label_rejects_invalid_types_and_lengths() -> None:
    with pytest.raises(PlaygroundTargetServiceError) as invalid_type_error:
        normalize_playground_target_label(123)  # type: ignore[arg-type]

    with pytest.raises(PlaygroundTargetServiceError) as invalid_length_error:
        normalize_playground_target_label("x" * 101)

    assert invalid_type_error.value.code is PlaygroundTargetServiceErrorCode.INVALID_LABEL
    assert invalid_length_error.value.code is PlaygroundTargetServiceErrorCode.INVALID_LABEL


@pytest.mark.parametrize(
    ("playground_id", "normalized_playground_id"),
    [
        (" target-123 ", "target-123"),
        ("Sandbox_01", "Sandbox_01"),
        ("alpha.beta-01", "alpha.beta-01"),
    ],
)
def test_normalize_saved_playground_id_accepts_valid_values(
    playground_id: str,
    normalized_playground_id: str,
) -> None:
    assert normalize_saved_playground_id(playground_id) == normalized_playground_id


@pytest.mark.parametrize(
    "playground_id",
    [
        "",
        "  ",
        "ab",
        "-target-123",
        "target id",
        "target/123",
    ],
)
def test_normalize_saved_playground_id_rejects_invalid_shapes(playground_id: str) -> None:
    with pytest.raises(PlaygroundTargetServiceError) as error:
        normalize_saved_playground_id(playground_id)

    assert error.value.code is PlaygroundTargetServiceErrorCode.INVALID_PLAYGROUND_ID
    assert error.value.field == "playground_id"


def test_playground_target_service_error_serializes_stable_payload() -> None:
    error = PlaygroundTargetServiceError(
        PlaygroundTargetServiceErrorCode.DUPLICATE_PLAYGROUND_ID,
        "This playground ID is already saved to your account.",
        field="playground_id",
        details={"playground_id": "target-123"},
    )

    assert error.as_payload() == {
        "code": "duplicate_playground_id",
        "field": "playground_id",
        "message": "This playground ID is already saved to your account.",
        "details": {"playground_id": "target-123"},
    }
