"""Slack webhook events: verify the request signature, persist the raw event, and enqueue
route_message (returns a SlackHandlerResult)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import structlog
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import Settings
from evercurrent.connectors.slack.schemas import SlackEventEnvelope
from evercurrent.db import models
from evercurrent.tenancy.org_context import set_org_context

log = structlog.get_logger(__name__)

SIGNATURE_SKEW_SECONDS = 60 * 5


class EnqueueRouteMessage(Protocol):
    def __call__(self, *, raw_event_id: uuid.UUID) -> None: ...


@dataclass(frozen=True)
class SlackHandlerResult:
    status_code: int
    body: dict[str, Any]
    raw_event_id: uuid.UUID | None = None


def verify_signature(
    *,
    body: bytes,
    timestamp: str,
    signature: str,
    signing_secret: str,
    now: float | None = None,
) -> bool:
    if not timestamp or not signature or not signing_secret:
        return False
    try:
        ts_float = float(timestamp)
    except ValueError:
        return False
    current = now if now is not None else time.time()
    if abs(current - ts_float) > SIGNATURE_SKEW_SECONDS:
        return False
    basestring = f"v0:{timestamp}:".encode() + body
    expected = (
        "v0="
        + hmac.new(
            signing_secret.encode(),
            basestring,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


async def handle_event(
    *,
    session: AsyncSession,
    settings: Settings,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    enqueue_route_message: EnqueueRouteMessage | None = None,
    now: float | None = None,
) -> SlackHandlerResult:
    payload = _parse_envelope(body)

    if payload.type == "url_verification":
        challenge = payload.challenge or ""
        return SlackHandlerResult(status_code=200, body={"challenge": challenge})

    if settings.slack_signing_secret is None:
        log.error("slack.events.signing_secret_missing")
        return SlackHandlerResult(status_code=503, body={"ok": False})

    valid = verify_signature(
        body=body,
        timestamp=timestamp or "",
        signature=signature or "",
        signing_secret=settings.slack_signing_secret,
        now=now,
    )
    if not valid:
        log.warning("slack.events.bad_signature")
        return SlackHandlerResult(status_code=401, body={"ok": False})

    if payload.team_id is None:
        return SlackHandlerResult(status_code=200, body={"ok": True})

    connector = (
        await session.execute(
            select(models.Connector).where(
                models.Connector.kind == "slack",
                models.Connector.external_team_id == payload.team_id,
            ),
        )
    ).scalar_one_or_none()
    if connector is None or connector.status != "active":
        log.info("slack.events.unknown_team", team_id=payload.team_id)
        return SlackHandlerResult(status_code=200, body={"ok": True})

    await set_org_context(session, connector.org_id)

    event = payload.event
    if event is None:
        return SlackHandlerResult(status_code=200, body={"ok": True})
    if event.subtype is not None:
        log.info(
            "slack.events.subtype_skipped",
            subtype=event.subtype,
            ts=event.ts,
        )
        return SlackHandlerResult(status_code=200, body={"ok": True})

    raw_event_id = await _persist_raw_event(
        session=session,
        org_id=connector.org_id,
        external_id=event.ts,
        body=body,
    )
    if raw_event_id is None:
        return SlackHandlerResult(status_code=200, body={"ok": True})

    if enqueue_route_message is not None:
        try:
            enqueue_route_message(raw_event_id=raw_event_id)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "slack.events.enqueue_failed",
                raw_event_id=str(raw_event_id),
                error=str(exc),
            )

    return SlackHandlerResult(
        status_code=200,
        body={"ok": True},
        raw_event_id=raw_event_id,
    )


def _parse_envelope(body: bytes) -> SlackEventEnvelope:
    try:
        data = json.loads(body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return SlackEventEnvelope(type="event_callback")
    return SlackEventEnvelope.model_validate(data)


async def _persist_raw_event(
    *,
    session: AsyncSession,
    org_id: uuid.UUID,
    external_id: str,
    body: bytes,
) -> uuid.UUID | None:
    payload_json = body.decode()
    try:
        result = await session.execute(
            text(
                "INSERT INTO raw_events (org_id, source, external_id, payload) "
                "VALUES (:org_id, :source, :external_id, CAST(:payload AS jsonb)) "
                "ON CONFLICT (source, external_id) DO NOTHING "
                "RETURNING id",
            ),
            {
                "org_id": str(org_id),
                "source": "slack",
                "external_id": external_id,
                "payload": payload_json,
            },
        )
        row = result.scalar_one_or_none()
        await session.commit()
    except IntegrityError:
        await session.rollback()
        log.info("slack.events.duplicate", external_id=external_id)
        return None
    if row is None:
        log.info("slack.events.duplicate", external_id=external_id)
        return None
    return uuid.UUID(str(row))
