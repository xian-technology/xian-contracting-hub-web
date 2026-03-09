"""Application metadata shared across modules."""

from urllib.parse import quote, urlencode

APP_NAME = "contracting-hub"
HOME_ROUTE = "/"
BROWSE_ROUTE = "/browse"
DEVELOPER_LEADERBOARD_ROUTE = "/developers"
LOGIN_ROUTE = "/login"
REGISTER_ROUTE = "/register"
PROFILE_SETTINGS_ROUTE = "/settings/profile"
DEPLOYMENT_HISTORY_ROUTE = "/settings/deployments"
CONTRACT_DETAIL_ROUTE = "/contracts/[slug]"
DEVELOPER_PROFILE_ROUTE = "/developers/[username]"
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


def build_developer_profile_path(username: str | None) -> str:
    """Build the canonical public developer-profile URL for one username."""
    normalized_username = str(username or "").strip().lower().lstrip("@")
    if not normalized_username:
        return DEVELOPER_LEADERBOARD_ROUTE
    return f"/developers/{quote(normalized_username)}"


__all__ = [
    "APP_NAME",
    "BROWSE_ROUTE",
    "CONTRACT_DETAIL_ROUTE",
    "DEVELOPER_PROFILE_ROUTE",
    "DEVELOPER_LEADERBOARD_ROUTE",
    "DEPLOYMENT_HISTORY_ROUTE",
    "HOME_BADGE_TEXT",
    "HOME_ROUTE",
    "LOGIN_ROUTE",
    "PROFILE_SETTINGS_ROUTE",
    "REGISTER_ROUTE",
    "build_developer_profile_path",
    "HOME_TAGLINE",
    "build_contract_detail_path",
]
