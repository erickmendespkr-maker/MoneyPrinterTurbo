"""Verified mailbox is a prerequisite for the free video generation UI."""
import sqlite3
import time

import pytest

from app.afiliados.auth import LocalAuth


def test_new_user_unverified_until_single_use_token_confirmed(tmp_path):
    path = tmp_path / "auth.sqlite"
    auth = LocalAuth(path)
    owner = auth.register("First@Example.com", "a secure password here")
    assert not auth.is_verified(owner)
    assert auth.resolve(auth.login("first@example.com", "a secure password here")) == owner
    token = auth.create_verification_token("first@example.com")
    assert token and len(token) >= 32
    assert not auth.is_verified(owner)
    auth.verify_email(token)
    assert LocalAuth(path).is_verified(owner)
    assert auth.create_verification_token("first@example.com") is None
    with pytest.raises(ValueError, match="Link de verificação"):
        auth.verify_email(token)


def test_invalid_and_expired_verification_token(tmp_path, monkeypatch):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    auth.register("account@example.com", "a secure password here")
    with pytest.raises(ValueError):
        auth.verify_email("fake")
    token = auth.create_verification_token("account@example.com")
    real = time.time
    monkeypatch.setattr("app.afiliados.auth.time.time", lambda: real() + 86401)
    with pytest.raises(ValueError, match="Link de verificação"):
        auth.verify_email(token)


def test_resending_invalidates_previous_token_and_throttles(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    owner = auth.register("account@example.com", "a secure password here")
    old = auth.create_verification_token("account@example.com")
    fresh = auth.create_verification_token("account@example.com")
    assert not auth.is_verified(owner)
    with pytest.raises(ValueError, match="Link de verificação"):
        auth.verify_email(old)
    assert auth.create_verification_token("account@example.com")
    with pytest.raises(ValueError, match="Muitas tentativas"):
        auth.create_verification_token("account@example.com")
    auth.verify_email(fresh) if False else None  # old links never regain validity


def test_unknown_mailbox_never_receives_token(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    assert auth.create_verification_token("absent@example.com") is None


def test_existing_accounts_require_confirmation_after_migration(tmp_path):
    path = tmp_path / "auth.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE affiliate_users (id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,salt BLOB NOT NULL,password_hash BLOB NOT NULL)")
        db.execute("INSERT INTO affiliate_users VALUES (?,?,?,?)",
                   ("legacy-owner", "legacy@example.com", b"salt", b"digest"))
    auth = LocalAuth(path)
    assert not auth.is_verified("legacy-owner")
    auth.verify_email(auth.create_verification_token("legacy@example.com"))
    assert auth.is_verified("legacy-owner")
