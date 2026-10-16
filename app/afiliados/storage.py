"""Local SQLite project storage with explicit, trusted owner scoping.

IMPORTANT: owner_id must come from verified server-side authentication, never
from a text field, query parameter or an imported project. Do not expose this
storage to public users before authentication and authorization are wired.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.afiliados.projects import import_project, MAX_PROJECT_BYTES

OWNER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,128}$")


def _owner(owner_id: str) -> str:
    if not isinstance(owner_id, str) or not OWNER_PATTERN.fullmatch(owner_id):
        raise ValueError("Identificador de proprietário inválido")
    return owner_id


class ProjectStore:
    def __init__(self, database_path: Path):
        self.path = Path(database_path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS affiliate_projects (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                title TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_owner ON affiliate_projects(owner_id, updated_at)")
        return conn

    def save(self, owner_id: str, draft: dict, project_id: str | None = None) -> str:
        owner_id = _owner(owner_id)
        if not isinstance(draft, dict):
            raise ValueError("Projeto inválido")
        payload = json.dumps(draft, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(payload) > MAX_PROJECT_BYTES:
            raise ValueError("Projeto acima de 16 KB")
        safe = import_project(payload)
        stored = json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
        title = safe["product"]["product_name"]
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            if project_id is None:
                project_id = uuid4().hex
                conn.execute(
                    "INSERT INTO affiliate_projects VALUES (?,?,?,?,?,?)",
                    (project_id, owner_id, title, stored, now, now),
                )
            else:
                if not isinstance(project_id, str) or not re.fullmatch(r"[0-9a-f]{32}", project_id):
                    raise ValueError("ID de projeto inválido")
                cur = conn.execute(
                    "UPDATE affiliate_projects SET title=?, payload=?, updated_at=? WHERE id=? AND owner_id=?",
                    (title, stored, now, project_id, owner_id),
                )
                if cur.rowcount != 1:
                    raise ValueError("Projeto não encontrado")
        return project_id

    def list(self, owner_id: str) -> list[dict]:
        owner_id = _owner(owner_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id,title,created_at,updated_at FROM affiliate_projects WHERE owner_id=? ORDER BY updated_at DESC LIMIT 100",
                (owner_id,),
            ).fetchall()
        return [dict(zip(("id", "title", "created_at", "updated_at"), row)) for row in rows]

    def load(self, owner_id: str, project_id: str) -> dict:
        owner_id = _owner(owner_id)
        if not isinstance(project_id, str) or not re.fullmatch(r"[0-9a-f]{32}", project_id):
            raise ValueError("ID de projeto inválido")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM affiliate_projects WHERE id=? AND owner_id=?",
                (project_id, owner_id),
            ).fetchone()
        if row is None:
            raise ValueError("Projeto não encontrado")
        return import_project(row[0].encode("utf-8"))

    def delete(self, owner_id: str, project_id: str) -> bool:
        owner_id = _owner(owner_id)
        if not isinstance(project_id, str) or not re.fullmatch(r"[0-9a-f]{32}", project_id):
            raise ValueError("ID de projeto inválido")
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM affiliate_projects WHERE id=? AND owner_id=?",
                (project_id, owner_id),
            )
        return cur.rowcount == 1
