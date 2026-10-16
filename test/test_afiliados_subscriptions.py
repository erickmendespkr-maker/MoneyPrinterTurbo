import pytest

from app.afiliados.core import AffiliateBrief, prepare_draft
from app.afiliados.storage import ProjectStore
from app.afiliados.subscriptions import AuthorizedProjects, SubscriptionStore

OWNER = "owner-test-12345"


def draft():
    return prepare_draft(AffiliateBrief(
        "Produto real", "https://shopee.com.br/produto/123",
        "Característica verificada", 15, "comentario", "feminina", "",
    ))


def test_free_plan_is_default_and_cannot_access_project_storage(tmp_path):
    subs = SubscriptionStore(tmp_path / "subscriptions.sqlite")
    projects = AuthorizedProjects(ProjectStore(tmp_path / "projects.sqlite"), subs)
    assert subs.get_plan(OWNER) == "gratis"
    for operation in (
        lambda: projects.save(OWNER, draft()),
        lambda: projects.list(OWNER),
        lambda: projects.load(OWNER, "a" * 32),
        lambda: projects.delete(OWNER, "a" * 32),
    ):
        with pytest.raises(PermissionError):
            operation()


@pytest.mark.parametrize("plan", ["pro", "creator"])
def test_paid_plans_can_save_and_reopen_projects(tmp_path, plan):
    subs = SubscriptionStore(tmp_path / "subscriptions.sqlite")
    subs.set_plan(OWNER, plan, trusted_admin=True)
    projects = AuthorizedProjects(ProjectStore(tmp_path / "projects.sqlite"), subs)
    pid = projects.save(OWNER, draft())
    assert projects.list(OWNER)[0]["id"] == pid
    assert projects.load(OWNER, pid)["product"]["product_name"] == "Produto real"
    assert projects.delete(OWNER, pid)


def test_downgrade_immediately_revokes_access(tmp_path):
    subs = SubscriptionStore(tmp_path / "subscriptions.sqlite")
    projects = AuthorizedProjects(ProjectStore(tmp_path / "projects.sqlite"), subs)
    subs.set_plan(OWNER, "pro", trusted_admin=True)
    pid = projects.save(OWNER, draft())
    subs.set_plan(OWNER, "gratis", trusted_admin=True)
    with pytest.raises(PermissionError):
        projects.load(OWNER, pid)
    with pytest.raises(PermissionError):
        projects.list(OWNER)
    subs.set_plan(OWNER, "pro", trusted_admin=True)
    assert projects.load(OWNER, pid)


def test_user_cannot_self_upgrade(tmp_path):
    subs = SubscriptionStore(tmp_path / "subscriptions.sqlite")
    with pytest.raises(PermissionError):
        subs.set_plan(OWNER, "creator")
    assert subs.get_plan(OWNER) == "gratis"
