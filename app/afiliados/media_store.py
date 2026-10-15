"""Owner-scoped local media library for validated generated PNG and MP4 bytes.

Experimental backend, not public cloud storage. Caller must provide owner_id
from a verified server-side session. Never trust an owner_id from user input.
"""
from __future__ import annotations

import hashlib
import io
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from app.afiliados.storage import _owner

MAX_PNG_BYTES = 12 * 1024 * 1024
MAX_MP4_BYTES = 100 * 1024 * 1024
MAX_FILES_PER_OWNER = 100
MAX_TOTAL_BYTES_PER_OWNER = 512 * 1024 * 1024
ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
KINDS = {"thumbnail": "image/png", "video": "video/mp4"}


def _validate(kind: str, data: bytes) -> str:
    if kind not in KINDS:
        raise ValueError("Tipo de mídia inválido")
    limit = MAX_PNG_BYTES if kind == "thumbnail" else MAX_MP4_BYTES
    if not isinstance(data, bytes) or not data or len(data) > limit:
        raise ValueError("Arquivo vazio ou acima do limite")
    if kind == "thumbnail":
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "PNG" or image.width > 4096 or image.height > 4096:
                    raise ValueError("Imagem PNG inválida")
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError("Imagem PNG inválida") from exc
    else:
        # Container signature validation is not a substitute for sandboxed decoding.
        if len(data) < 12 or data[4:8] != b"ftyp" or data[8:12] not in (
            b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ", b"qt  ",
        ):
            raise ValueError("Arquivo MP4 inválido")
    return hashlib.sha256(data).hexdigest()


class MediaStore:
    def __init__(self, database_path: Path):
        self.path = Path(database_path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("""CREATE TABLE IF NOT EXISTS affiliate_media (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, kind TEXT NOT NULL,
            sha256 TEXT NOT NULL, payload BLOB NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_media_owner ON affiliate_media(owner_id, created_at)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_media_dedupe ON affiliate_media(owner_id, kind, sha256)")
        return db

    def save(self, owner_id: str, kind: str, data: bytes) -> str:
        owner_id = _owner(owner_id)
        digest = _validate(kind, data)
        with self._connect() as db:
            # Serialize quota decisions across simultaneous connections.
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT id FROM affiliate_media WHERE owner_id=? AND kind=? AND sha256=?",
                (owner_id, kind, digest),
            ).fetchone()
            if existing:
                return existing[0]
            count, used = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(length(payload)), 0) FROM affiliate_media WHERE owner_id=?",
                (owner_id,),
            ).fetchone()
            if count >= MAX_FILES_PER_OWNER:
                raise ValueError("Limite de arquivos atingido")
            if used + len(data) > MAX_TOTAL_BYTES_PER_OWNER:
                raise ValueError("Limite de armazenamento da conta atingido")
            media_id = uuid4().hex
            db.execute("INSERT INTO affiliate_media VALUES (?,?,?,?,?,?)", (
                media_id, owner_id, kind, digest, data, datetime.now(timezone.utc).isoformat()
            ))
        return media_id

    def list(self, owner_id: str) -> list[dict]:
        owner_id = _owner(owner_id)
        with self._connect() as db:
            rows = db.execute("""SELECT id,kind,sha256,length(payload),created_at
                FROM affiliate_media WHERE owner_id=? ORDER BY created_at DESC LIMIT 100""",
                (owner_id,)).fetchall()
        return [dict(zip(("id", "kind", "sha256", "size", "created_at"), row)) for row in rows]

    def load(self, owner_id: str, media_id: str) -> tuple[str, bytes]:
        owner_id = _owner(owner_id)
        if not isinstance(media_id, str) or not ID_PATTERN.fullmatch(media_id):
            raise ValueError("ID de mídia inválido")
        with self._connect() as db:
            row = db.execute("SELECT kind,payload FROM affiliate_media WHERE owner_id=? AND id=?",
                             (owner_id, media_id)).fetchone()
        if row is None:
            raise ValueError("Mídia não encontrada")
        return row[0], row[1]

    def delete(self, owner_id: str, media_id: str) -> bool:
        owner_id = _owner(owner_id)
        if not isinstance(media_id, str) or not ID_PATTERN.fullmatch(media_id):
            raise ValueError("ID de mídia inválido")
        with self._connect() as db:
            result = db.execute("DELETE FROM affiliate_media WHERE owner_id=? AND id=?",
                                (owner_id, media_id))
        return result.rowcount == 1
