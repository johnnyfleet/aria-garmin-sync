from aria_garmin_sync import notify, sync
from aria_garmin_sync.store import Store


def test_failure_alerts_are_deduplicated_and_recovery_announced(monkeypatch, isolated_config):
    sent = []
    monkeypatch.setattr(notify, "slack", sent.append)
    store = Store(isolated_config / "state.db")

    for _ in range(3):
        sync.handle_failure(store, RuntimeError("Google token refresh failed"))
    assert len(sent) == 1 and "failing" in sent[0]

    sync.handle_failure(store, ValueError("something else"))
    assert len(sent) == 2

    sync.handle_success(store)
    sync.handle_success(store)
    assert len(sent) == 3 and "recovered" in sent[2]


def test_failure_reminder_after_interval(monkeypatch, isolated_config):
    sent = []
    monkeypatch.setattr(notify, "slack", sent.append)
    monkeypatch.setattr(sync.config, "FAILURE_REMINDER", 0)
    store = Store(isolated_config / "state.db")
    sync.handle_failure(store, RuntimeError("x"))
    sync.handle_failure(store, RuntimeError("x"))
    assert len(sent) == 2 and "Still failing" in sent[1]
