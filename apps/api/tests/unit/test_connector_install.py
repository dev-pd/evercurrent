from __future__ import annotations

import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from evercurrent.config import Settings
from evercurrent.connectors.slack import install as slack_install
from evercurrent.connectors.slack.client import SlackClient
from evercurrent.connectors.slack.crypto import TokenVault, generate_key


def _settings() -> Settings:
    return Settings(
        slack_client_id="client-id",
        slack_client_secret="client-secret",
        connector_secret_key=generate_key(),
        webhook_public_url="https://example.test",
    )


def _client_with_oauth_response(payload: dict[str, Any]) -> SlackClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://slack.com/api",
    )
    return SlackClient(client=async_client)


def test_build_install_url_contains_required_query_params() -> None:
    settings = _settings()
    org_id = uuid.uuid4()

    url = slack_install.build_install_url(org_id=org_id, settings=settings)

    assert url.startswith("https://slack.com/oauth/v2/authorize?")
    assert "client_id=client-id" in url
    assert "scope=channels%3Ahistory" in url
    assert "redirect_uri=https" in url
    assert "state=" in url


def test_encoded_state_round_trips() -> None:
    settings = _settings()
    org_id = uuid.uuid4()

    token = slack_install.encode_state(org_id, settings=settings)
    decoded = slack_install.decode_state(token, settings=settings)

    assert decoded.org_id == org_id


def test_decode_state_rejects_expired_token() -> None:
    settings = _settings()
    org_id = uuid.uuid4()
    long_ago = int(time.time()) - 60 * 60

    token = slack_install.encode_state(org_id, settings=settings, now=long_ago)

    with pytest.raises(slack_install.InstallStateError):
        slack_install.decode_state(token, settings=settings)


def test_decode_state_rejects_mismatched_signature() -> None:
    settings = _settings()
    org_id = uuid.uuid4()
    token = slack_install.encode_state(org_id, settings=settings)

    with pytest.raises(slack_install.InstallStateError):
        slack_install.decode_state(token + "x", settings=settings)


@pytest.mark.asyncio
async def test_callback_inserts_new_connector_with_encrypted_token() -> None:
    settings = _settings()
    vault = TokenVault(settings.connector_secret_key or "")
    org_id = uuid.uuid4()
    state = slack_install.encode_state(org_id, settings=settings)

    session = AsyncMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = None
    session.execute.return_value = select_result

    added: list[Any] = []

    def _capture_add(row: Any) -> None:
        added.append(row)

    session.add = _capture_add

    client = _client_with_oauth_response(
        {
            "ok": True,
            "access_token": "xoxb-bot-token-fresh",
            "team": {"id": "T-NEW", "name": "Demo"},
        },
    )

    connector_id = await slack_install.exchange_and_persist(
        session=session,
        settings=settings,
        vault=vault,
        code="auth-code",
        state_token=state,
        installed_by_membership_id=None,
        slack_client=client,
    )

    assert connector_id is not None
    assert added, "connector row should have been added"
    new_row = added[0]
    assert new_row.kind == "slack"
    assert new_row.external_team_id == "T-NEW"
    assert new_row.credentials_secret != "xoxb-bot-token-fresh"
    assert vault.decrypt(new_row.credentials_secret) == "xoxb-bot-token-fresh"


@pytest.mark.asyncio
async def test_callback_updates_existing_connector_on_reinstall() -> None:
    settings = _settings()
    vault = TokenVault(settings.connector_secret_key or "")
    org_id = uuid.uuid4()
    state = slack_install.encode_state(org_id, settings=settings)

    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing.credentials_secret = vault.encrypt("xoxb-bot-token-OLD")
    existing.external_team_id = "T-OLD"
    existing.status = "active"

    session = AsyncMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = existing
    session.execute.return_value = select_result

    client = _client_with_oauth_response(
        {
            "ok": True,
            "access_token": "xoxb-bot-token-NEW",
            "team": {"id": "T-NEW", "name": "Demo"},
        },
    )

    connector_id = await slack_install.exchange_and_persist(
        session=session,
        settings=settings,
        vault=vault,
        code="auth-code-2",
        state_token=state,
        installed_by_membership_id=None,
        slack_client=client,
    )

    assert connector_id == existing.id
    assert vault.decrypt(existing.credentials_secret) == "xoxb-bot-token-NEW"
    assert existing.external_team_id == "T-NEW"


@pytest.mark.asyncio
async def test_callback_with_bad_state_raises() -> None:
    settings = _settings()
    vault = TokenVault(settings.connector_secret_key or "")
    session = AsyncMock()

    client = _client_with_oauth_response({"ok": True, "access_token": "x", "team": {"id": "T"}})

    with pytest.raises(slack_install.InstallStateError):
        await slack_install.exchange_and_persist(
            session=session,
            settings=settings,
            vault=vault,
            code="auth-code",
            state_token="not-a-real-state-token",
            installed_by_membership_id=None,
            slack_client=client,
        )
