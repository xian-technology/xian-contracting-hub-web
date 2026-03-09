import importlib


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
