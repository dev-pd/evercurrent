"""Unit tests for Slack HMAC signature verification.

Covers the four bits that matter: valid signature accepted, tampered
body rejected, old timestamp rejected (replay protection), wrong
signing secret rejected.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from evercurrent.connectors.slack.events import verify_signature


def _sign(secret: str, body: bytes, timestamp: str) -> str:
    basestring = f"v0:{timestamp}:".encode() + body
    digest = hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def test_valid_signature_accepted() -> None:
    secret = "test_signing_secret"
    body = b'{"type":"event_callback","team_id":"T1"}'
    timestamp = str(int(time.time()))
    signature = _sign(secret, body, timestamp)

    assert verify_signature(
        body=body,
        timestamp=timestamp,
        signature=signature,
        signing_secret=secret,
        now=float(timestamp),
    )


def test_tampered_body_rejected() -> None:
    secret = "test_signing_secret"
    body = b'{"type":"event_callback","team_id":"T1"}'
    timestamp = str(int(time.time()))
    signature = _sign(secret, body, timestamp)

    tampered = body[:-1] + b"X"
    assert not verify_signature(
        body=tampered,
        timestamp=timestamp,
        signature=signature,
        signing_secret=secret,
        now=float(timestamp),
    )


def test_old_timestamp_rejected() -> None:
    secret = "test_signing_secret"
    body = b'{"type":"event_callback","team_id":"T1"}'
    now = time.time()
    old_ts = str(int(now - 60 * 6))
    signature = _sign(secret, body, old_ts)

    assert not verify_signature(
        body=body,
        timestamp=old_ts,
        signature=signature,
        signing_secret=secret,
        now=now,
    )


def test_wrong_secret_rejected() -> None:
    body = b'{"type":"event_callback","team_id":"T1"}'
    timestamp = str(int(time.time()))
    signature = _sign("first_secret", body, timestamp)

    assert not verify_signature(
        body=body,
        timestamp=timestamp,
        signature=signature,
        signing_secret="other_secret",
        now=float(timestamp),
    )


def test_missing_inputs_rejected() -> None:
    assert not verify_signature(
        body=b"{}",
        timestamp="",
        signature="",
        signing_secret="x",
    )


def test_non_numeric_timestamp_rejected() -> None:
    assert not verify_signature(
        body=b"{}",
        timestamp="not-a-number",
        signature="v0=abc",
        signing_secret="x",
    )
