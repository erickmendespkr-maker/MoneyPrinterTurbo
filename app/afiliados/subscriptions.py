"""Server-side subscription entitlements for local test accounts.

Only a trusted administrator should call set_plan. Client session values,
imported project JSON, and request parameters must never grant paid plans.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.afiliados.plans import get_plan_policy, require_feature
from app.afiliados.storage import ProjectStore, _owner


class SubscriptionStore:
    def __init__(self, database_path: Path):
        self.path = Path(database_path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_subscriptions (
            owner_id TEXT PRIMARY KEY, plan TEXT NOT NULL
        )""")
        return db

    def get_plan(self, owner_id: str) -> str:
        owner_id = _owner(owner_id)
        with self._connect() as db:
            row = db.execute("SELECT plan FROM affiliate_subscriptions WHERE owner_id=?",
                             (owner_id,)).fetchone()
        plan = row[0] if row else "gratis"
        try:
            get_plan_policy(plan)
        except ValueError:
            return "gratis"
        return plan

    def set_plan(self, owner_id: str, plan: str, *, trusted_admin: bool = False) -> None:
        """Test-only administrative mutation; never expose to user-facing routes."""
        if trusted_admin is not True:
            raise PermissionError("Alteração de plano exige administrador confiável")
        owner_id = _owner(owner_id)
        get_plan_policy(plan)
        with self._connect() as db:
            db.execute("""INSERT INTO affiliate_subscriptions(owner_id,plan) VALUES (?,?)
                ON CONFLICT(owner_id) DO UPDATE SET plan=excluded.plan""", (owner_id, plan))


class AuthorizedProjects:
    """Apply server-resolved subscription permissions to every project operation."""

    def __init__(self, projects: ProjectStore, subscriptions: SubscriptionStore):
        self.projects = projects
        self.subscriptions = subscriptions

    def _check(self, owner_id: str) -> None:
        require_feature(self.subscriptions.get_plan(owner_id), "projects")

    def save(self, owner_id: str, draft: dict, project_id: str | None = None) -> str:
        self._check(owner_id)
        return self.projects.save(owner_id, draft, project_id)

    def list(self, owner_id: str) -> list[dict]:
        self._check(owner_id)
        return self.projects.list(owner_id)

    def load(self, owner_id: str, project_id: str) -> dict:
        self._check(owner_id)
        return self.projects.load(owner_id, project_id)

    def delete(self, owner_id: str, project_id: str) -> bool:
        self._check(owner_id)
        return self.projects.delete(owner_id, project_id)
