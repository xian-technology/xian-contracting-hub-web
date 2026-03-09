import importlib
import sys
from pathlib import Path

import reflex as rx


def _load_home_page() -> tuple[str, object, str]:
    """Load the home page module when the app file is executed by path."""
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    home_module = importlib.import_module("contracting_hub.pages.home")
    meta_module = importlib.import_module("contracting_hub.utils.meta")
    return home_module.ROUTE, home_module.index, meta_module.APP_NAME


HOME_ROUTE, index, APP_NAME = _load_home_page()

app = rx.App()
app.add_page(index, route=HOME_ROUTE, title=APP_NAME)
