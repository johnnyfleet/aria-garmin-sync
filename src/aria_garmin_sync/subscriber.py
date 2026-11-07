"""Manage the Google Health API webhook subscriber (run from a machine with gcloud)."""

import subprocess

import requests

from . import config

SUBSCRIBER_ID = "aria-garmin-sync"
DATA_TYPES = ["weight", "body-fat"]


def _session(project_number: str) -> requests.Session:
    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"], check=True, capture_output=True, text=True
    ).stdout.strip()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "x-goog-user-project": project_number})
    return s


def _url(project_number: str, suffix: str = "") -> str:
    return f"{config.HEALTH_API_BASE}/projects/{project_number}/subscribers{suffix}"


def _check(resp: requests.Response) -> dict:
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.json() if resp.content else {}


def create(project_number: str, endpoint: str, secret: str) -> dict:
    body = {
        "endpointUri": endpoint,
        "subscriberConfigs": [{"dataTypes": DATA_TYPES, "subscriptionCreatePolicy": "AUTOMATIC"}],
        "endpointAuthorization": {"secret": secret},
    }
    return _check(
        _session(project_number).post(
            _url(project_number), params={"subscriberId": SUBSCRIBER_ID}, json=body, timeout=60
        )
    )


def list_all(project_number: str) -> dict:
    return _check(_session(project_number).get(_url(project_number), timeout=30))


def delete(project_number: str) -> dict:
    return _check(_session(project_number).delete(_url(project_number, f"/{SUBSCRIBER_ID}"), timeout=30))
