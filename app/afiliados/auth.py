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

from app.afiliados.auth_limits import enforce_limit
from app.afiliados.verification_policy import VERIFICATION_TOKEN_LIFETIME_SECONDS
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
        columns = {row[1] for row in db.execute("PRAGMA table_info(affiliate_users)")}
        if "verified_at" not in columns:
            db.execute("ALTER TABLE affiliate_users ADD COLUMN verified_at INTEGER")
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_email_verification (
            token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES affiliate_users(id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_sessions (
            token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES affiliate_users(id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_password_resets (
            token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
            expires_at INTEGER NOT NULL, used_at INTEGER,
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

    def create_verification_token(self, email: str) -> str | None:
        """Issue a single-use confirmation link, rate-limited per address.

        The raw token must only be delivered to that address by server-side mail.
        """
        if not isinstance(email, str) or len(email) > 254 or not EMAIL.fullmatch(email):
            raise ValueError("E-mail inválido")
        normalized = email.strip().casefold()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            enforce_limit(db, "verify_email", normalized, maximum=3, window=3600)
            db.commit()
            row = db.execute("SELECT id,verified_at FROM affiliate_users WHERE email=?",
                             (normalized,)).fetchone()
            if row is None or row[1] is not None:
                return None
            owner_id = row[0]
            db.execute("DELETE FROM affiliate_email_verification WHERE owner_id=?", (owner_id,))
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO affiliate_email_verification VALUES (?,?,?)",
                       (hashlib.sha256(token.encode()).hexdigest(), owner_id,
                        int(time.time()) + VERIFICATION_TOKEN_LIFETIME_SECONDS))
        return token

    def verify_email(self, token: str) -> None:
        """Confirm possession of the mailbox before allowing free generation."""
        if not isinstance(token, str) or not 32 <= len(token) <= 256:
            raise ValueError("Link de verificação inválido ou expirado")
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT owner_id FROM affiliate_email_verification
                WHERE token_hash=? AND expires_at>?""",
                (digest, int(time.time()))).fetchone()
            if row is None:
                raise ValueError("Link de verificação inválido ou expirado")
            db.execute("UPDATE affiliate_users SET verified_at=? WHERE id=?",
                       (int(time.time()), row[0]))
            db.execute("DELETE FROM affiliate_email_verification WHERE owner_id=?", (row[0],))

    def is_verified(self, owner_id: str) -> bool:
        """Use only owner_id obtained by resolving a server-issued session."""
        if not isinstance(owner_id, str) or not owner_id:
            return False
        with self._connect() as db:
            row = db.execute("SELECT verified_at FROM affiliate_users WHERE id=?",
                             (owner_id,)).fetchone()
        return row is not None and row[0] is not None

    def login(self, email: str, password: str) -> str:
        email = self._credentials(email, password)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            enforce_limit(db, "login", email, maximum=8, window=900)
            db.commit()
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

    def create_reset_token(self, email: str) -> str | None:
        """Issue a single-use 30-minute token. Unknown emails yield None."""
        if not isinstance(email, str) or len(email) > 254 or not EMAIL.fullmatch(email):
            raise ValueError("E-mail inválido")
        normalized = email.strip().casefold()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            enforce_limit(db, "reset", normalized, maximum=3, window=3600)
            db.commit()
            row = db.execute("SELECT id FROM affiliate_users WHERE email=?", (normalized,)).fetchone()
            if row is None:
                return None
            owner = row[0]
            # Invalidate older outstanding tokens on new request.
            db.execute("DELETE FROM affiliate_password_resets WHERE owner_id=?", (owner,))
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO affiliate_password_resets VALUES (?,?,?,NULL)",
                       (hashlib.sha256(token.encode()).hexdigest(), owner, int(time.time()) + 1800))
        return token

    def reset_password(self, token: str, new_password: str) -> None:
        if not isinstance(token, str) or len(token) > 256 or len(token) < 32:
            raise ValueError("Link de recuperação inválido ou expirado")
        if not isinstance(new_password, str) or not 12 <= len(new_password) <= 128:
            raise ValueError("A senha deve ter entre 12 e 128 caracteres")
        digest = hashlib.sha256(token.encode()).hexdigest()
        salt = secrets.token_bytes(16)
        password_hash = self._derive(new_password, salt)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT owner_id FROM affiliate_password_resets WHERE token_hash=? AND used_at IS NULL AND expires_at>?",
                             (digest, int(time.time()))).fetchone()
            if row is None:
                raise ValueError("Link de recuperação inválido ou expirado")
            owner = row[0]
            db.execute("UPDATE affiliate_users SET salt=?,password_hash=? WHERE id=?", (salt, password_hash, owner))
            db.execute("DELETE FROM affiliate_sessions WHERE owner_id=?", (owner,))
            db.execute("DELETE FROM affiliate_password_resets WHERE owner_id=?", (owner,))
