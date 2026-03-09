import runpy


def test_app_module_exports_reflex_app() -> None:
    module = runpy.run_path("contracting_hub/app.py")

    assert module["app"] is not None
    assert module["app"].theme is not None
    assert module["app"].style["--hub-layout-max-width"] == "76rem"


def test_home_page_uses_the_shared_shell() -> None:
    module = runpy.run_path("contracting_hub/app.py")

    rendered = module["index"]().render()

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"app-shell"' in rendered["props"]
