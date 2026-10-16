"""End-to-end local authentication + project ownership regression tests."""
import pytest

from app.afiliados.auth import LocalAuth
from app.afiliados.core import AffiliateBrief, prepare_draft
from app.afiliados.storage import ProjectStore


def _draft(name):
    return prepare_draft(AffiliateBrief(
        name, "https://shopee.com.br/produto/123",
        "Caracteristicas verificadas", 15, "comentario", "feminina", "",
    ))


def test_login_save_resume_update_and_logout(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    projects = ProjectStore(tmp_path / "projects.sqlite")
    auth.register("creator@example.com", "strong password for tests")
    token = auth.login("creator@example.com", "strong password for tests")
    owner = auth.resolve(token)
    assert owner
    project_id = projects.save(owner, _draft("Primeiro produto"))
    assert projects.list(owner)[0]["id"] == project_id
    assert projects.load(owner, project_id)["product"]["product_name"] == "Primeiro produto"
    projects.save(owner, _draft("Produto revisado"), project_id)
    assert projects.load(owner, project_id)["product"]["product_name"] == "Produto revisado"
    auth.logout(token)
    assert auth.resolve(token) is None


def test_second_authenticated_account_cannot_open_first_account_projects(tmp_path):
    auth = LocalAuth(tmp_path / "auth.sqlite")
    projects = ProjectStore(tmp_path / "projects.sqlite")
    auth.register("one@example.com", "strong password for tests")
    auth.register("two@example.com", "another strong password")
    first = auth.resolve(auth.login("one@example.com", "strong password for tests"))
    second = auth.resolve(auth.login("two@example.com", "another strong password"))
    project_id = projects.save(first, _draft("Private"))
    assert projects.list(second) == []
    with pytest.raises(ValueError):
        projects.load(second, project_id)
    with pytest.raises(ValueError):
        projects.save(second, _draft("Attack"), project_id)
    assert projects.delete(second, project_id) is False
    assert projects.load(first, project_id)["product"]["product_name"] == "Private"


def test_expired_session_cannot_resolve(tmp_path, monkeypatch):
    import app.afiliados.auth as auth_module
    clock = [1_800_000_000]
    monkeypatch.setattr(auth_module.time, "time", lambda: clock[0])
    auth = LocalAuth(tmp_path / "auth.sqlite")
    auth.register("expire@example.com", "strong password for tests")
    token = auth.login("expire@example.com", "strong password for tests")
    assert auth.resolve(token)
    clock[0] += auth_module.SESSION_SECONDS + 1
    assert auth.resolve(token) is None
