"""Command-line entry point: `aria-sync <command>`."""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta

from . import config
from .google_auth import AuthError, authorize, load_credentials, load_meta
from .health import HealthApiError, HealthClient, since_filter


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


def main() -> None:
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

    args = parser.parse_args()
    try:
        args.func(args)
    except (AuthError, HealthApiError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
