import base64
import json
import time

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from aria_garmin_sync import config, webhook

SECRET = "Bearer s3cret"
PATH = "/hook/abc"


@pytest.fixture
def receiver(monkeypatch):
    import threading

    monkeypatch.setattr(config, "WEBHOOK_PATH", PATH)
    monkeypatch.setattr(config, "WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(config, "WEBHOOK_PORT", 0)
    monkeypatch.setattr(config, "WEBHOOK_VERIFY_SIGNATURE", True)
    wake = threading.Event()
    server = webhook.start(wake)
    priv = ec.generate_private_key(ec.SECP256R1())
    server.RequestHandlerClass.verifier._keys = {42: priv.public_key()}
    server.RequestHandlerClass.verifier._fetched_at = float("inf")
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base, wake, priv
    server.shutdown()


def _sign(priv, body):
    sig = priv.sign(body, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(b"\x01" + (42).to_bytes(4, "big") + sig).decode()


VERIFY = b'{"type": "verification"}'
NOTE = json.dumps([{"data": {"operation": "UPSERT", "dataType": "weight", "intervals": []}}]).encode()


def test_disabled_without_config(monkeypatch):
    import threading

    monkeypatch.setattr(config, "WEBHOOK_PATH", "")
    assert webhook.start(threading.Event()) is None


def test_verification_handshake(receiver):
    base, _, _ = receiver
    assert requests.post(base + PATH, data=VERIFY, headers={"Authorization": SECRET}).status_code == 200
    assert requests.post(base + PATH, data=VERIFY).status_code == 401


def test_everything_else_is_rejected(receiver):
    base, wake, priv = receiver
    auth = {"Authorization": SECRET}
    assert requests.get(base + PATH).status_code == 404
    assert requests.post(base + "/other", data=VERIFY, headers=auth).status_code == 404
    assert requests.post(base + PATH, data=NOTE, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert requests.post(base + PATH, data=NOTE, headers=auth).status_code == 403
    tampered = {**auth, "GOOGLE-HEALTH-API-SIGNATURE": _sign(priv, NOTE)}
    assert requests.post(base + PATH, data=NOTE.replace(b"weight", b"steps "), headers=tampered).status_code == 403
    assert requests.post(base + PATH, data=b"x" * 300_000, headers=auth).status_code == 413
    assert not wake.is_set()


def test_signed_upsert_wakes_loop(receiver):
    base, wake, priv = receiver
    headers = {"Authorization": SECRET, "GOOGLE-HEALTH-API-SIGNATURE": _sign(priv, NOTE)}
    assert requests.post(base + PATH, data=NOTE, headers=headers).status_code == 204
    assert wake.wait(2)


def test_chunked_body(receiver):
    base, _, _ = receiver

    def gen():
        yield b'{"type": '
        yield b'"verification"}'

    assert requests.post(base + PATH, data=gen(), headers={"Authorization": SECRET}).status_code == 200
