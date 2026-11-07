import subprocess
import sys


def test_cli_help_lists_commands():
    out = subprocess.run(
        [sys.executable, "-c", "from aria_garmin_sync.cli import main; main()", "--help"],
        capture_output=True, text=True, check=True,
    ).stdout
    for cmd in ("run", "sync-once", "backfill", "webhook-test", "garmin-login", "google-auth"):
        assert cmd in out
