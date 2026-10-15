import pytest

from app.afiliados.auth import LocalAuth


def test_failed_login_attempts_are_persisted(tmp_path):
    path = tmp_path / "auth.sqlite"
    auth = LocalAuth(path)
    auth.register("user@example.com", "a secure long password")
    for _ in range(8):
        with pytest.raises(ValueError, match="Credenciais"):
            auth.login("user@example.com", "incorrect password 123")
    with pytest.raises(ValueError, match="Muitas tentativas"):
        LocalAuth(path).login("user@example.com", "a secure long password")


def test_reset_request_limit_for_existing_and_unknown_accounts(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    auth.register("user@example.com", "a secure long password")
    for _ in range(3):
        assert auth.create_reset_token("user@example.com")
        assert auth.create_reset_token("unknown@example.com") is None
    for email in ("user@example.com", "unknown@example.com"):
        with pytest.raises(ValueError, match="Muitas tentativas"):
            auth.create_reset_token(email)
