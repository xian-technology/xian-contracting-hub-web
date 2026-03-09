import importlib
import sys
from pathlib import Path

import reflex as rx


def _ensure_project_root_on_path() -> None:
    """Keep package imports stable when this module is executed by path."""
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def _load_data_layer() -> None:
    """Import model modules so Reflex can discover metadata for migrations."""
    _ensure_project_root_on_path()
    importlib.import_module("contracting_hub.models")


def _load_home_page() -> tuple[str, object, str]:
    """Load the home page module when the app file is executed by path."""
    _ensure_project_root_on_path()
    home_module = importlib.import_module("contracting_hub.pages.home")
    meta_module = importlib.import_module("contracting_hub.utils.meta")
    return home_module.ROUTE, home_module.index, meta_module.APP_NAME


def _load_theme_config() -> tuple[object, object, object]:
    """Load theme configuration after ensuring package imports are stable."""
    _ensure_project_root_on_path()
    theme_module = importlib.import_module("contracting_hub.theme")
    return theme_module.APP_STYLE, theme_module.APP_STYLESHEETS, theme_module.APP_THEME


_load_data_layer()
APP_STYLE, APP_STYLESHEETS, APP_THEME = _load_theme_config()
HOME_ROUTE, index, APP_NAME = _load_home_page()

app = rx.App(theme=APP_THEME, style=APP_STYLE, stylesheets=APP_STYLESHEETS)
app.add_page(index, route=HOME_ROUTE, title=APP_NAME)
