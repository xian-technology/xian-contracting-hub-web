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
    developer_leaderboard_module = importlib.import_module(
        "contracting_hub.pages.developer_leaderboard"
    )
    developer_profile_module = importlib.import_module("contracting_hub.pages.developer_profile")
    login_module = importlib.import_module("contracting_hub.pages.login")
    register_module = importlib.import_module("contracting_hub.pages.register")
    profile_settings_module = importlib.import_module("contracting_hub.pages.profile_settings")
    deployment_history_module = importlib.import_module("contracting_hub.pages.deployment_history")
    admin_contracts_module = importlib.import_module("contracting_hub.admin.contracts_index")
    admin_contract_editor_module = importlib.import_module("contracting_hub.admin.contract_editor")
    admin_contract_versions_module = importlib.import_module(
        "contracting_hub.admin.contract_versions"
    )
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
            developer_leaderboard_module.ROUTE,
            developer_leaderboard_module.index,
            f"Developer Leaderboard | {meta_module.APP_NAME}",
            developer_leaderboard_module.ON_LOAD,
        ),
        (
            developer_profile_module.ROUTE,
            developer_profile_module.index,
            f"Developer Profile | {meta_module.APP_NAME}",
            developer_profile_module.ON_LOAD,
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
        (
            profile_settings_module.ROUTE,
            profile_settings_module.index,
            f"Profile settings | {meta_module.APP_NAME}",
            profile_settings_module.ON_LOAD,
        ),
        (
            deployment_history_module.ROUTE,
            deployment_history_module.index,
            f"Deployment history | {meta_module.APP_NAME}",
            deployment_history_module.ON_LOAD,
        ),
        (
            admin_contracts_module.ROUTE,
            admin_contracts_module.index,
            f"Admin Contracts | {meta_module.APP_NAME}",
            admin_contracts_module.ON_LOAD,
        ),
        (
            admin_contract_editor_module.NEW_ROUTE,
            admin_contract_editor_module.new_contract,
            f"Create Contract | {meta_module.APP_NAME}",
            admin_contract_editor_module.ON_LOAD,
        ),
        (
            admin_contract_editor_module.EDIT_ROUTE,
            admin_contract_editor_module.edit_contract,
            f"Edit Contract | {meta_module.APP_NAME}",
            admin_contract_editor_module.ON_LOAD,
        ),
        (
            admin_contract_versions_module.ROUTE,
            admin_contract_versions_module.index,
            f"Contract Versions | {meta_module.APP_NAME}",
            admin_contract_versions_module.ON_LOAD,
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
