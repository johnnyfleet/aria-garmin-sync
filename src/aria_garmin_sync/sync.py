"""One sync cycle, and the polling loop that runs it with alerting."""

import logging
import signal
import threading
import time
from datetime import UTC, datetime, timedelta

from . import config, garmin, notify
from .health import HealthClient, since_filter
from .readings import Reading, pair
from .store import Store

log = logging.getLogger(__name__)


def describe(r: Reading) -> str:
    fat = f", {r.fat_pct:.1f}% body fat" if r.fat_pct is not None else " (no body fat)"
    return f"{r.weight_kg:.2f} kg{fat}, weighed {r.time:%a %d %b %H:%M}"


def fetch_readings(days: int) -> list[Reading]:
    health = HealthClient()
    start = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return pair(
        list(health.data_points("weight", filter=since_filter("weight", start))),
        list(health.data_points("body-fat", filter=since_filter("body-fat", start))),
    )


def run_once(store: Store) -> list[Reading]:
    """Upload any new readings. Returns the readings uploaded this cycle."""
    now = datetime.now(UTC)
    pending = []
    for r in fetch_readings(config.LOOKBACK_DAYS):
        if store.is_synced(r.id):
            continue
        if r.fat_pct is None and (now - r.time).total_seconds() < config.BODY_FAT_WAIT:
            log.info("Holding %s until body fat arrives", r.id)
            continue
        pending.append(r)
    if not pending:
        return []

    client = garmin.connect()  # only touch Garmin when there's something to do
    uploaded = []
    for r in pending:
        if garmin.already_uploaded(client, r):
            log.info("Already in Garmin, recording: %s", describe(r))
            store.record(r, "already_in_garmin")
            continue
        garmin.upload(client, r)
        store.record(r, "uploaded")
        uploaded.append(r)
        log.info("Uploaded: %s", describe(r))
        lag = (datetime.now(UTC) - r.time).total_seconds() / 60
        notify.slack(f":white_check_mark: Synced to Garmin: {describe(r)} ({lag:.0f} min after weigh-in)")
    return uploaded


def _failure_key(e: Exception) -> str:
    return f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}"[:300]


def handle_failure(store: Store, e: Exception) -> None:
    """Alert on a new kind of failure, or remind if the same one has persisted for a day."""
    key = _failure_key(e)
    last_key = store.get("failure_key")
    last_alert = float(store.get("failure_alerted_at") or 0)
    if key != last_key or time.time() - last_alert >= config.FAILURE_REMINDER:
        since = datetime.fromisoformat(store.get("failing_since") or datetime.now(UTC).isoformat()).astimezone()
        prefix = ":x: Aria → Garmin sync failing" if key != last_key else ":warning: Still failing"
        notify.slack(f"{prefix} (since {since:%a %d %b %H:%M}):\n```{key}```")
        store.set("failure_alerted_at", str(time.time()))
    store.set("failure_key", key)
    if not store.get("failing_since"):
        store.set("failing_since", datetime.now(UTC).isoformat())


def handle_success(store: Store) -> None:
    if store.get("failure_key"):
        notify.slack(":large_green_circle: Aria → Garmin sync recovered.")
        for k in ("failure_key", "failure_alerted_at", "failing_since"):
            store.set(k, None)


def run_forever() -> None:
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    store = Store()
    log.info("Polling every %ss (lookback %s days)", config.POLL_INTERVAL, config.LOOKBACK_DAYS)
    while not stop.is_set():
        try:
            uploaded = run_once(store)
        except Exception as e:
            log.exception("Sync cycle failed")
            handle_failure(store, e)
            notify.healthcheck(False, _failure_key(e))
        else:
            handle_success(store)
            notify.healthcheck(True, f"{len(uploaded)} uploaded")
        stop.wait(config.POLL_INTERVAL)
    log.info("Stopped")
