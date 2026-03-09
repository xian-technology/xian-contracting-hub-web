import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_base_application_packages_are_importable() -> None:
    modules = [
        "contracting_hub.admin",
        "contracting_hub.components",
        "contracting_hub.integrations",
        "contracting_hub.models",
        "contracting_hub.pages",
        "contracting_hub.repositories",
        "contracting_hub.services",
        "contracting_hub.states",
        "contracting_hub.theme",
        "contracting_hub.utils",
    ]

    for module_name in modules:
        assert importlib.import_module(module_name) is not None
