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
