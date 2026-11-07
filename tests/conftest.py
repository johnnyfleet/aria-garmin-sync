import pytest

from aria_garmin_sync import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point all state at a temp dir and switch off outbound alerts."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "STATE_DB", tmp_path / "state.db")
    monkeypatch.setattr(config, "HEARTBEAT", tmp_path / "heartbeat")
    monkeypatch.setattr(config, "SLACK_WEBHOOK", None)
    monkeypatch.setattr(config, "HEALTHCHECK_URL", None)
    return tmp_path
