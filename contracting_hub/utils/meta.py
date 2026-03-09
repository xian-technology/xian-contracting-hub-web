"""Application metadata shared across modules."""

APP_NAME = "contracting-hub"
HOME_ROUTE = "/"
BROWSE_ROUTE = "/browse"
CONTRACT_DETAIL_ROUTE = "/contracts/[slug]"
HOME_BADGE_TEXT = "Xian Ecosystem"
HOME_TAGLINE = "Curated smart contracts, version history, and deployment workflows."


def build_contract_detail_path(slug: str) -> str:
    """Build the canonical public detail URL for one contract slug."""
    return f"/contracts/{slug}"


__all__ = [
    "APP_NAME",
    "BROWSE_ROUTE",
    "CONTRACT_DETAIL_ROUTE",
    "HOME_BADGE_TEXT",
    "HOME_ROUTE",
    "HOME_TAGLINE",
    "build_contract_detail_path",
]
