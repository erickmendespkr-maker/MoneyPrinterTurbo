"""Verify production auth does not trust browser claims or access tokens."""
import json
import urllib.error
from uuid import uuid4

import pytest

from app.afiliados.production_auth import (
    SupabaseAuth, AuthDenied, AuthServiceUnavailable,
)

PROJECT = "https://example-ref.supabase.co"
KEY = "sb_publishable_example_public_key_1234"
USER_ID = str(uuid4())


class FakeResponse:
    def __init__(self, result, status=200):
        self.data = json.dumps(result).encode() if not isinstance(result, bytes) else result
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self, amount):
        return self.data[:amount]


class StubOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        assert timeout == 10
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


def make_auth(*responses):
    auth = SupabaseAuth(PROJECT, KEY)
    auth._opener = StubOpener(responses)
    return auth


def confirmed_user():
    return {"id": USER_ID, "email": "verified@example.com",
            "email_confirmed_at": "2026-10-15T16:00:00Z",
            "user_metadata": {"plan": "creator", "admin": True}}


def test_confirmed_identity_comes_from_server_not_metadata():
    auth = make_auth(confirmed_user())
    who = auth.require_verified_user("token_" + "x" * 30)
    assert who.owner_id == USER_ID
    assert who.email_verified and who.email == "verified@example.com"
    request = auth._opener.requests[0]
    assert request.full_url == PROJECT + "/auth/v1/user"
    assert request.get_header("Authorization").startswith("Bearer token_")
    assert request.get_header("Apikey") == KEY


@pytest.mark.parametrize("user", [
    {"id": USER_ID, "email": "user@example.com"},
    {"id": USER_ID, "email": "user@example.com", "email_confirmed_at": None},
    {"id": "fake-owner", "email": "user@example.com", "email_confirmed_at": "2026"},
    {"id": USER_ID, "email": None, "email_confirmed_at": "2026"},
    [],
])
def test_unverified_or_invalid_user_rejected(user):
    with pytest.raises(AuthDenied):
        make_auth(user).require_verified_user("token_" + "x" * 30)


def test_password_login_requires_confirmed_server_user():
    auth = make_auth(
        {"access_token": "user_" + "a" * 40, "refresh_token": "refresh_" + "b" * 40,
         "expires_in": 3600,
         "user": {"id": USER_ID, "email_confirmed_at": "fake"}},
        confirmed_user(),
    )
    session = auth.login("Verify@Example.com", "a secure 12345 password")
    assert session["expires_in"] == 3600
    req = auth._opener.requests[0]
    assert req.full_url.endswith("/token?grant_type=password")
    assert json.loads(req.data) == {
        "email": "verify@example.com", "password": "a secure 12345 password",
    }
    assert auth._opener.requests[1].full_url.endswith("/user")


def test_login_refuses_unverified_user_despite_session():
    auth = make_auth(
        {"access_token": "user_" + "a" * 40, "refresh_token": "refresh_" + "b" * 40,
         "expires_in": 3600},
        {"id": USER_ID, "email": "test@example.com", "email_confirmed_at": None},
    )
    with pytest.raises(AuthDenied, match="Confirme"):
        auth.login("test@example.com", "a secure 12345 password")


def test_refresh_token_rotated_and_verified():
    auth = make_auth(
        {"access_token": "user_" + "a" * 40, "refresh_token": "new_" + "b" * 40,
         "expires_in": 3600},
        confirmed_user(),
    )
    result = auth.refresh("old_" + "x" * 40)
    assert result["refresh_token"].startswith("new_")
    assert json.loads(auth._opener.requests[0].data)["refresh_token"].startswith("old_")


def test_registration_rejects_provider_without_email_confirmation(monkeypatch):
    from app.afiliados.turnstile import TurnstileConfig
    monkeypatch.setattr("app.afiliados.turnstile.load_turnstile_config",
                        lambda required: TurnstileConfig("public", "secret", "app.example.com"))
    checked = []
    monkeypatch.setattr("app.afiliados.turnstile.verify_registration_token",
                        lambda token, config: checked.append(token))
    auth = make_auth({"id": USER_ID, "email": "new@example.com"})
    auth.register("new@example.com", "a secure 12345 password", captcha_token="validated")
    assert checked == ["validated"]
    auth2 = make_auth({"access_token": "a" * 80, "refresh_token": "b" * 80})
    with pytest.raises(AuthServiceUnavailable, match="Confirmação"):
        auth2.register("new@example.com", "a secure 12345 password", captcha_token="validated")


def test_public_registration_fails_without_config_or_proof(monkeypatch):
    auth = make_auth({"id": USER_ID})
    monkeypatch.delenv("AFILIADOS_TURNSTILE_SITE_KEY", raising=False)
    monkeypatch.delenv("AFILIADOS_TURNSTILE_SECRET_KEY", raising=False)
    monkeypatch.delenv("AFILIADOS_TURNSTILE_HOSTNAME", raising=False)
    with pytest.raises(RuntimeError):
        auth.register("new@example.com", "a secure 12345 password", captcha_token="something")
    assert not auth._opener.requests



def test_auth_denied_and_network_error_are_fail_closed():
    auth = make_auth(urllib.error.HTTPError(PROJECT + "/auth/v1/user", 401,
                                           "unauthorized", {}, None))
    with pytest.raises(AuthDenied):
        auth.require_verified_user("token_" + "x" * 30)
    auth = make_auth(urllib.error.URLError("offline"))
    with pytest.raises(AuthServiceUnavailable):
        auth.require_verified_user("token_" + "x" * 30)


@pytest.mark.parametrize("url,key", [
    ("http://example-ref.supabase.co", KEY),
    ("https://example-ref.supabase.co.evil.net", KEY),
    ("https://example-ref.supabase.co/path", KEY),
    ("https://localhost:54321", KEY),
    (PROJECT, "sb_secret_NEVER"),
    (PROJECT, ""),
])
def test_unsafe_provider_config_rejected(url, key):
    with pytest.raises(ValueError):
        SupabaseAuth(url, key)


def test_redirect_following_is_disabled_for_auth_tokens():
    auth = SupabaseAuth(PROJECT, KEY)
    assert any(handler.__class__.__name__ == "_NoRedirects"
               for handler in auth._opener.handlers)
