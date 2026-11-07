"""Garmin Connect writes via the unofficial garminconnect library."""

import os
from datetime import timedelta
from getpass import getpass

from garminconnect import Garmin, GarminConnectAuthenticationError

from . import config
from .readings import Reading


class GarminAuthError(RuntimeError):
    pass


def interactive_login(email: str) -> str:
    """Log in with password + MFA prompt and save session tokens. Returns the display name."""
    config.GARMIN_TOKEN.parent.mkdir(parents=True, exist_ok=True)
    if config.GARMIN_TOKEN.exists():
        config.GARMIN_TOKEN.unlink()  # force a credential login rather than reusing old tokens
    client = Garmin(
        email,
        getpass("Garmin password: "),
        prompt_mfa=lambda: input("Garmin MFA code (check your email): ").strip(),
    )
    client.login(str(config.GARMIN_TOKEN))
    if not config.GARMIN_TOKEN.exists():
        raise GarminAuthError(f"Login succeeded but no tokens were written to {config.GARMIN_TOKEN}")
    os.chmod(config.GARMIN_TOKEN, 0o600)
    return client.get_full_name()


def connect() -> Garmin:
    """Log in using saved tokens only; never prompts for a password or MFA."""
    if not config.GARMIN_TOKEN.exists():
        raise GarminAuthError(f"No Garmin tokens at {config.GARMIN_TOKEN}; run `aria-sync garmin-login`.")
    client = Garmin()
    try:
        client.login(str(config.GARMIN_TOKEN))
    except GarminConnectAuthenticationError as e:
        raise GarminAuthError(f"Garmin rejected the saved tokens ({e}); run `aria-sync garmin-login`.") from e
    return client


def weigh_ins_on(client: Garmin, reading: Reading) -> list[dict]:
    return client.get_daily_weigh_ins(reading.time.date().isoformat()).get("dateWeightList", [])


def already_uploaded(client: Garmin, reading: Reading) -> bool:
    """True if Garmin has a weigh-in within a minute of this reading."""
    target_ms = reading.time.timestamp() * 1000
    window_ms = timedelta(minutes=1).total_seconds() * 1000
    return any(
        abs(w.get("timestampGMT", 0) - target_ms) <= window_ms
        for w in weigh_ins_on(client, reading)
    )


def upload(client: Garmin, reading: Reading) -> dict:
    return client.add_body_composition(
        reading.time.isoformat(),
        weight=reading.weight_kg,
        percent_fat=reading.fat_pct,
    )
