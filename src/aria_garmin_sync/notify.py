"""Slack messages and healthchecks.io pings. Both are best-effort and never raise."""

import logging

import requests

from . import config

log = logging.getLogger(__name__)


def slack(text: str) -> None:
    if not config.SLACK_WEBHOOK:
        log.info("Slack not configured; would have sent: %s", text)
        return
    try:
        requests.post(config.SLACK_WEBHOOK, json={"text": text}, timeout=10).raise_for_status()
    except requests.RequestException as e:
        log.warning("Slack post failed: %s", e)


def healthcheck(ok: bool, message: str = "") -> None:
    if not config.HEALTHCHECK_URL:
        return
    url = config.HEALTHCHECK_URL.rstrip("/") + ("" if ok else "/fail")
    try:
        requests.post(url, data=message.encode()[:10000], timeout=10)
    except requests.RequestException as e:
        log.warning("Healthcheck ping failed: %s", e)
