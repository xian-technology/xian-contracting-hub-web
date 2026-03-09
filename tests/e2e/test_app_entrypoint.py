import runpy


def test_app_entrypoint_is_importable() -> None:
    module = runpy.run_path("contracting_hub/app.py")

    assert callable(module["index"])
