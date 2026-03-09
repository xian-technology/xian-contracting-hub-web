import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict[str, bool]:
    """Keep browser-backed E2E runs headless in automated loops."""
    return {"headless": True}


@pytest.fixture(scope="session")
def browser_context_args(
    browser_context_args: dict[str, object],
) -> dict[str, object]:
    """Apply a stable viewport for browser tests across local and CI runs."""
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 960},
    }
