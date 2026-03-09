import pytest

pytestmark = pytest.mark.smoke


def test_app_module_exports_reflex_app(app_module: dict[str, object]) -> None:
    assert app_module["app"] is not None
    assert app_module["app"].theme is not None
    assert app_module["app"].style["--hub-layout-max-width"] == "76rem"


def test_home_page_uses_the_shared_shell(app_module: dict[str, object]) -> None:
    rendered = app_module["index"]().render()

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"app-shell"' in rendered["props"]
