"""Command-line entry point: `aria-sync <command>`."""

import argparse
import json
import logging
import sys
from datetime import UTC, date, datetime, timedelta

from . import config, garmin, notify, sync
from .google_auth import AuthError, authorize, load_credentials, load_meta
from .health import HealthApiError, HealthClient, since_filter
from .readings import Reading, pair
from .store import Store


def _describe_expiry(meta: dict) -> str:
    expires_in = meta.get("refresh_token_expires_in")
    if not expires_in:
        return "no refresh-token expiry set by Google (app is In production)"
    expires_at = datetime.fromtimestamp(meta["issued_at"] + int(expires_in), UTC)
    days = int(expires_in) / 86400
    return (
        f"refresh token expires in {days:.1f} days ({expires_at:%Y-%m-%d %H:%M} UTC). "
        "The app is probably still in Testing; publish it and re-run google-auth."
    )


def cmd_google_auth(args: argparse.Namespace) -> None:
    meta = authorize(port=args.port, open_browser=not args.no_browser)
    print(f"Saved token to {config.GOOGLE_TOKEN}")
    print(f"Granted scopes: {meta.get('scope')}")
    print(_describe_expiry(meta))


def cmd_google_status(args: argparse.Namespace) -> None:
    creds = load_credentials()
    meta = load_meta()
    print(f"Access token valid until {creds.expiry:%Y-%m-%d %H:%M} UTC")
    if meta:
        issued = datetime.fromtimestamp(meta["issued_at"], UTC)
        print(f"Consent given {issued:%Y-%m-%d %H:%M} UTC; {_describe_expiry(meta)}")
    print("Identity:", json.dumps(HealthClient().identity(), indent=2))


def cmd_google_fetch(args: argparse.Namespace) -> None:
    client = HealthClient()
    start = (datetime.now(UTC) - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = {}
    for data_type in args.types:
        flt = None if args.no_filter else since_filter(data_type, start)
        result[data_type] = list(client.data_points(data_type, filter=flt))
        print(f"{data_type}: {len(result[data_type])} data points", file=sys.stderr)
    print(json.dumps(result, indent=2))


def _latest_reading(days: int) -> Reading:
    client = HealthClient()
    start = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    weights = list(client.data_points("weight", filter=since_filter("weight", start)))
    fats = list(client.data_points("body-fat", filter=since_filter("body-fat", start)))
    readings = pair(weights, fats)
    if not readings:
        raise HealthApiError(f"No weight readings in the last {days} days")
    return readings[-1]


def _describe(r: Reading) -> str:
    fat = f"{r.fat_pct:.1f}% BF" if r.fat_pct is not None else "no BF"
    return f"{r.weight_kg:.2f} kg, {fat}, weighed {r.time:%Y-%m-%d %H:%M %z} (id {r.id})"


def cmd_garmin_login(args: argparse.Namespace) -> None:
    email = args.email or input("Garmin email: ").strip()
    name = garmin.interactive_login(email)
    print(f"Logged in as {name}; tokens saved to {config.GARMIN_TOKEN}")


def cmd_garmin_check(args: argparse.Namespace) -> None:
    client = garmin.connect()
    print(f"Garmin tokens OK for {client.get_full_name()}")
    end = date.today()
    start = end - timedelta(days=args.days)
    print(json.dumps(client.get_weigh_ins(start.isoformat(), end.isoformat()), indent=2))


def cmd_push_latest(args: argparse.Namespace) -> None:
    reading = _latest_reading(args.days)
    print(f"Latest Google reading: {_describe(reading)}")
    client = garmin.connect()
    if garmin.already_uploaded(client, reading) and not args.force:
        print("Garmin already has a weigh-in at that time; skipping (use --force to upload anyway).")
        return
    if args.dry_run:
        print("Dry run: not uploading.")
        return
    garmin.upload(client, reading)
    print("Uploaded. Garmin now shows for that day:")
    print(json.dumps(garmin.weigh_ins_on(client, reading), indent=2))


def cmd_backfill(args: argparse.Namespace) -> None:
    start = datetime.combine(args.since, datetime.min.time(), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    health = HealthClient()
    readings = pair(
        list(health.data_points("weight", filter=since_filter("weight", start))),
        list(health.data_points("body-fat", filter=since_filter("body-fat", start))),
    )
    print(f"{len(readings)} Google readings since {args.since}")
    client = garmin.connect()
    for r in readings:
        if garmin.already_uploaded(client, r):
            print(f"  skip (in Garmin): {_describe(r)}")
        elif args.dry_run:
            print(f"  would upload:     {_describe(r)}")
        else:
            garmin.upload(client, r)
            print(f"  uploaded:         {_describe(r)}")


def cmd_run(args: argparse.Namespace) -> None:
    sync.run_forever()


def cmd_sync_once(args: argparse.Namespace) -> None:
    store = Store()
    uploaded = sync.run_once(store)
    sync.handle_success(store)
    notify.healthcheck(True, f"{len(uploaded)} uploaded (manual)")
    print(f"{len(uploaded)} reading(s) uploaded")


def cmd_test_alerts(args: argparse.Namespace) -> None:
    notify.slack(":wave: Test message from aria-sync. Slack alerts are working.")
    notify.healthcheck(True, "test ping from aria-sync")
    print(f"Slack configured: {bool(config.SLACK_WEBHOOK)}; healthcheck configured: {bool(config.HEALTHCHECK_URL)}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="aria-sync")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("google-auth", help="Interactive Google OAuth consent; saves a refresh token")
    p.add_argument("--port", type=int, default=8080, help="localhost callback port (default 8080)")
    p.add_argument("--no-browser", action="store_true", help="print the URL instead of opening a browser")
    p.set_defaults(func=cmd_google_auth)

    p = sub.add_parser("google-status", help="Refresh the token and show the linked Google Health identity")
    p.set_defaults(func=cmd_google_status)

    p = sub.add_parser("google-fetch", help="Dump recent weight/body-fat data points as JSON")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--types", nargs="+", default=["weight", "body-fat"])
    p.add_argument("--no-filter", action="store_true", help="skip the time filter (if the API rejects it)")
    p.set_defaults(func=cmd_google_fetch)

    p = sub.add_parser("garmin-login", help="Interactive Garmin login (password + email MFA); saves tokens")
    p.add_argument("--email")
    p.set_defaults(func=cmd_garmin_login)

    p = sub.add_parser("garmin-check", help="Log in with saved tokens and list recent Garmin weigh-ins")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_garmin_check)

    p = sub.add_parser("push-latest", help="Upload the most recent Google reading to Garmin")
    p.add_argument("--days", type=int, default=2, help="how far back to look in Google (default 2)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="upload even if Garmin has a weigh-in at that time")
    p.set_defaults(func=cmd_push_latest)

    p = sub.add_parser("backfill", help="Upload every Google reading since a date that Garmin doesn't have")
    p.add_argument("--since", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_backfill)

    p = sub.add_parser("run", help="Poll forever: sync new readings, alert to Slack, ping healthchecks.io")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("sync-once", help="Run a single sync cycle")
    p.set_defaults(func=cmd_sync_once)

    p = sub.add_parser("test-alerts", help="Send a test Slack message and healthcheck ping")
    p.set_defaults(func=cmd_test_alerts)

    args = parser.parse_args()
    try:
        args.func(args)
    except (AuthError, HealthApiError, garmin.GarminAuthError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
