"""Shared presentation helpers for contract catalog UI surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ContractRatingDisplay:
    """Serialized rating summary content for UI components."""

    headline: str
    detail: str
    empty: bool


def format_contract_calendar_date(value: datetime | None) -> str:
    """Render one timestamp as a compact calendar label."""
    if value is None:
        return "Pending"
    return value.strftime("%b %d, %Y").replace(" 0", " ")


def build_contract_rating_display(
    *,
    average_rating: float | None,
    rating_count: int,
) -> ContractRatingDisplay:
    """Build a compact rating summary for cards and detail metadata."""
    if rating_count == 0 or average_rating is None:
        return ContractRatingDisplay(
            headline="No ratings yet",
            detail="",
            empty=True,
        )

    rating_label = "1 rating" if rating_count == 1 else f"{rating_count} ratings"
    return ContractRatingDisplay(
        headline=f"{average_rating:.1f} avg",
        detail=rating_label,
        empty=False,
    )


__all__ = [
    "ContractRatingDisplay",
    "build_contract_rating_display",
    "format_contract_calendar_date",
]
