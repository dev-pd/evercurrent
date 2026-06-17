"""Auth0 JWT verification: fetches + caches the JWKS and validates bearer-token
claims (audience, issuer, signature), returning typed Auth0Claims."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from jose import jwt
from jose.exceptions import JWTError
from pydantic import BaseModel, ConfigDict

log = structlog.get_logger(__name__)

_JWKS_TTL_SECONDS = 3600
_REQUEST_TIMEOUT_SECONDS = 5


_CLAIM_NS = "https://evercurrent/"
ROLES_CLAIM = f"{_CLAIM_NS}roles"
EMAIL_CLAIM = f"{_CLAIM_NS}email"
NAME_CLAIM = f"{_CLAIM_NS}name"
ORG_NAME_CLAIM = f"{_CLAIM_NS}org_name"


class Auth0Claims(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    sub: str
    aud: str | list[str]
    iss: str
    exp: int
    iat: int
    azp: str | None = None
    org_id: str | None = None
    org_name: str | None = None
    email: str | None = None
    name: str | None = None
    roles: list[str] = []


@dataclass
class _JwksCache:
    keys: list[dict[str, Any]]
    fetched_at: float


class Auth0Verifier:
    def __init__(
        self,
        *,
        domain: str,
        audience: str,
        algorithms: tuple[str, ...] = ("RS256",),
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._domain = domain.rstrip("/")
        self._audience = audience
        self._algorithms = list(algorithms)
        self._issuer = f"https://{self._domain}/"
        self._jwks_url = f"https://{self._domain}/.well-known/jwks.json"
        self._client = client or httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS)
        self._cache: _JwksCache | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def verify(self, token: str) -> Auth0Claims:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise InvalidTokenError("malformed token header") from exc

        key = await self._find_key(unverified_header.get("kid"))
        if key is None:
            await self._refresh_jwks()
            key = await self._find_key(unverified_header.get("kid"))
        if key is None:
            raise InvalidTokenError("no matching JWKS key for kid")

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
            )
        except JWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        raw_roles = payload.get(ROLES_CLAIM) or payload.get("roles") or []
        payload["roles"] = [str(r) for r in raw_roles] if isinstance(raw_roles, list) else []
        if payload.get(EMAIL_CLAIM):
            payload["email"] = payload[EMAIL_CLAIM]
        if payload.get(NAME_CLAIM):
            payload["name"] = payload[NAME_CLAIM]
        if payload.get(ORG_NAME_CLAIM):
            payload["org_name"] = payload[ORG_NAME_CLAIM]
        return Auth0Claims.model_validate(payload)

    async def _find_key(self, kid: str | None) -> dict[str, Any] | None:
        if kid is None:
            return None
        if self._cache is None or self._is_stale():
            await self._refresh_jwks()
        if self._cache is None:
            return None
        for k in self._cache.keys:
            if k.get("kid") == kid:
                return k
        return None

    def _is_stale(self) -> bool:
        if self._cache is None:
            return True
        return (time.time() - self._cache.fetched_at) > _JWKS_TTL_SECONDS

    async def _refresh_jwks(self) -> None:
        try:
            response = await self._client.get(self._jwks_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("auth0.jwks.fetch_failed", error=str(exc))
            return
        body = response.json()
        keys = body.get("keys", []) if isinstance(body, dict) else []
        self._cache = _JwksCache(keys=keys, fetched_at=time.time())


class InvalidTokenError(Exception):
    pass
