from __future__ import annotations

from datetime import datetime, timezone

from contracting_hub.utils import build_contract_rating_display, format_contract_calendar_date
from contracting_hub.utils.contract_catalog import ContractRatingDisplay


def test_build_contract_rating_display_formats_empty_and_populated_states() -> None:
    assert build_contract_rating_display(
        average_rating=None,
        rating_count=0,
    ) == ContractRatingDisplay(
        headline="No ratings yet",
        detail="",
        empty=True,
    )

    assert build_contract_rating_display(
        average_rating=4.25,
        rating_count=3,
    ) == ContractRatingDisplay(
        headline="4.2 avg",
        detail="3 ratings",
        empty=False,
    )


def test_format_contract_calendar_date_returns_pending_or_compact_label() -> None:
    assert format_contract_calendar_date(None) == "Pending"
    assert (
        format_contract_calendar_date(
            datetime(2026, 3, 9, 14, 30, tzinfo=timezone.utc),
        )
        == "Mar 9, 2026"
    )
