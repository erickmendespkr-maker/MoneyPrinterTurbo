import pytest

from app.afiliados.auth import LocalAuth


def test_register_login_resolve_logout(tmp_path):
    path = tmp_path / "auth.sqlite"
    auth = LocalAuth(path)
    owner = auth.register("Test@Example.com", "correct horse battery 123")
    token = auth.login("test@example.com", "correct horse battery 123")
    assert token != owner
    assert LocalAuth(path).resolve(token) == owner
    auth.logout(token)
    assert auth.resolve(token) is None


def test_invalid_login_does_not_return_session(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    auth.register("user@example.com", "a long secure password")
    with pytest.raises(ValueError, match="Credenciais"):
        auth.login("user@example.com", "wrong password 123")
    with pytest.raises(ValueError, match="Credenciais"):
        auth.login("missing@example.com", "wrong password 123")
    assert auth.resolve("not-a-session") is None


def test_duplicate_email_is_rejected(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    auth.register("user@example.com", "a long secure password")
    with pytest.raises(ValueError):
        auth.register("USER@example.com", "another secure password")


@pytest.mark.parametrize("email,password", [
    ("not-an-email", "a long secure password"),
    ("user@example.com", "short"),
    ("user@example.com", "x" * 129),
])
def test_invalid_credentials_rejected(tmp_path, email, password):
    with pytest.raises(ValueError):
        LocalAuth(tmp_path / "auth.sqlite").register(email, password)
