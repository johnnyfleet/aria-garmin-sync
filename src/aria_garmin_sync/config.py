"""Paths and settings, overridable through environment variables."""

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("ARIA_SYNC_DATA_DIR", "data"))

# OAuth client downloaded from Google Cloud console (Desktop app client).
GOOGLE_CLIENT_SECRET = Path(
    os.environ.get("ARIA_SYNC_GOOGLE_CLIENT_SECRET", DATA_DIR / "google_client_secret.json")
)
GOOGLE_TOKEN = Path(os.environ.get("ARIA_SYNC_GOOGLE_TOKEN", DATA_DIR / "google_token.json"))
GOOGLE_TOKEN_META = GOOGLE_TOKEN.with_name(GOOGLE_TOKEN.stem + "_meta.json")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
]

HEALTH_API_BASE = "https://health.googleapis.com/v4"

# Garmin Connect session tokens written by garminconnect after the interactive login.
GARMIN_TOKEN = Path(os.environ.get("ARIA_SYNC_GARMIN_TOKEN", DATA_DIR / "garmin_tokens.json"))


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding real environment variables."""
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file(DATA_DIR / ".env")

STATE_DB = Path(os.environ.get("ARIA_SYNC_STATE_DB", DATA_DIR / "state.db"))
SLACK_WEBHOOK = os.environ.get("ARIA_SYNC_SLACK_WEBHOOK")
HEALTHCHECK_URL = os.environ.get("ARIA_SYNC_HEALTHCHECK_URL")
POLL_INTERVAL = int(os.environ.get("ARIA_SYNC_POLL_INTERVAL", "300"))  # seconds
LOOKBACK_DAYS = int(os.environ.get("ARIA_SYNC_LOOKBACK_DAYS", "2"))
# How long to hold a weight that has no body-fat reading yet before uploading it alone.
BODY_FAT_WAIT = int(os.environ.get("ARIA_SYNC_BODY_FAT_WAIT", "180"))  # seconds
# Repeat an unresolved failure alert this often.
FAILURE_REMINDER = int(os.environ.get("ARIA_SYNC_FAILURE_REMINDER", str(24 * 3600)))  # seconds
