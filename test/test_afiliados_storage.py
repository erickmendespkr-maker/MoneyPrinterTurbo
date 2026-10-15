import json

import pytest

from app.afiliados.core import AffiliateBrief, prepare_draft
from app.afiliados.storage import ProjectStore


ALICE = "alice-user-0001"
BOB = "other-user-0002"


def draft():
    return prepare_draft(AffiliateBrief(
        "Aspirador portátil", "https://shopee.com.br/produto/123",
        "Cor preta e cabo USB", 15, "comentario", "feminina", "",
    ))


def test_project_persists_across_store_instances(tmp_path):
    path = tmp_path / "projects.sqlite"
    project_id = ProjectStore(path).save(ALICE, draft())
    assert ProjectStore(path).load(ALICE, project_id)["product"]["product_name"] == "Aspirador portátil"
    assert len(ProjectStore(path).list(ALICE)) == 1


def test_projects_are_isolated_by_owner(tmp_path):
    store = ProjectStore(tmp_path / "projects.sqlite")
    project_id = store.save(ALICE, draft())
    assert store.list(BOB) == []
    with pytest.raises(ValueError):
        store.load(BOB, project_id)
    with pytest.raises(ValueError):
        store.save(BOB, draft(), project_id)
    assert not store.delete(BOB, project_id)
    assert store.load(ALICE, project_id)


def test_project_update_and_delete(tmp_path):
    store = ProjectStore(tmp_path / "projects.sqlite")
    project_id = store.save(ALICE, draft())
    updated = draft()
    updated["script"] = "Roteiro revisado."
    assert store.save(ALICE, updated, project_id) == project_id
    assert store.load(ALICE, project_id)["script"] == "Roteiro revisado."
    assert store.delete(ALICE, project_id)
    with pytest.raises(ValueError):
        store.load(ALICE, project_id)


def test_imported_provider_settings_are_not_trusted(tmp_path):
    store = ProjectStore(tmp_path / "projects.sqlite")
    changed = draft()
    changed["generation"]["openai_enabled"] = True
    project_id = store.save(ALICE, changed)
    assert store.load(ALICE, project_id)["generation"]["openai_enabled"] is False


@pytest.mark.parametrize("owner", ["", "../owner", "short", "name@example.com", None])
def test_invalid_owners_rejected(tmp_path, owner):
    with pytest.raises(ValueError):
        ProjectStore(tmp_path / "projects.sqlite").list(owner)
