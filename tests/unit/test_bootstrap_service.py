from pathlib import Path

from contracting_hub.config import load_settings
from contracting_hub.services.bootstrap import (
    DEFAULT_CATEGORY_TAXONOMY,
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
