from __future__ import annotations

from datetime import datetime, timezone

from reflex import constants
from reflex.istate.data import RouterData

from contracting_hub.models import PublicationStatus
from contracting_hub.services.developer_profiles import (
    PublicDeveloperContractSummary,
    PublicDeveloperProfileSnapshot,
    build_empty_public_developer_profile_snapshot,
)
from contracting_hub.states import DeveloperProfileState
from contracting_hub.states.developer_profile import (
    _serialize_authored_contracts,
    _serialize_profile_links,
)


def _set_route_context(state: DeveloperProfileState, path: str) -> None:
    router_data = {
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.HEADERS: {"origin": "http://localhost:3000"},
    }
    object.__setattr__(state, "router_data", router_data)
    object.__setattr__(state, "router", RouterData.from_router_data(router_data))


def _build_state(path: str) -> DeveloperProfileState:
    state = DeveloperProfileState(_reflex_internal_init=True)
    _set_route_context(state, path)
    return state


def _timestamp(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 12, 0, tzinfo=timezone.utc)


def test_load_page_populates_public_profile_snapshot(monkeypatch) -> None:
    state = _build_state("/developers/alice")

    snapshot = PublicDeveloperProfileSnapshot(
        found=True,
        username="alice",
        display_name="Alice Builder",
        bio="Builds treasury-safe Xian modules.",
        avatar_path=None,
        website_url="https://alice.dev",
        github_url="https://github.com/alice",
        xian_profile_url=None,
        published_contract_count=2,
        total_stars_received=5,
        weighted_average_rating=4.5,
        total_rating_count=2,
        total_deployment_count=3,
        recent_publish_count=1,
        recent_stars_received=2,
        recent_rating_count=1,
        recent_deployment_count=1,
        recent_activity_count=5,
        activity_window_days=30,
        activity_since=_timestamp(2, 8),
        authored_contracts=(
            PublicDeveloperContractSummary(
                slug="escrow",
                contract_name="con_escrow",
                display_name="Escrow",
                short_summary="Escrow settlement primitives.",
                status=PublicationStatus.PUBLISHED,
                featured=True,
                semantic_version="1.2.0",
                primary_category_name="Treasury",
                category_names=("Treasury",),
                tag_names=("escrow", "treasury"),
                updated_at=_timestamp(2, 20),
                published_at=_timestamp(2, 20),
                star_count=5,
                rating_count=2,
                average_rating=4.5,
                deployment_count=3,
            ),
        ),
    )

    monkeypatch.setattr(
        "contracting_hub.states.developer_profile.load_public_developer_profile_snapshot_safe",
        lambda **_kwargs: snapshot,
    )

    state.load_page()

    assert state.load_state == "ready"
    assert state.developer_username == "alice"
    assert state.display_name == "Alice Builder"
    assert state.page_title == "Alice Builder"
    assert state.profile_secondary == "@alice"
    assert state.published_contract_count_text == "2"
    assert state.star_total_text == "5"
    assert state.recent_activity_breakdown == "1 publishes • 2 stars • 1 ratings • 1 deploys"
    assert state.authored_contract_count_label == "1 public contract"
    assert state.authored_contracts[0]["detail_href"] == "/contracts/escrow"
    assert state.authored_contracts[0]["status_is_published"] is True
    assert state.profile_links[0]["href"] == "https://alice.dev"


def test_load_page_applies_missing_state_for_unknown_profile(monkeypatch) -> None:
    state = _build_state("/developers/missing")

    monkeypatch.setattr(
        "contracting_hub.states.developer_profile.load_public_developer_profile_snapshot_safe",
        lambda **_kwargs: build_empty_public_developer_profile_snapshot(username="missing"),
    )

    state.load_page()

    assert state.load_state == "missing"
    assert state.developer_username == "missing"
    assert state.page_title == "@missing"
    assert state.authored_contracts == []
    assert state.rating_empty is True


def test_state_derived_properties_cover_default_bio_and_missing_branches() -> None:
    state = _build_state("/developers/placeholder")

    assert state.is_loading is True
    assert state.is_ready is False
    assert state.is_missing is False
    assert state.has_bio is False
    assert state.has_profile_links is False
    assert state.has_authored_contracts is False
    assert state.page_title == "Developer profile"
    assert "Published authorship signals" in state.page_intro
    assert state.profile_secondary == "Public developer"
    assert state.avatar_fallback == "PD"

    state.load_state = "missing"
    state.developer_username = "placeholder"
    assert state.is_missing is True
    assert state.page_intro == "This developer profile is not available on the public catalog."

    state.load_state = "ready"
    state.bio = "Builds reusable treasury flows."
    assert state.page_intro == "Builds reusable treasury flows."

    state.display_name = ""
    state.developer_username = ""
    assert state.avatar_fallback == "DP"


def test_profile_state_helper_serializers_include_all_public_links_and_status_flags() -> None:
    snapshot = PublicDeveloperProfileSnapshot(
        found=True,
        username="alice",
        display_name="Alice Builder",
        bio=None,
        avatar_path=None,
        website_url="https://alice.dev",
        github_url="https://github.com/alice",
        xian_profile_url="https://xian.org/@alice",
        published_contract_count=1,
        total_stars_received=2,
        weighted_average_rating=None,
        total_rating_count=0,
        total_deployment_count=0,
        recent_publish_count=0,
        recent_stars_received=0,
        recent_rating_count=0,
        recent_deployment_count=0,
        recent_activity_count=0,
        activity_window_days=30,
        activity_since=_timestamp(2, 8),
        authored_contracts=(),
    )
    contracts = _serialize_authored_contracts(
        (
            PublicDeveloperContractSummary(
                slug="legacy-vault",
                contract_name="con_legacy_vault",
                display_name="Legacy Vault",
                short_summary="Deprecated treasury vault release.",
                status=PublicationStatus.DEPRECATED,
                featured=False,
                semantic_version=None,
                primary_category_name=None,
                category_names=(),
                tag_names=("vault",),
                updated_at=_timestamp(3, 2),
                published_at=None,
                star_count=0,
                rating_count=0,
                average_rating=None,
                deployment_count=0,
            ),
        )
    )

    assert [link["label"] for link in _serialize_profile_links(snapshot)] == [
        "Website",
        "GitHub",
        "Xian",
    ]
    assert contracts[0]["detail_href"] == "/contracts/legacy-vault"
    assert contracts[0]["status_is_published"] is False
    assert contracts[0]["category_label"] == "Uncategorized"
    assert contracts[0]["rating_empty"] is True


def test_profile_link_serializer_skips_missing_earlier_links() -> None:
    snapshot = PublicDeveloperProfileSnapshot(
        found=True,
        username="alice",
        display_name="Alice Builder",
        bio=None,
        avatar_path=None,
        website_url=None,
        github_url=None,
        xian_profile_url="https://xian.org/@alice",
        published_contract_count=0,
        total_stars_received=0,
        weighted_average_rating=None,
        total_rating_count=0,
        total_deployment_count=0,
        recent_publish_count=0,
        recent_stars_received=0,
        recent_rating_count=0,
        recent_deployment_count=0,
        recent_activity_count=0,
        activity_window_days=30,
        activity_since=_timestamp(2, 8),
        authored_contracts=(),
    )

    assert _serialize_profile_links(snapshot) == [
        {"label": "Xian", "href": "https://xian.org/@alice"}
    ]
