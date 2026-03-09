import importlib

import pytest

pytestmark = pytest.mark.smoke


def test_app_entrypoint_is_importable(app_module: dict[str, object]) -> None:
    assert callable(app_module["index"])


def test_reflex_export_shim_is_importable() -> None:
    app_module = importlib.import_module("contracting_hub.contracting_hub")

    assert app_module.app is not None
