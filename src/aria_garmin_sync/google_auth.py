"""Google OAuth: one-off interactive consent, then refresh-token reuse."""

import json
import os
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config


class AuthError(RuntimeError):
    pass


def _write_secret(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    os.chmod(path, 0o600)


def authorize(port: int = 8080, open_browser: bool = True) -> dict:
    """Run the consent flow on a localhost callback and save the token.

    Returns metadata from the token response, including
    refresh_token_expires_in when Google sets one (Testing mode = 7 days).
    """
    if not config.GOOGLE_CLIENT_SECRET.exists():
        raise AuthError(
            f"OAuth client file not found at {config.GOOGLE_CLIENT_SECRET}. "
            "Download it from the Cloud console (see docs/google-oauth-setup.md)."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.GOOGLE_CLIENT_SECRET), scopes=config.GOOGLE_SCOPES
    )
    creds = flow.run_local_server(
        host="localhost",
        port=port,
        open_browser=open_browser,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message="Open this URL in a browser signed in to your personal Google account:\n{url}\n",
        success_message="Authorised. You can close this tab.",
    )
    if not creds.refresh_token:
        raise AuthError("Google did not return a refresh token; re-run so prompt=consent is honoured.")

    token = flow.oauth2session.token
    meta = {
        "issued_at": int(time.time()),
        "refresh_token_expires_in": token.get("refresh_token_expires_in"),
        "scope": token.get("scope"),
    }
    _write_secret(config.GOOGLE_TOKEN, creds.to_json())
    _write_secret(config.GOOGLE_TOKEN_META, json.dumps(meta, indent=2))
    return meta


def load_credentials() -> Credentials:
    """Load saved credentials, refreshing (and re-saving) the access token if needed."""
    if not config.GOOGLE_TOKEN.exists():
        raise AuthError(f"No Google token at {config.GOOGLE_TOKEN}; run `aria-sync google-auth` first.")

    creds = Credentials.from_authorized_user_file(str(config.GOOGLE_TOKEN), config.GOOGLE_SCOPES)
    if not creds.valid:
        try:
            creds.refresh(Request())
        except Exception as e:  # google.auth.exceptions.RefreshError and transport errors
            raise AuthError(f"Google token refresh failed ({e}); re-run `aria-sync google-auth`.") from e
        _write_secret(config.GOOGLE_TOKEN, creds.to_json())
    return creds


def load_meta() -> dict:
    try:
        return json.loads(config.GOOGLE_TOKEN_META.read_text())
    except FileNotFoundError:
        return {}
