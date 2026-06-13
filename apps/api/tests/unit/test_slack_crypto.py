from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from evercurrent.connectors.slack.crypto import TokenVault, TokenVaultError, generate_key


def test_round_trip_preserves_plaintext() -> None:
    key = generate_key()
    vault = TokenVault(key)

    ciphertext = vault.encrypt("xoxb-abc-123")
    assert ciphertext != "xoxb-abc-123"
    assert vault.decrypt(ciphertext) == "xoxb-abc-123"


def test_different_keys_produce_different_ciphertext() -> None:
    a = TokenVault(generate_key())
    b = TokenVault(generate_key())

    assert a.encrypt("same-token") != b.encrypt("same-token")


def test_wrong_key_raises_token_vault_error() -> None:
    good = TokenVault(generate_key())
    bad = TokenVault(Fernet.generate_key().decode())

    ciphertext = good.encrypt("xoxb-abc-123")

    with pytest.raises(TokenVaultError):
        bad.decrypt(ciphertext)


def test_bytes_key_accepted() -> None:
    raw_key = Fernet.generate_key()
    vault = TokenVault(raw_key)
    assert vault.decrypt(vault.encrypt("hello")) == "hello"
