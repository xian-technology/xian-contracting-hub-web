import pytest

pytestmark = pytest.mark.smoke


def test_project_dependencies_are_pinned(pyproject_data: dict[str, object]) -> None:
    project = pyproject_data["project"]
    dependencies = project["dependencies"]

    assert project["requires-python"] == ">=3.14,<3.15"
    assert "reflex>=0.9.6.post1,<0.10.0" in dependencies
    assert not any(dependency.startswith("reflex-components-") for dependency in dependencies)
    assert "sqlmodel==0.0.38" in dependencies
    assert "alembic==1.18.4" in dependencies
    assert "xian-tech-contracting>=1.0.1,<2" in dependencies


def test_reflex_configuration_uses_package_name(rxconfig_module: dict[str, object]) -> None:
    assert rxconfig_module["config"].app_name == "contracting_hub"
