"""Receiver for Google Health API webhook notifications.

Only one path is served; everything else is a 404. Notifications are just a
wake-up signal: the sync loop re-reads Google itself, so a forged request can at
worst cause an extra poll.
"""

import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config
from .signature import Verifier

log = logging.getLogger(__name__)

MAX_BODY = 256 * 1024
MAX_CONCURRENT = 8


class _Handler(BaseHTTPRequestHandler):
    server_version = "aria-sync"
    sys_version = ""
    timeout = 10  # per-connection socket timeout

    wake: threading.Event
    verifier: Verifier
    slots = threading.BoundedSemaphore(MAX_CONCURRENT)

    def log_message(self, fmt, *args):  # route through logging, quietly
        log.debug("%s %s", self.address_string(), fmt % args)

    def _reply(self, code: int) -> None:
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._reply(404)

    do_PUT = do_DELETE = do_PATCH = do_HEAD = do_GET

    def do_POST(self):
        if not self.slots.acquire(blocking=False):
            return self._reply(503)
        try:
            self._handle_post()
        finally:
            self.slots.release()

    def _handle_post(self):
        if self.path.split("?", 1)[0] != config.WEBHOOK_PATH:
            return self._reply(404)
        if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), config.WEBHOOK_SECRET.encode()):
            log.info("Rejected webhook with bad/missing Authorization")
            return self._reply(401)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._reply(400)
        if length > MAX_BODY:
            return self._reply(413)
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except ValueError:
            return self._reply(400)

        if isinstance(payload, dict) and payload.get("type") == "verification":
            log.info("Answered webhook verification request")
            return self._reply(200)

        if config.WEBHOOK_VERIFY_SIGNATURE and not self.verifier.verify(
            body, self.headers.get("GOOGLE-HEALTH-API-SIGNATURE")
        ):
            log.warning("Rejected webhook with invalid signature")
            return self._reply(403)

        notifications = payload if isinstance(payload, list) else [payload]
        for n in notifications:
            data = n.get("data", n) if isinstance(n, dict) else {}
            log.info("Webhook: %s %s", data.get("operation"), data.get("dataType"))
        self._reply(204)
        if any(
            isinstance(n, dict) and n.get("data", n).get("operation") == "UPSERT" for n in notifications
        ):
            self.wake.set()


def start(wake: threading.Event) -> ThreadingHTTPServer | None:
    """Start the receiver in a background thread, or return None if it isn't configured."""
    if not (config.WEBHOOK_PATH and config.WEBHOOK_SECRET):
        log.info("Webhook receiver disabled (ARIA_SYNC_WEBHOOK_PATH / _SECRET not set)")
        return None
    handler = type("Handler", (_Handler,), {"wake": wake, "verifier": Verifier()})
    server = ThreadingHTTPServer(("0.0.0.0", config.WEBHOOK_PORT), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="webhook", daemon=True).start()
    log.info("Webhook receiver listening on :%d", config.WEBHOOK_PORT)
    return server
