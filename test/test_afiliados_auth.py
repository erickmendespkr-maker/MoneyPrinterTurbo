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


def test_password_reset_revokes_sessions_and_is_single_use(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    auth.register("user@example.com", "original secure password")
    session = auth.login("user@example.com", "original secure password")
    token = auth.create_reset_token("user@example.com")
    assert token and len(token) > 32
    auth.reset_password(token, "new secure password 123")
    assert auth.resolve(session) is None
    with pytest.raises(ValueError):
        auth.reset_password(token, "another secure password")
    with pytest.raises(ValueError):
        auth.login("user@example.com", "original secure password")
    assert auth.login("user@example.com", "new secure password 123")


def test_unknown_email_does_not_issue_reset_token(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    assert auth.create_reset_token("unknown@example.com") is None


def test_new_reset_request_invalidates_old_token(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    auth.register("user@example.com", "original secure password")
    first = auth.create_reset_token("user@example.com")
    second = auth.create_reset_token("user@example.com")
    with pytest.raises(ValueError):
        auth.reset_password(first, "new secure password 123")
    auth.reset_password(second, "new secure password 123")
