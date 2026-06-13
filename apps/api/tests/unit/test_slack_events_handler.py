from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from evercurrent.config import Settings
from evercurrent.connectors.slack.events import handle_event


def _settings_with_secret(secret: str = "test_signing_secret") -> Settings:
    return Settings(slack_signing_secret=secret)


def _sign(body: bytes, timestamp: str, secret: str) -> str:
    basestring = f"v0:{timestamp}:".encode() + body
    digest = hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _fake_connector(*, status: str = "active") -> Any:
    conn = MagicMock()
    conn.id = uuid.uuid4()
    conn.org_id = uuid.uuid4()
    conn.kind = "slack"
    conn.status = status
    conn.external_team_id = "T123"
    return conn


def _fake_session(
    *,
    connector: Any | None,
    insert_result: uuid.UUID | None,
) -> AsyncMock:
    session = AsyncMock()
    connector_lookup = MagicMock()
    connector_lookup.scalar_one_or_none.return_value = connector
    insert_lookup = MagicMock()
    insert_lookup.scalar_one_or_none.return_value = (
        str(insert_result) if insert_result is not None else None
    )

    calls = {"n": 0}

    async def execute(*_args: Any, **_kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            return connector_lookup
        if calls["n"] == 2:
            return MagicMock()
        return insert_lookup

    session.execute.side_effect = execute
    return session


@pytest.mark.asyncio
async def test_url_verification_returns_challenge_without_signature() -> None:
    body = json.dumps({"type": "url_verification", "challenge": "abc123"}).encode()
    session = AsyncMock()

    result = await handle_event(
        session=session,
        settings=_settings_with_secret(),
        body=body,
        timestamp=None,
        signature=None,
    )

    assert result.status_code == 200
    assert result.body == {"challenge": "abc123"}


@pytest.mark.asyncio
async def test_bad_signature_returns_401() -> None:
    body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T123",
            "event": {"type": "message", "ts": "1717800000.000100", "channel": "C1"},
        },
    ).encode()
    session = AsyncMock()
    timestamp = str(int(time.time()))

    result = await handle_event(
        session=session,
        settings=_settings_with_secret(),
        body=body,
        timestamp=timestamp,
        signature="v0=deadbeef",
    )

    assert result.status_code == 401


@pytest.mark.asyncio
async def test_unknown_team_returns_200_no_insert() -> None:
    body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T-UNKNOWN",
            "event": {"type": "message", "ts": "1717800000.000100"},
        },
    ).encode()
    timestamp = str(int(time.time()))
    secret = "test_signing_secret"
    signature = _sign(body, timestamp, secret)

    session = _fake_session(connector=None, insert_result=None)
    enqueue = MagicMock()

    result = await handle_event(
        session=session,
        settings=_settings_with_secret(secret),
        body=body,
        timestamp=timestamp,
        signature=signature,
        enqueue_route_message=enqueue,
        now=float(timestamp),
    )

    assert result.status_code == 200
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_event_persists_and_enqueues_route_message() -> None:
    body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "ts": "1717800000.000100",
                "channel": "C1",
                "user": "U1",
                "text": "hello",
            },
        },
    ).encode()
    timestamp = str(int(time.time()))
    secret = "test_signing_secret"
    signature = _sign(body, timestamp, secret)
    raw_event_id = uuid.uuid4()

    connector = _fake_connector()
    session = _fake_session(connector=connector, insert_result=raw_event_id)
    enqueue = MagicMock()

    result = await handle_event(
        session=session,
        settings=_settings_with_secret(secret),
        body=body,
        timestamp=timestamp,
        signature=signature,
        enqueue_route_message=enqueue,
        now=float(timestamp),
    )

    assert result.status_code == 200
    assert result.raw_event_id == raw_event_id
    enqueue.assert_called_once_with(raw_event_id=raw_event_id)


@pytest.mark.asyncio
async def test_duplicate_event_returns_200_without_enqueue() -> None:
    body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "ts": "1717800000.000100",
                "channel": "C1",
            },
        },
    ).encode()
    timestamp = str(int(time.time()))
    secret = "test_signing_secret"
    signature = _sign(body, timestamp, secret)

    connector = _fake_connector()
    session = _fake_session(connector=connector, insert_result=None)
    enqueue = MagicMock()

    result = await handle_event(
        session=session,
        settings=_settings_with_secret(secret),
        body=body,
        timestamp=timestamp,
        signature=signature,
        enqueue_route_message=enqueue,
        now=float(timestamp),
    )

    assert result.status_code == 200
    assert result.raw_event_id is None
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_subtype_message_skipped() -> None:
    body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "subtype": "message_changed",
                "ts": "1717800000.000100",
            },
        },
    ).encode()
    timestamp = str(int(time.time()))
    secret = "test_signing_secret"
    signature = _sign(body, timestamp, secret)

    connector = _fake_connector()
    session = _fake_session(connector=connector, insert_result=None)
    enqueue = MagicMock()

    result = await handle_event(
        session=session,
        settings=_settings_with_secret(secret),
        body=body,
        timestamp=timestamp,
        signature=signature,
        enqueue_route_message=enqueue,
        now=float(timestamp),
    )

    assert result.status_code == 200
    enqueue.assert_not_called()
