from reflex.model import ModelRegistry

from contracting_hub import models

EXPECTED_TABLES = {
    "admin_audit_logs",
    "categories",
    "contract_category_links",
    "contract_relations",
    "contract_versions",
    "contracts",
    "deployment_history",
    "playground_targets",
    "profiles",
    "ratings",
    "stars",
    "users",
}


def test_models_module_exports_full_domain_schema() -> None:
    exported_names = set(models.__all__)

    assert {"User", "Profile", "Contract", "ContractVersion", "DeploymentHistory"} <= exported_names
    assert models.ContractRelationType.DEPENDS_ON.value == "depends_on"
    assert models.PublicationStatus.PUBLISHED.value == "published"


def test_model_registry_contains_phase_two_tables() -> None:
    metadata = ModelRegistry.get_metadata()

    assert EXPECTED_TABLES <= set(metadata.tables)
