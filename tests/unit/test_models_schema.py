from reflex.model import ModelRegistry

from contracting_hub import models

EXPECTED_TABLES = {
    "admin_audit_logs",
    "auth_sessions",
    "categories",
    "contract_category_links",
    "contract_packages",
    "contract_package_release_artifacts",
    "contract_package_releases",
    "contract_relations",
    "contract_versions",
    "contracts",
    "profiles",
    "ratings",
    "stars",
    "users",
}


def test_models_module_exports_full_domain_schema() -> None:
    exported_names = set(models.__all__)

    assert {
        "AuthSession",
        "User",
        "Profile",
        "Contract",
        "ContractPackage",
        "ContractPackageRelease",
        "ContractPackageReleaseArtifact",
        "ContractVersion",
    } <= exported_names
    assert models.ContractRelationType.DEPENDS_ON.value == "depends_on"
    assert models.ContractPackageKind.PRODUCT.value == "product"
    assert models.PublicationStatus.PUBLISHED.value == "published"


def test_model_registry_contains_phase_two_tables() -> None:
    metadata = ModelRegistry.get_metadata()

    assert EXPECTED_TABLES <= set(metadata.tables)


def test_browser_playground_has_no_server_side_target_or_deployment_tables() -> None:
    metadata = ModelRegistry.get_metadata()

    assert "playground_targets" not in metadata.tables
    assert "deployment_history" not in metadata.tables
