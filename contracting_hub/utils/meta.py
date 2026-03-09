"""Application metadata shared across modules."""

from urllib.parse import urlencode

APP_NAME = "contracting-hub"
HOME_ROUTE = "/"
BROWSE_ROUTE = "/browse"
LOGIN_ROUTE = "/login"
REGISTER_ROUTE = "/register"
CONTRACT_DETAIL_ROUTE = "/contracts/[slug]"
HOME_BADGE_TEXT = "Xian Ecosystem"
HOME_TAGLINE = "Curated smart contracts, version history, and deployment workflows."


def build_contract_detail_path(
    slug: str,
    *,
    semantic_version: str | None = None,
) -> str:
    """Build the canonical public detail URL for one contract slug."""
    path = f"/contracts/{slug}"
    if semantic_version is None:
        return path

    normalized_version = semantic_version.strip()
    if not normalized_version:
        return path

    return f"{path}?{urlencode({'version': normalized_version})}"


__all__ = [
    "APP_NAME",
    "BROWSE_ROUTE",
    "CONTRACT_DETAIL_ROUTE",
    "HOME_BADGE_TEXT",
    "HOME_ROUTE",
    "LOGIN_ROUTE",
    "REGISTER_ROUTE",
    "HOME_TAGLINE",
    "build_contract_detail_path",
]
