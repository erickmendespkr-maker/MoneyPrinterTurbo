"""No external calls: stub Siteverify and enforce fail-closed behavior."""
import json
import urllib.error
from urllib.parse import parse_qs

import pytest

from app.afiliados.turnstile import (
    SITEVERIFY_URL, TurnstileConfig, load_turnstile_config, verify_registration_token,
)

CONFIG = TurnstileConfig("sitekey_1234", "secret_for_test_only", "app.example.com")


class FakeResponse:
    status = 200
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, limit):
        assert limit == 8193
        return self.body


def test_valid_proof_checked_server_side(monkeypatch):
    calls = []
    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(json.dumps({
            "success": True,
            "hostname": "app.example.com",
            "action": "register",
        }).encode())
    monkeypatch.setattr("app.afiliados.turnstile.urllib.request.urlopen", fake_urlopen)
    assert verify_registration_token("safe_proof_123", CONFIG) is None
    assert calls[0][0].full_url == SITEVERIFY_URL
    assert calls[0][1] == 8
    sent = parse_qs(calls[0][0].data.decode("ascii"))
    assert sent == {"secret": [CONFIG.secret_key], "response": ["safe_proof_123"]}


@pytest.mark.parametrize("payload", [
    {"success": False, "hostname": "app.example.com", "action": "register"},
    {"success": True, "hostname": "evil.example.com", "action": "register"},
    {"success": True, "hostname": "app.example.com", "action": "login"},
    {"success": True, "hostname": "app.example.com"},
    {"success": 1, "hostname": "app.example.com", "action": "register"},
    [],
])
def test_rejects_invalid_proof_response(monkeypatch, payload):
    monkeypatch.setattr("app.afiliados.turnstile.urllib.request.urlopen",
                        lambda *_args, **_kwargs: FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(PermissionError):
        verify_registration_token("safe_proof_123", CONFIG)


@pytest.mark.parametrize("token", [None, "", " ", "x" * 2049, "line\nbreak", "\x00", 234])
def test_missing_or_malformed_token_rejected_without_network(monkeypatch, token):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Should not make network request")
    monkeypatch.setattr("app.afiliados.turnstile.urllib.request.urlopen", forbidden)
    with pytest.raises(PermissionError):
        verify_registration_token(token, CONFIG)


def test_network_error_and_oversize_json_fail_closed(monkeypatch):
    def failed(*_args, **_kwargs):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr("app.afiliados.turnstile.urllib.request.urlopen", failed)
    with pytest.raises(PermissionError):
        verify_registration_token("safe_proof_123", CONFIG)
    monkeypatch.setattr("app.afiliados.turnstile.urllib.request.urlopen",
                        lambda *_a, **_kw: FakeResponse(b" " * 8193))
    with pytest.raises(PermissionError):
        verify_registration_token("safe_proof_123", CONFIG)


def test_config_requires_complete_safe_values(monkeypatch):
    for key in ("AFILIADOS_TURNSTILE_SITE_KEY", "AFILIADOS_TURNSTILE_SECRET_KEY",
                "AFILIADOS_TURNSTILE_HOSTNAME"):
        monkeypatch.delenv(key, raising=False)
    assert load_turnstile_config(required=False) is None
    with pytest.raises(RuntimeError):
        load_turnstile_config(required=True)
    monkeypatch.setenv("AFILIADOS_TURNSTILE_SITE_KEY", "sitekey_1234")
    with pytest.raises(RuntimeError):
        load_turnstile_config()
    monkeypatch.setenv("AFILIADOS_TURNSTILE_SECRET_KEY", "secret_for_test_only")
    monkeypatch.setenv("AFILIADOS_TURNSTILE_HOSTNAME", "app.example.com")
    assert load_turnstile_config(required=True) == CONFIG
    monkeypatch.setenv("AFILIADOS_TURNSTILE_HOSTNAME", "http://evil.com")
    with pytest.raises(RuntimeError):
        load_turnstile_config()
