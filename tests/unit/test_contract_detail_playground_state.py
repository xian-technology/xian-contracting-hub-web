import base64
import json
import zlib
from urllib.parse import urlsplit

from contracting_hub.config import load_settings
from contracting_hub.states.contract_detail import ContractDetailState


def test_public_detail_shares_selected_source_without_an_account(monkeypatch, tmp_path):
    settings = load_settings(project_root=tmp_path, environ={}, env_file=tmp_path / ".env")
    monkeypatch.setattr("contracting_hub.states.contract_detail.get_settings", lambda: settings)
    state = ContractDetailState(_reflex_internal_init=True)
    state.load_state = "ready"
    state.contract_name = "con_legacy"
    state.selected_version_source_code = "@export\ndef value():\n    return 'legacy'\n"
    state._load_playground_link()
    encoded = urlsplit(state.playground_href).fragment[2:]
    payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    workspace = json.loads(zlib.decompress(payload, wbits=-15))
    assert workspace["editor"] == {
        "contractName": "con_legacy",
        "code": state.selected_version_source_code,
    }
    assert state.current_user_id is None
    assert state.playground_error == ""


def test_invalid_playground_url_reports_error_and_clears_previous_link(monkeypatch, tmp_path):
    settings = load_settings(
        project_root=tmp_path,
        environ={"CONTRACTING_HUB_PLAYGROUND_URL": "javascript:alert(1)"},
        env_file=tmp_path / ".env",
    )
    monkeypatch.setattr("contracting_hub.states.contract_detail.get_settings", lambda: settings)
    state = ContractDetailState(_reflex_internal_init=True)
    state.load_state = "ready"
    state.playground_href = "stale"
    state._load_playground_link()
    assert state.playground_href == ""
    assert "Playground URL" in state.playground_error


def test_missing_contract_clears_playground_link_and_error():
    state = ContractDetailState(_reflex_internal_init=True)
    state.playground_href = "stale"
    state.playground_error = "stale"
    state._load_playground_link()
    assert state.playground_href == ""
    assert state.playground_error == ""
