"""
Unit tests for bot/crypto.py — no server, no DB, no API key needed.
Requires FORGE_ENCRYPTION_KEY to be set (uses the value from .env via config).
"""
import pytest
from cryptography.fernet import Fernet
from unittest.mock import patch
from bot.crypto import encrypt_token, decrypt_token


@pytest.fixture
def valid_key():
    return Fernet.generate_key().decode()


def test_roundtrip(valid_key):
    with patch("bot.crypto._fernet", return_value=Fernet(valid_key.encode())):
        encrypted = encrypt_token("my-secret-token")
        assert decrypt_token(encrypted) == "my-secret-token"


def test_encrypted_value_differs_from_plaintext(valid_key):
    with patch("bot.crypto._fernet", return_value=Fernet(valid_key.encode())):
        encrypted = encrypt_token("my-secret-token")
        assert encrypted != "my-secret-token"


def test_two_encryptions_differ(valid_key):
    """Fernet uses random IV — same plaintext yields different ciphertext each time."""
    fernet = Fernet(valid_key.encode())
    with patch("bot.crypto._fernet", return_value=fernet):
        a = encrypt_token("token")
        b = encrypt_token("token")
        assert a != b


def test_wrong_key_raises(valid_key):
    other_key = Fernet.generate_key().decode()
    with patch("bot.crypto._fernet", return_value=Fernet(valid_key.encode())):
        encrypted = encrypt_token("token")
    with patch("bot.crypto._fernet", return_value=Fernet(other_key.encode())):
        with pytest.raises(Exception):
            decrypt_token(encrypted)


def test_empty_string_roundtrip(valid_key):
    with patch("bot.crypto._fernet", return_value=Fernet(valid_key.encode())):
        assert decrypt_token(encrypt_token("")) == ""
