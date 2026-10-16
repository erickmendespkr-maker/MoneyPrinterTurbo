"""Persistent account-scoped throttling for prototype authentication."""
import hashlib
import sqlite3
import time


def enforce_limit(db: sqlite3.Connection, action: str, email: str, maximum: int, window: int) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS affiliate_auth_attempts (
        action TEXT NOT NULL, subject_hash TEXT NOT NULL,
        window_start INTEGER NOT NULL, attempts INTEGER NOT NULL,
        PRIMARY KEY(action,subject_hash)
    )""")
    now = int(time.time())
    subject_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    row = db.execute("SELECT window_start,attempts FROM affiliate_auth_attempts WHERE action=? AND subject_hash=?",
                     (action, subject_hash)).fetchone()
    if row and now - row[0] < window and row[1] >= maximum:
        raise ValueError("Muitas tentativas. Aguarde antes de tentar novamente.")
    if not row or now - row[0] >= window:
        db.execute("INSERT INTO affiliate_auth_attempts VALUES (?,?,?,1) "
                   "ON CONFLICT(action,subject_hash) DO UPDATE SET window_start=excluded.window_start,attempts=1",
                   (action, subject_hash, now))
    else:
        db.execute("UPDATE affiliate_auth_attempts SET attempts=attempts+1 WHERE action=? AND subject_hash=?",
                   (action, subject_hash))
