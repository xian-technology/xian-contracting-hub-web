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


def _load_pages() -> tuple[tuple[str, object, str, object | None], ...]:
    """Load public pages when the app file is executed by path."""
    _ensure_project_root_on_path()
    home_module = importlib.import_module("contracting_hub.pages.home")
    browse_module = importlib.import_module("contracting_hub.pages.browse")
    detail_module = importlib.import_module("contracting_hub.pages.contract_detail")
    login_module = importlib.import_module("contracting_hub.pages.login")
    register_module = importlib.import_module("contracting_hub.pages.register")
    meta_module = importlib.import_module("contracting_hub.utils.meta")
    return (
        (home_module.ROUTE, home_module.index, meta_module.APP_NAME, home_module.ON_LOAD),
        (
            browse_module.ROUTE,
            browse_module.index,
            f"Browse | {meta_module.APP_NAME}",
            browse_module.ON_LOAD,
        ),
        (
            detail_module.ROUTE,
            detail_module.index,
            f"Contract Detail | {meta_module.APP_NAME}",
            detail_module.ON_LOAD,
        ),
        (
            login_module.ROUTE,
            login_module.index,
            f"Log in | {meta_module.APP_NAME}",
            login_module.ON_LOAD,
        ),
        (
            register_module.ROUTE,
            register_module.index,
            f"Create account | {meta_module.APP_NAME}",
            register_module.ON_LOAD,
        ),
    )


def _load_theme_config() -> tuple[object, object, object]:
    """Load theme configuration after ensuring package imports are stable."""
    _ensure_project_root_on_path()
    theme_module = importlib.import_module("contracting_hub.theme")
    return theme_module.APP_STYLE, theme_module.APP_STYLESHEETS, theme_module.APP_THEME


_load_data_layer()
APP_STYLE, APP_STYLESHEETS, APP_THEME = _load_theme_config()
PAGES = _load_pages()
HOME_ROUTE, index, APP_NAME, _ = PAGES[0]

app = rx.App(theme=APP_THEME, style=APP_STYLE, stylesheets=APP_STYLESHEETS)
for route, component, title, on_load in PAGES:
    app.add_page(component, route=route, title=title, on_load=on_load)
