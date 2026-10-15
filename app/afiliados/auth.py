"""Local prototype authentication with server-side opaque sessions.

Not a production identity service: deploy behind HTTPS, add email verification,
rate limiting, password reset, CSRF review and a shared persistent database
before exposing publicly. Never accept owner IDs from client input.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from pathlib import Path

EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,190}$")
SESSION_SECONDS = 12 * 3600


class LocalAuth:
    def __init__(self, database_path: Path):
        self.path = Path(database_path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
            salt BLOB NOT NULL, password_hash BLOB NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_sessions (
            token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES affiliate_users(id)
        )""")
        return db

    @staticmethod
    def _credentials(email: str, password: str) -> str:
        if not isinstance(email, str) or len(email) > 254 or not EMAIL.fullmatch(email):
            raise ValueError("E-mail inválido")
        if not isinstance(password, str) or len(password) < 12 or len(password) > 128:
            raise ValueError("A senha deve ter entre 12 e 128 caracteres")
        return email.strip().casefold()

    @staticmethod
    def _derive(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)

    def register(self, email: str, password: str) -> str:
        email = self._credentials(email, password)
        salt = secrets.token_bytes(16)
        owner_id = secrets.token_hex(16)
        digest = self._derive(password, salt)
        try:
            with self._connect() as db:
                db.execute("INSERT INTO affiliate_users VALUES (?,?,?,?)", (owner_id, email, salt, digest))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Não foi possível criar esta conta") from exc
        return owner_id

    def login(self, email: str, password: str) -> str:
        email = self._credentials(email, password)
        with self._connect() as db:
            row = db.execute("SELECT id,salt,password_hash FROM affiliate_users WHERE email=?", (email,)).fetchone()
            # Perform expensive hashing even when email is unknown to reduce timing leakage.
            salt = row[1] if row else b"\x00" * 16
            computed = self._derive(password, salt)
            if row is None or not hmac.compare_digest(computed, row[2]):
                raise ValueError("Credenciais inválidas")
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO affiliate_sessions VALUES (?,?,?)",
                       (hashlib.sha256(token.encode()).hexdigest(), row[0], int(time.time()) + SESSION_SECONDS))
        return token

    def resolve(self, token: str) -> str | None:
        if not isinstance(token, str) or len(token) > 256 or not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as db:
            row = db.execute("SELECT owner_id FROM affiliate_sessions WHERE token_hash=? AND expires_at>?",
                             (digest, int(time.time()))).fetchone()
        return row[0] if row else None

    def logout(self, token: str) -> None:
        if not isinstance(token, str) or len(token) > 256:
            return
        with self._connect() as db:
            db.execute("DELETE FROM affiliate_sessions WHERE token_hash=?",
                       (hashlib.sha256(token.encode()).hexdigest(),))
