import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from aria_garmin_sync.signature import Verifier, _parse_ecdsa_public_key

FIXTURE = Path(__file__).parent / "fixtures" / "webhooks_public_keyset.json"


def _tink_ecdsa_public_key(pub: ec.EllipticCurvePublicKey) -> bytes:
    """Serialize like Tink's EcdsaPublicKey: params (2), x (3), y (4), with a leading zero byte."""
    nums = pub.public_numbers()
    x = b"\x00" + nums.x.to_bytes(32, "big")
    y = b"\x00" + nums.y.to_bytes(32, "big")
    params = b"\x08\x03\x10\x02\x18\x02"
    return b"\x12" + bytes([len(params)]) + params + b"\x1a\x21" + x + b"\x22\x21" + y


def test_parses_googles_published_keyset():
    keys = json.loads(FIXTURE.read_text())["key"]
    assert keys
    for k in keys:
        _parse_ecdsa_public_key(base64.b64decode(k["keyData"]["value"]))  # raises if not on P-256


def test_round_trip_parse_matches_key():
    priv = ec.generate_private_key(ec.SECP256R1())
    parsed = _parse_ecdsa_public_key(_tink_ecdsa_public_key(priv.public_key()))
    assert parsed.public_numbers() == priv.public_key().public_numbers()


def _verifier_with(key_id, pub):
    v = Verifier()
    v._keys = {key_id: pub}
    v._fetched_at = float("inf")  # never refetch in tests
    return v


def _sign(priv, key_id, body):
    sig = priv.sign(body, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(b"\x01" + key_id.to_bytes(4, "big") + sig).decode()


def test_verify_accepts_valid_and_rejects_tampered_or_unknown():
    priv = ec.generate_private_key(ec.SECP256R1())
    v = _verifier_with(7, priv.public_key())
    body = b'[{"data":{"operation":"UPSERT"}}]'
    assert v.verify(body, _sign(priv, 7, body))
    assert not v.verify(body + b" ", _sign(priv, 7, body))
    assert not v.verify(body, _sign(priv, 8, body))
    assert not v.verify(body, None)
    assert not v.verify(body, "not base64!!")
