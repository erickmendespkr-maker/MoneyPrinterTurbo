"""Server-side video quota ledger.

Free accounts have a rolling 24-hour cooldown after a successful render,
not a calendar-day reset. Paid plans retain Sao Paulo calendar-day quotas.
Reservations are transactional, including concurrent browser sessions.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.afiliados.plans import get_plan_policy
from app.afiliados.storage import _owner

TZ = ZoneInfo("America/Sao_Paulo")
FREE_COOLDOWN_SECONDS = 24 * 60 * 60
# A crashed renderer must not lock an account permanently. Production
# workers should renew leases or reconcile failed jobs before this timeout.
RESERVATION_TTL_SECONDS = 6 * 60 * 60
FREE_ATTEMPT_WINDOW_SECONDS = 60 * 60
FREE_MAX_RENDER_ATTEMPTS = 5
# Protect shared compute even when someone creates multiple free accounts.
# Local SQLite limit; public launch requires one centralized quota database.
MAX_GLOBAL_FREE_ATTEMPTS_PER_HOUR = 12
MAX_GLOBAL_FREE_ATTEMPTS_PER_DAY = 40


def _now() -> int:
    return int(time.time())


def _day() -> str:
    return datetime.fromtimestamp(_now(), TZ).date().isoformat()


@dataclass(frozen=True)
class FreeQuotaStatus:
    remaining_seconds: int
    in_progress: bool
    attempt_retry_seconds: int = 0
    capacity_retry_seconds: int = 0

    @property
    def can_generate(self) -> bool:
        return (not self.in_progress and self.remaining_seconds == 0
                and self.attempt_retry_seconds == 0 and self.capacity_retry_seconds == 0)


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
            created_at TEXT NOT NULL, completed_at INTEGER
        )""")
        # Upgrade existing local installations without deleting past usage.
        columns = {row[1] for row in db.execute("PRAGMA table_info(affiliate_video_quota)")}
        if "completed_at" not in columns:
            db.execute("ALTER TABLE affiliate_video_quota ADD COLUMN completed_at INTEGER")
        # Historic rows predate completed_at; use creation timestamp as a
        # conservative approximation, instead of granting a free reset.
        historic = db.execute("""SELECT id, created_at FROM affiliate_video_quota
            WHERE status='completed' AND completed_at IS NULL""").fetchall()
        for reservation_id, created_at in historic:
            try:
                timestamp = int(datetime.fromisoformat(created_at).timestamp())
            except (TypeError, ValueError, OverflowError):
                timestamp = _now()
            db.execute("UPDATE affiliate_video_quota SET completed_at=? WHERE id=?",
                       (timestamp, reservation_id))
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_free_render_attempts (
            owner_id TEXT NOT NULL, started_at INTEGER NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_free_attempt_owner_time ON affiliate_free_render_attempts(owner_id,started_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_video_quota_owner_day ON affiliate_video_quota(owner_id,day,status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_video_quota_cooldown ON affiliate_video_quota(owner_id,status,completed_at)")
        db.commit()
        return db

    @staticmethod
    def _expire_stale(db: sqlite3.Connection, owner_id: str, now: int) -> None:
        # Only expired reservations can be removed; a late completion will
        # then fail because its reservation no longer exists.
        old = db.execute("""SELECT id, created_at FROM affiliate_video_quota
            WHERE owner_id=? AND status='reserved'""", (owner_id,)).fetchall()
        for reservation_id, timestamp in old:
            try:
                created = datetime.fromisoformat(timestamp)
                created_ts = int(created.timestamp()) if created.tzinfo else now
            except (ValueError, TypeError, OverflowError):
                created_ts = now
            if now - created_ts >= RESERVATION_TTL_SECONDS:
                db.execute("DELETE FROM affiliate_video_quota WHERE id=? AND status='reserved'", (reservation_id,))

    @staticmethod
    def _free_state(db: sqlite3.Connection, owner_id: str, now: int) -> FreeQuotaStatus:
        last_completed = db.execute("""SELECT MAX(completed_at) FROM affiliate_video_quota
            WHERE owner_id=? AND status='completed'""", (owner_id,)).fetchone()[0]
        pending = db.execute("""SELECT 1 FROM affiliate_video_quota
            WHERE owner_id=? AND status='reserved' LIMIT 1""", (owner_id,)).fetchone() is not None
        remaining = max(0, int(last_completed) + FREE_COOLDOWN_SECONDS - now) if last_completed is not None else 0
        attempt_row = db.execute("""SELECT COUNT(*), MIN(started_at)
            FROM affiliate_free_render_attempts
            WHERE owner_id=? AND started_at>?""",
            (owner_id, now - FREE_ATTEMPT_WINDOW_SECONDS)).fetchone()
        attempts, first_attempt = attempt_row
        retry = (max(0, int(first_attempt) + FREE_ATTEMPT_WINDOW_SECONDS - now)
                 if attempts >= FREE_MAX_RENDER_ATTEMPTS else 0)
        global_attempts, earliest = db.execute(
            """SELECT COUNT(*), MIN(started_at) FROM affiliate_free_render_attempts
            WHERE started_at>?""", (now - FREE_ATTEMPT_WINDOW_SECONDS,)
        ).fetchone()
        pool_wait = (max(0, int(earliest) + FREE_ATTEMPT_WINDOW_SECONDS - now)
                     if global_attempts >= MAX_GLOBAL_FREE_ATTEMPTS_PER_HOUR else 0)
        daily_count, earliest_daily = db.execute(
            """SELECT COUNT(*), MIN(started_at) FROM affiliate_free_render_attempts
            WHERE started_at>?""", (now - FREE_COOLDOWN_SECONDS,)
        ).fetchone()
        daily_wait = (max(0, int(earliest_daily) + FREE_COOLDOWN_SECONDS - now)
                      if daily_count >= MAX_GLOBAL_FREE_ATTEMPTS_PER_DAY else 0)
        pool_wait = max(pool_wait, daily_wait)
        return FreeQuotaStatus(
            remaining_seconds=remaining, in_progress=pending,
            attempt_retry_seconds=retry, capacity_retry_seconds=pool_wait,
        )

    def free_status(self, owner_id: str) -> FreeQuotaStatus:
        """Read status from persistent server state, never browser cookies."""
        owner_id = _owner(owner_id)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._expire_stale(db, owner_id, _now())
            return self._free_state(db, owner_id, _now())

    def reserve(self, owner_id: str, plan: str, count: int = 1) -> list[str]:
        """Atomically reserve all videos before render. Plan must be server-resolved."""
        owner_id = _owner(owner_id)
        policy = get_plan_policy(plan)
        if type(count) is not int or count < 1 or count > policy.videos_per_ad:
            raise ValueError("Quantidade de vídeos não permitida para o plano")
        now = _now()
        day = _day()
        ids = [uuid4().hex for _ in range(count)]
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._expire_stale(db, owner_id, now)
            if plan == "gratis":
                status = self._free_state(db, owner_id, now)
                if status.in_progress:
                    raise PermissionError("Você já tem uma geração gratuita em andamento")
                if status.remaining_seconds > 0:
                    raise PermissionError("Limite gratuito: aguarde 24 horas após a última geração concluída")
                if status.attempt_retry_seconds > 0:
                    raise PermissionError("Muitas tentativas de geração gratuita. Tente novamente mais tarde.")
                if status.capacity_retry_seconds > 0:
                    raise PermissionError("Capacidade gratuita temporariamente esgotada. Tente novamente mais tarde.")
                db.execute("DELETE FROM affiliate_free_render_attempts WHERE started_at<=?",
                           (now - FREE_COOLDOWN_SECONDS,))
                db.execute("INSERT INTO affiliate_free_render_attempts VALUES (?,?)", (owner_id, now))
            else:
                used = db.execute("""SELECT COUNT(*) FROM affiliate_video_quota
                    WHERE owner_id=? AND day=?""", (owner_id, day)).fetchone()[0]
                if policy.daily_video_limit is not None and used + count > policy.daily_video_limit:
                    raise PermissionError("Limite diário de vídeos atingido")
            db.executemany("INSERT INTO affiliate_video_quota VALUES (?,?,?,?,?,NULL)",
                [(rid, owner_id, day, "reserved",
                  datetime.fromtimestamp(now, timezone.utc).isoformat()) for rid in ids])
        return ids

    def complete(self, owner_id: str, reservation_ids: list[str]) -> None:
        self._change(_owner(owner_id), reservation_ids, True)

    def release(self, owner_id: str, reservation_ids: list[str]) -> None:
        self._change(_owner(owner_id), reservation_ids, False)

    def _change(self, owner_id: str, reservation_ids: list[str], success: bool) -> None:
        if (not isinstance(reservation_ids, list) or not reservation_ids
                or len(reservation_ids) > 3 or len(set(reservation_ids)) != len(reservation_ids)
                or any(not isinstance(i, str) or len(i) != 32
                       or any(c not in "0123456789abcdef" for c in i) for i in reservation_ids)):
            raise ValueError("Reservas inválidas")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._expire_stale(db, owner_id, _now())
            placeholders = ",".join("?" for _ in reservation_ids)
            existing = db.execute(
                f"SELECT id FROM affiliate_video_quota WHERE owner_id=? AND status='reserved' AND id IN ({placeholders})",
                [owner_id, *reservation_ids],
            ).fetchall()
            if len(existing) != len(reservation_ids):
                raise ValueError("Reserva não encontrada, expirada ou já finalizada")
            if success:
                db.execute(
                    f"UPDATE affiliate_video_quota SET status='completed',completed_at=? WHERE owner_id=? AND id IN ({placeholders})",
                    [_now(), owner_id, *reservation_ids],
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
