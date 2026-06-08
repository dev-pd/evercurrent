"""Fernet wrapper for connector token storage.

The Slack bot token sits in `connectors.credentials_secret` as a
Fernet-encrypted blob. The key comes from
`settings.connector_secret_key` — a base64-encoded 32-byte secret. In
production the key moves to KMS; this vault interface stays the same.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class TokenVaultError(ValueError):
    """Raised when decryption fails: wrong key, corrupted ciphertext, etc."""


class TokenVault:
    """Encrypt/decrypt connector secrets with a single Fernet key.

    A new instance per request is cheap (Fernet stores only the key
    schedule); we keep one per app via dependency injection.
    """

    def __init__(self, key: str | bytes) -> None:
        if isinstance(key, str):
            key = key.encode()
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise TokenVaultError("failed to decrypt connector token") from exc


def generate_key() -> str:
    """Generate a fresh Fernet key. Used by ops scripts, not request path."""
    return Fernet.generate_key().decode()
