"""TokenVault: symmetric encryption for stored connector tokens so provider secrets aren't persisted in plaintext."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class TokenVaultError(ValueError):
    pass


class TokenVault:
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
    return Fernet.generate_key().decode()
