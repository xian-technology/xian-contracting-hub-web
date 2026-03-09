import runpy
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_MARKERS_BY_DIRECTORY = {
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
}

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    """Keep cached settings isolated across tests that mutate local env state."""
    from contracting_hub.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def pyproject_data(project_root: Path) -> dict[str, object]:
    return tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.fixture
def rxconfig_module(project_root: Path) -> dict[str, object]:
    return runpy.run_path(str(project_root / "rxconfig.py"))


@pytest.fixture
def app_module(project_root: Path) -> dict[str, object]:
    return runpy.run_path(str(project_root / "contracting_hub" / "app.py"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        test_path = Path(str(item.fspath))
        for directory_name, marker_name in TEST_MARKERS_BY_DIRECTORY.items():
            if directory_name in test_path.parts:
                item.add_marker(getattr(pytest.mark, marker_name))
