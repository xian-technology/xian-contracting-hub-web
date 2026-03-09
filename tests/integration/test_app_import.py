import runpy


def test_app_module_exports_reflex_app() -> None:
    module = runpy.run_path("contracting_hub/app.py")

    assert module["app"] is not None
