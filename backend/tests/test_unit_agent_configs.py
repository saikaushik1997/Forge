"""
Unit tests for channel_configs helpers in api/agents.py — no server, no DB.
"""
import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet
from api.agents import _mask_configs, _encrypt_configs, _maybe_encrypt


# ── _mask_configs ──────────────────────────────────────────────────────────────

def test_mask_replaces_token_with_has_token_true():
    configs = {"telegram": {"enabled": True, "bot_token": "secret"}}
    result = _mask_configs(configs)
    assert "bot_token" not in result["telegram"]
    assert result["telegram"]["has_token"] is True


def test_mask_has_token_false_when_no_token():
    configs = {"telegram": {"enabled": False}}
    result = _mask_configs(configs)
    assert result["telegram"]["has_token"] is False


def test_mask_preserves_other_fields():
    configs = {"telegram": {"enabled": True, "bot_token": "secret", "extra": "value"}}
    result = _mask_configs(configs)
    assert result["telegram"]["enabled"] is True
    assert result["telegram"]["extra"] == "value"


def test_mask_empty_configs():
    assert _mask_configs({}) == {}


def test_mask_multiple_channels():
    configs = {
        "telegram": {"enabled": True, "bot_token": "tok1"},
        "slack": {"enabled": False},
    }
    result = _mask_configs(configs)
    assert result["telegram"]["has_token"] is True
    assert result["slack"]["has_token"] is False


# ── _maybe_encrypt ─────────────────────────────────────────────────────────────

def test_maybe_encrypt_returns_none_for_empty():
    assert _maybe_encrypt(None) is None
    assert _maybe_encrypt("") is None


def test_maybe_encrypt_returns_plaintext_when_no_key():
    with patch("api.agents.settings") as mock_settings:
        mock_settings.forge_encryption_key = None
        result = _maybe_encrypt("my-token")
    assert result == "my-token"


# ── _encrypt_configs ───────────────────────────────────────────────────────────

def test_encrypt_configs_encrypts_bot_token():
    key = Fernet.generate_key().decode()
    with patch("api.agents.settings") as mock_settings, \
         patch("api.agents.encrypt_token", side_effect=lambda t: f"enc:{t}"):
        mock_settings.forge_encryption_key = key
        configs = {"telegram": {"enabled": True, "bot_token": "raw-token"}}
        result = _encrypt_configs(configs)
    assert result["telegram"]["bot_token"] == "enc:raw-token"


def test_encrypt_configs_skips_missing_token():
    configs = {"telegram": {"enabled": True}}
    result = _encrypt_configs(configs)
    assert "bot_token" not in result["telegram"]


def test_encrypt_configs_empty():
    assert _encrypt_configs({}) == {}


def test_encrypt_configs_preserves_other_fields():
    with patch("api.agents.encrypt_token", side_effect=lambda t: f"enc:{t}"):
        with patch("api.agents.settings") as mock_settings:
            mock_settings.forge_encryption_key = "key"
            configs = {"telegram": {"enabled": True, "bot_token": "tok", "chat_id": "123"}}
            result = _encrypt_configs(configs)
    assert result["telegram"]["chat_id"] == "123"
    assert result["telegram"]["enabled"] is True
