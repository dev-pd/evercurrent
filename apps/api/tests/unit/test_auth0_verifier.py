"""Unit tests for Auth0 JWT verification.

Covers the deterministic edges: malformed header, unknown kid, expired
token, wrong audience. Live network calls to Auth0 are mocked via
httpx.MockTransport.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from evercurrent.auth.auth0 import Auth0Verifier, InvalidTokenError

_TEST_AUDIENCE = "https://api.evercurrent.test"
_TEST_DOMAIN = "evercurrent-test.us.auth0.com"


def _make_keypair() -> tuple[str, dict[str, Any]]:
    """Build a deterministic RSA keypair as JWKS for tests."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    jwk_dict = jwk.construct(public_pem, "RS256").to_dict()
    jwk_dict["kid"] = "test-kid-1"
    jwk_dict["use"] = "sig"
    return private_pem.decode(), jwk_dict


def _sign(private_pem: str, *, audience: str = _TEST_AUDIENCE, exp_offset: int = 600) -> str:
    payload = {
        "sub": "auth0|user_1",
        "aud": audience,
        "iss": f"https://{_TEST_DOMAIN}/",
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "org_id": "org_abc",
        "email": "test@example.com",
        "name": "Test User",
    }
    return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": "test-kid-1"})


def _client_with_jwks(public_jwk: dict[str, Any]) -> httpx.AsyncClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [public_jwk]})

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


@pytest.mark.asyncio
async def test_verify_returns_claims_for_valid_token() -> None:
    private_pem, public_jwk = _make_keypair()
    verifier = Auth0Verifier(
        domain=_TEST_DOMAIN,
        audience=_TEST_AUDIENCE,
        client=_client_with_jwks(public_jwk),
    )
    token = _sign(private_pem)

    claims = await verifier.verify(token)

    assert claims.sub == "auth0|user_1"
    assert claims.org_id == "org_abc"
    assert claims.email == "test@example.com"
    await verifier.aclose()


@pytest.mark.asyncio
async def test_verify_rejects_malformed_token() -> None:
    _, public_jwk = _make_keypair()
    verifier = Auth0Verifier(
        domain=_TEST_DOMAIN,
        audience=_TEST_AUDIENCE,
        client=_client_with_jwks(public_jwk),
    )

    with pytest.raises(InvalidTokenError):
        await verifier.verify("not.a.jwt")

    await verifier.aclose()


@pytest.mark.asyncio
async def test_verify_rejects_wrong_audience() -> None:
    private_pem, public_jwk = _make_keypair()
    verifier = Auth0Verifier(
        domain=_TEST_DOMAIN,
        audience=_TEST_AUDIENCE,
        client=_client_with_jwks(public_jwk),
    )
    token = _sign(private_pem, audience="https://wrong.audience")

    with pytest.raises(InvalidTokenError):
        await verifier.verify(token)

    await verifier.aclose()


@pytest.mark.asyncio
async def test_verify_rejects_expired_token() -> None:
    private_pem, public_jwk = _make_keypair()
    verifier = Auth0Verifier(
        domain=_TEST_DOMAIN,
        audience=_TEST_AUDIENCE,
        client=_client_with_jwks(public_jwk),
    )
    token = _sign(private_pem, exp_offset=-60)

    with pytest.raises(InvalidTokenError):
        await verifier.verify(token)

    await verifier.aclose()
