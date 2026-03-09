import pytest

pytestmark = pytest.mark.smoke


def test_app_entrypoint_is_importable(app_module: dict[str, object]) -> None:
    assert callable(app_module["index"])
