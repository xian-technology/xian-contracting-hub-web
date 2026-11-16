from pathlib import Path

import pytest

from contracting_hub.config import load_settings
from contracting_hub.services.bootstrap import (
    DEFAULT_CATEGORY_TAXONOMY,
    BootstrapSeedReport,
    DemoSeedReport,
    _format_bootstrap_report,
    build_bootstrap_admin_definition,
)


def test_default_category_taxonomy_has_stable_order_and_unique_slugs() -> None:
    assert [category.sort_order for category in DEFAULT_CATEGORY_TAXONOMY] == sorted(
        category.sort_order for category in DEFAULT_CATEGORY_TAXONOMY
    )
    assert len({category.slug for category in DEFAULT_CATEGORY_TAXONOMY}) == len(
        DEFAULT_CATEGORY_TAXONOMY
    )
    assert len({category.name for category in DEFAULT_CATEGORY_TAXONOMY}) == len(
        DEFAULT_CATEGORY_TAXONOMY
    )


def test_build_bootstrap_admin_definition_returns_none_when_identity_is_disabled(
    tmp_path: Path,
) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_EMAIL": "",
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_USERNAME": "",
        },
        env_file=tmp_path / ".env",
    )

    assert build_bootstrap_admin_definition(settings) is None


def test_build_bootstrap_admin_definition_uses_configured_values(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_EMAIL": "catalog-admin@example.com",
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_USERNAME": "catalogadmin",
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Catalog Admin",
            "CONTRACTING_HUB_BOOTSTRAP_ADMIN_PASSWORD_HASH": "hashed-catalog-admin",
        },
        env_file=tmp_path / ".env",
    )

    definition = build_bootstrap_admin_definition(settings)

    assert definition is not None
    assert definition.email == "catalog-admin@example.com"
    assert definition.username == "catalogadmin"
    assert definition.display_name == "Catalog Admin"
    assert definition.password_hash == "hashed-catalog-admin"


@pytest.mark.parametrize("with_demo", [False, True])
def test_bootstrap_cli_summary_reports_catalog_counts_without_server_playground(with_demo):
    demo = DemoSeedReport(True, 1, 1, 2, 3, 0, 4, 5, 1) if with_demo else None
    report = BootstrapSeedReport(True, 2, 3, False, False, False, ("seed warning",), demo)
    summary = _format_bootstrap_report(report)
    assert "categories_created=2" in summary
    assert "categories_existing=3" in summary
    assert "warning=seed warning" in summary
    assert ("demo_contracts_created=2" in summary) is with_demo
    assert ("demo_ratings_created=5" in summary) is with_demo
    assert "playground" not in summary
    assert "deployment" not in summary
