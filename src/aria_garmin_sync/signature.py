"""Verify GOOGLE-HEALTH-API-SIGNATURE headers (Tink ECDSA P-256/SHA-256, TINK output prefix)."""

import base64
import logging
import threading
import time

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

log = logging.getLogger(__name__)

KEYSET_URL = "https://www.gstatic.com/googlehealthapi/webhooks/webhooks_public_keyset.json"
REFETCH_MIN_INTERVAL = 600  # seconds; limits refetches triggered by unknown key IDs


def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def _parse_ecdsa_public_key(blob: bytes) -> ec.EllipticCurvePublicKey:
    """Pull x (field 3) and y (field 4) out of a serialized Tink EcdsaPublicKey protobuf."""
    fields = {}
    i = 0
    while i < len(blob):
        tag, i = _read_varint(blob, i)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            fields[field], i = _read_varint(blob, i)
        elif wire == 2:
            length, i = _read_varint(blob, i)
            fields[field] = blob[i : i + length]
            i += length
        else:
            raise ValueError(f"unexpected protobuf wire type {wire}")
    x = int.from_bytes(fields[3], "big")
    y = int.from_bytes(fields[4], "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()


class Verifier:
    def __init__(self) -> None:
        self._keys: dict[int, ec.EllipticCurvePublicKey] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def _refresh(self) -> None:
        resp = requests.get(KEYSET_URL, timeout=10)
        resp.raise_for_status()
        keys = {}
        for k in resp.json()["key"]:
            if k.get("status") == "ENABLED" and k.get("outputPrefixType") == "TINK":
                keys[k["keyId"]] = _parse_ecdsa_public_key(base64.b64decode(k["keyData"]["value"]))
        self._keys = keys
        self._fetched_at = time.time()
        log.info("Loaded %d webhook signing keys", len(keys))

    def _key(self, key_id: int) -> ec.EllipticCurvePublicKey | None:
        with self._lock:
            if key_id not in self._keys and time.time() - self._fetched_at > REFETCH_MIN_INTERVAL:
                self._refresh()
            return self._keys.get(key_id)

    def verify(self, body: bytes, header: str | None) -> bool:
        if not header:
            return False
        try:
            sig = base64.b64decode(header)
        except ValueError:
            return False
        if len(sig) < 6 or sig[0] != 0x01:  # TINK prefix: 0x01 + 4-byte key ID
            return False
        key = self._key(int.from_bytes(sig[1:5], "big"))
        if key is None:
            return False
        try:
            key.verify(sig[5:], body, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False
