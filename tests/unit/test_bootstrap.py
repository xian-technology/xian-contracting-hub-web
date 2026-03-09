import pytest

pytestmark = pytest.mark.smoke


def test_project_dependencies_are_pinned(pyproject_data: dict[str, object]) -> None:
    project = pyproject_data["project"]

    assert project["requires-python"] == "==3.11.11"
    assert "reflex==0.8.27" in project["dependencies"]
    assert "sqlmodel==0.0.33" in project["dependencies"]
    assert "alembic==1.18.4" in project["dependencies"]
    assert "xian-contracting==1.0.2" in project["dependencies"]


def test_reflex_configuration_uses_package_name(rxconfig_module: dict[str, object]) -> None:
    assert rxconfig_module["config"].app_name == "contracting_hub"
