from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from evercurrent.connectors.slack.client import SlackAPIError, SlackClient
from evercurrent.notify import slack_deliver
from evercurrent.notify.slack_deliver import (
    SlackRateLimitedError,
    deliver_digest_dm,
)


def _fake_digest(*, day_index: int = 14, phase: str = "DVT") -> Any:
    digest = MagicMock()
    digest.id = uuid.uuid4()
    digest.project_member_id = uuid.uuid4()
    digest.day_index = day_index
    digest.phase = phase
    digest.content_md = "## Top\n- one\n## FYI\n- two\n"
    return digest


def _fake_membership(
    *,
    slack_user_id: str | None = "U1",
    quiet_start: dt.time | None = dt.time(22, 0),
    quiet_end: dt.time | None = dt.time(7, 0),
    timezone: str = "UTC",
) -> Any:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.org_id = uuid.uuid4()
    m.slack_user_id = slack_user_id
    m.timezone = timezone
    m.quiet_start = quiet_start
    m.quiet_end = quiet_end
    m.display_name = "Sarah"
    return m


def _fake_subscription(*, enabled: bool, value: str | None = None) -> Any:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.enabled = enabled
    s.value = value
    return s


class _FakeSlackClient:
    def __init__(
        self, *, response: dict[str, Any] | None = None, raise_error: SlackAPIError | None = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response = response or {"ok": True, "ts": "1717800000.000100", "channel": "D1"}
        self._raise = raise_error

    async def chat_post_message(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        return self._response

    async def aclose(self) -> None:
        return None


def _install_session(
    monkeypatch: pytest.MonkeyPatch,
    *,
    digest: Any,
    membership: Any | None,
    subscription: Any | None,
    bot_token: str | None = "xoxb-test",
) -> tuple[AsyncMock, list[Any]]:
    session = AsyncMock()
    session.commit = AsyncMock(return_value=None)
    inserts: list[Any] = []

    async def fake_load_digest(_session: Any, _digest_id: uuid.UUID) -> Any:
        if membership is None:
            return None
        return (digest, membership)

    async def fake_load_subscription(
        _session: Any,
        *,
        membership_id: uuid.UUID,
        kind: str,
    ) -> Any:
        _ = membership_id, kind
        return subscription

    async def fake_load_token(_session: Any, *, org_id: uuid.UUID) -> Any:
        _ = org_id
        return bot_token

    async def fake_insert_notification(
        _session: Any,
        *,
        org_id: uuid.UUID,
        membership_id: uuid.UUID,
        kind: str,
        channel: str,
        payload: dict[str, Any],
    ) -> uuid.UUID:
        record = {
            "org_id": org_id,
            "membership_id": membership_id,
            "kind": kind,
            "channel": channel,
            "payload": payload,
        }
        inserts.append(record)
        return uuid.uuid4()

    async def fake_set_org_context(_session: Any, _org_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(slack_deliver, "_load_digest_member", fake_load_digest)
    monkeypatch.setattr(slack_deliver, "_load_subscription", fake_load_subscription)
    monkeypatch.setattr(slack_deliver, "_load_bot_token", fake_load_token)
    monkeypatch.setattr(slack_deliver, "set_org_context", fake_set_org_context)
    monkeypatch.setattr(
        slack_deliver.repository,
        "insert_notification",
        fake_insert_notification,
    )
    return session, inserts


@pytest.mark.asyncio
async def test_digest_dm_skips_when_subscription_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    digest = _fake_digest()
    membership = _fake_membership()
    subscription = _fake_subscription(enabled=False)
    session, inserts = _install_session(
        monkeypatch,
        digest=digest,
        membership=membership,
        subscription=subscription,
    )
    slack = _FakeSlackClient()

    result = await deliver_digest_dm(
        session,
        digest.id,
        slack_client=cast("SlackClient", slack),
        now=dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC),
    )

    assert result.status == "skipped"
    assert result.reason == "subscription_disabled"
    assert slack.calls == []
    assert len(inserts) == 1
    assert inserts[0]["channel"] == "skipped"


@pytest.mark.asyncio
async def test_429_raises_for_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    digest = _fake_digest()
    membership = _fake_membership()
    subscription = _fake_subscription(enabled=True)
    session, _ = _install_session(
        monkeypatch,
        digest=digest,
        membership=membership,
        subscription=subscription,
    )
    slack = _FakeSlackClient(
        raise_error=SlackAPIError("chat.postMessage", "ratelimited"),
    )

    with pytest.raises(SlackRateLimitedError):
        await deliver_digest_dm(
            session,
            digest.id,
            slack_client=cast("SlackClient", slack),
            now=dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC),
        )


@pytest.mark.asyncio
async def test_quiet_hours_returns_deferred(monkeypatch: pytest.MonkeyPatch) -> None:
    digest = _fake_digest()
    membership = _fake_membership(
        timezone="UTC",
        quiet_start=dt.time(22, 0),
        quiet_end=dt.time(7, 0),
    )
    subscription = _fake_subscription(enabled=True)
    session, inserts = _install_session(
        monkeypatch,
        digest=digest,
        membership=membership,
        subscription=subscription,
    )
    slack = _FakeSlackClient()

    result = await deliver_digest_dm(
        session,
        digest.id,
        slack_client=cast("SlackClient", slack),
        now=dt.datetime(2026, 6, 7, 23, 0, tzinfo=dt.UTC),
    )

    assert result.status == "deferred"
    assert result.deferred_eta is not None
    assert result.deferred_eta == dt.datetime(2026, 6, 8, 7, 0, tzinfo=dt.UTC)
    assert slack.calls == []
    assert inserts == []


@pytest.mark.asyncio
async def test_force_quiet_bypasses_quiet_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    digest = _fake_digest()
    membership = _fake_membership(
        timezone="UTC",
        quiet_start=dt.time(22, 0),
        quiet_end=dt.time(7, 0),
    )
    subscription = _fake_subscription(enabled=True)
    session, inserts = _install_session(
        monkeypatch,
        digest=digest,
        membership=membership,
        subscription=subscription,
    )
    slack = _FakeSlackClient()

    result = await deliver_digest_dm(
        session,
        digest.id,
        slack_client=cast("SlackClient", slack),
        force_quiet=True,
        now=dt.datetime(2026, 6, 7, 23, 0, tzinfo=dt.UTC),
    )

    assert result.status == "sent"
    assert len(slack.calls) == 1
    assert len(inserts) == 1
    assert inserts[0]["channel"] == "slack_dm"


@pytest.mark.asyncio
async def test_notifications_row_persisted_with_sent_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    digest = _fake_digest()
    membership = _fake_membership(
        timezone="UTC",
        quiet_start=None,
        quiet_end=None,
    )
    subscription = _fake_subscription(enabled=True)
    session, inserts = _install_session(
        monkeypatch,
        digest=digest,
        membership=membership,
        subscription=subscription,
    )
    slack = _FakeSlackClient(
        response={"ok": True, "ts": "1717800000.000100", "channel": "D1"},
    )

    result = await deliver_digest_dm(
        session,
        digest.id,
        slack_client=cast("SlackClient", slack),
        now=dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC),
    )

    assert result.status == "sent"
    assert len(inserts) == 1
    row = inserts[0]
    assert row["channel"] == "slack_dm"
    assert row["kind"] == "morning_digest"
    assert row["payload"]["ts"] == "1717800000.000100"
    assert row["payload"]["channel"] == "D1"


@pytest.mark.asyncio
async def test_missing_slack_user_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    digest = _fake_digest()
    membership = _fake_membership(slack_user_id=None)
    session, inserts = _install_session(
        monkeypatch,
        digest=digest,
        membership=membership,
        subscription=None,
    )
    slack = _FakeSlackClient()

    result = await deliver_digest_dm(
        session,
        digest.id,
        slack_client=cast("SlackClient", slack),
        now=dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC),
    )

    assert result.status == "skipped"
    assert result.reason == "no_slack_user"
    assert slack.calls == []
    assert inserts == []
