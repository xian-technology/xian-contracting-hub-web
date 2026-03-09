import runpy
import tomllib
from pathlib import Path


def test_project_dependencies_are_pinned() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["requires-python"] == "==3.11.11"
    assert "reflex==0.8.27" in project["dependencies"]
    assert "sqlmodel==0.0.33" in project["dependencies"]
    assert "alembic==1.18.4" in project["dependencies"]
    assert "xian-contracting==1.0.2" in project["dependencies"]


def test_reflex_configuration_uses_package_name() -> None:
    rxconfig = runpy.run_path("rxconfig.py")

    assert rxconfig["config"].app_name == "contracting_hub"
