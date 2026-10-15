"""Validate portable Afiliados Creator project JSON without trusting imported prompts."""
from __future__ import annotations

import json

from app.afiliados.core import AffiliateBrief, prepare_draft

MAX_PROJECT_BYTES = 16_384


def import_project(payload: bytes) -> dict:
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_PROJECT_BYTES:
        raise ValueError("Projeto vazio ou acima de 16 KB")
    try:
        raw = json.loads(payload.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Arquivo JSON inválido") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Versão de projeto não suportada")
    data = raw.get("product")
    if not isinstance(data, dict):
        raise ValueError("Dados do produto ausentes")
    fields = ("product_name", "product_url", "features", "duration", "cta", "voice", "price_note")
    if set(data) != set(fields):
        raise ValueError("Campos do produto inválidos")
    try:
        brief = AffiliateBrief(**{key: data[key] for key in fields})
        script = raw.get("script", "")
        if not isinstance(script, str):
            raise ValueError("Roteiro inválido")
        # Rebuild prompt and generation settings; ignore any injected configuration.
        return prepare_draft(brief, script)
    except (TypeError, ValueError) as exc:
        raise ValueError("Dados do projeto inválidos") from exc
