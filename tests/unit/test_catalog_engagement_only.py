import pytest

from contracting_hub.services.developer_kpis import (
    DeveloperKPIServiceError,
    normalize_developer_leaderboard_sort,
)
from contracting_hub.services.developer_leaderboard import (
    normalize_public_developer_leaderboard_sort,
)


def test_deployment_counts_are_not_a_leaderboard_sort():
    with pytest.raises(DeveloperKPIServiceError, match="Leaderboard sort"):
        normalize_developer_leaderboard_sort("deployment_count")
    assert normalize_public_developer_leaderboard_sort("deployment_count").value == "star_total"


@pytest.mark.parametrize("featured", [True, False])
@pytest.mark.parametrize("section", ["featured", "trending"])
def test_home_card_shows_source_release_and_engagement_without_deployment_metrics(
    featured, section
):
    from datetime import datetime, timezone

    from contracting_hub.models import PublicationStatus
    from contracting_hub.pages.home import _contract_summary_card, _resolve_contract_context
    from contracting_hub.services.homepage import HomePageContractSummary

    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    summary = HomePageContractSummary(
        slug="example",
        contract_name="con_example",
        display_name="Example",
        short_summary="A catalog example",
        status=PublicationStatus.PUBLISHED,
        featured=featured,
        semantic_version="1.2.3",
        author_name="Builder",
        primary_category_name="Examples",
        category_names=("Examples",),
        tag_names=("token",),
        updated_at=now,
        published_at=now if featured else None,
        star_count=7,
        rating_count=2,
        average_rating=4.5,
    )

    rendered = str(_contract_summary_card(summary, section_key=section).render())

    assert "Example" in rendered
    assert "1.2.3" in rendered
    assert "4.5 avg" in rendered
    assert "Deploys" not in rendered
    assert _resolve_contract_context(summary, section) == (
        "Published Nov 16, 2026" if featured and section == "featured" else "Updated Nov 16, 2026"
    )
