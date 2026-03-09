from __future__ import annotations

from contracting_hub.pages.login import index as login_index
from contracting_hub.pages.register import index as register_index
from contracting_hub.utils.meta import LOGIN_ROUTE, REGISTER_ROUTE


def _rendered_text(node: dict[str, object]) -> list[str]:
    text_fragments: list[str] = []
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue

        contents = current.get("contents")
        if isinstance(contents, str):
            text_fragments.append(contents.strip('"'))

        stack.extend(reversed(current.get("children", [])))
        false_value = current.get("false_value")
        true_value = current.get("true_value")
        if false_value is not None:
            stack.append(false_value)
        if true_value is not None:
            stack.append(true_value)

    return text_fragments


def _collect_props(node: dict[str, object]) -> list[str]:
    props_values: list[str] = []
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue

        props = current.get("props")
        if isinstance(props, list):
            props_values.extend(str(prop) for prop in props)

        stack.extend(reversed(current.get("children", [])))
        false_value = current.get("false_value")
        true_value = current.get("true_value")
        if false_value is not None:
            stack.append(false_value)
        if true_value is not None:
            stack.append(true_value)

    return props_values


def test_app_registers_login_and_registration_routes(app_module: dict[str, object]) -> None:
    assert LOGIN_ROUTE.lstrip("/") in app_module["app"]._unevaluated_pages
    assert REGISTER_ROUTE.lstrip("/") in app_module["app"]._unevaluated_pages


def test_login_page_renders_form_shell_and_session_navigation() -> None:
    rendered = login_index().render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"app-shell"' in rendered["props"]
    assert any('"data-testid":"login-page"' in prop for prop in rendered_props)
    assert any('"data-testid":"login-form"' in prop for prop in rendered_props)
    assert any('"data-testid":"session-navigation"' in prop for prop in rendered_props)
    assert "Log in" in rendered_text
    assert "Welcome back" in rendered_text
    assert "Create one" in rendered_text


def test_registration_page_renders_form_shell_and_identity_copy() -> None:
    rendered = register_index().render()
    rendered_text = _rendered_text(rendered)
    rendered_props = _collect_props(rendered)

    assert rendered["name"] == "RadixThemesBox"
    assert '"data-testid":"app-shell"' in rendered["props"]
    assert any('"data-testid":"register-page"' in prop for prop in rendered_props)
    assert any('"data-testid":"register-form"' in prop for prop in rendered_props)
    assert "Create account" in rendered_text
    assert "Create your account" in rendered_text
    assert "Username" in rendered_text
    assert "Already registered?" in rendered_text
