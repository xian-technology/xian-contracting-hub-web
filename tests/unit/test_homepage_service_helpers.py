import pytest
import sqlalchemy as sa

from contracting_hub.services import homepage


def test_normalize_home_page_section_limit_defaults_and_validates() -> None:
    assert homepage.normalize_home_page_section_limit(None) == 4
    assert homepage.normalize_home_page_section_limit(6) == 6

    with pytest.raises(ValueError, match="positive integer"):
        homepage.normalize_home_page_section_limit(0)


def test_load_public_home_page_snapshot_safe_returns_empty_snapshot_when_schema_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_operational_error():
        raise sa.exc.OperationalError("SELECT 1", {}, Exception("no such table"))

    monkeypatch.setattr(homepage, "session_scope", _raise_operational_error)

    snapshot = homepage.load_public_home_page_snapshot_safe()

    assert snapshot == homepage.build_empty_home_page_snapshot()
