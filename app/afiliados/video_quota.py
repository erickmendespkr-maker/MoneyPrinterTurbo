"""Transactional daily video quota ledger for authenticated local accounts.

Usage is counted only after successful rendering. Reservations prevent
concurrent renders from exceeding daily limits. All times use Sao Paulo.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.afiliados.plans import get_plan_policy
from app.afiliados.storage import _owner

TZ = ZoneInfo("America/Sao_Paulo")


def _day() -> str:
    return datetime.now(TZ).date().isoformat()


class VideoQuota:
    def __init__(self, database_path: Path):
        self.path = Path(database_path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_video_quota (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, day TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('reserved','completed')),
            created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_video_quota_owner_day ON affiliate_video_quota(owner_id,day,status)")
        return db

    def reserve(self, owner_id: str, plan: str, count: int = 1) -> list[str]:
        """Reserve capacity atomically before rendering. Caller must use a trusted plan."""
        owner_id = _owner(owner_id)
        policy = get_plan_policy(plan)
        if type(count) is not int or count < 1 or count > policy.videos_per_ad:
            raise ValueError("Quantidade de vídeos não permitida para o plano")
        day = _day()
        ids = [uuid4().hex for _ in range(count)]
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute(
                "SELECT COUNT(*) FROM affiliate_video_quota WHERE owner_id=? AND day=?",
                (owner_id, day),
            ).fetchone()[0]
            if policy.daily_video_limit is not None and used + count > policy.daily_video_limit:
                raise PermissionError("Limite diário de vídeos atingido")
            db.executemany(
                "INSERT INTO affiliate_video_quota VALUES (?,?,?,?,?)",
                [(i, owner_id, day, "reserved", datetime.now(TZ).isoformat()) for i in ids],
            )
        return ids

    def complete(self, owner_id: str, reservation_ids: list[str]) -> None:
        owner_id = _owner(owner_id)
        self._change(owner_id, reservation_ids, True)

    def release(self, owner_id: str, reservation_ids: list[str]) -> None:
        owner_id = _owner(owner_id)
        self._change(owner_id, reservation_ids, False)

    def _change(self, owner_id: str, reservation_ids: list[str], success: bool) -> None:
        if (not isinstance(reservation_ids, list) or not reservation_ids
                or len(reservation_ids) > 3 or len(set(reservation_ids)) != len(reservation_ids)
                or any(not isinstance(i, str) or len(i) != 32
                       or any(c not in "0123456789abcdef" for c in i) for i in reservation_ids)):
            raise ValueError("Reservas inválidas")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in reservation_ids)
            existing = db.execute(
                f"SELECT id FROM affiliate_video_quota WHERE owner_id=? AND status='reserved' AND id IN ({placeholders})",
                [owner_id, *reservation_ids],
            ).fetchall()
            if len(existing) != len(reservation_ids):
                raise ValueError("Reserva não encontrada ou já finalizada")
            if success:
                db.execute(
                    f"UPDATE affiliate_video_quota SET status='completed' WHERE owner_id=? AND id IN ({placeholders})",
                    [owner_id, *reservation_ids],
                )
            else:
                db.execute(
                    f"DELETE FROM affiliate_video_quota WHERE owner_id=? AND status='reserved' AND id IN ({placeholders})",
                    [owner_id, *reservation_ids],
                )

    def usage(self, owner_id: str) -> int:
        owner_id = _owner(owner_id)
        with self._connect() as db:
            return db.execute(
                "SELECT COUNT(*) FROM affiliate_video_quota WHERE owner_id=? AND day=? AND status='completed'",
                (owner_id, _day()),
            ).fetchone()[0]
