"""Cloudflare Turnstile proof validation for account creation.

This is a server-side check; never authorize registration based only on
a browser widget or an unverified form parameter.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
SITE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,128}$")
HOST_PATTERN = re.compile(r"^(?:[a-z0-9-]+\\.)+[a-z0-9-]+$", re.IGNORECASE)


@dataclass(frozen=True)
class TurnstileConfig:
    site_key: str
    secret_key: str
    hostname: str


def load_turnstile_config(*, required: bool = False) -> TurnstileConfig | None:
    """Absent config only allowed for local testing when not required."""
    site_key = os.environ.get("AFILIADOS_TURNSTILE_SITE_KEY", "").strip()
    secret = os.environ.get("AFILIADOS_TURNSTILE_SECRET_KEY", "").strip()
    hostname = os.environ.get("AFILIADOS_TURNSTILE_HOSTNAME", "").strip().lower()
    if not any((site_key, secret, hostname)):
        if required:
            raise RuntimeError("Proteção anti-bot não configurada")
        return None
    if (not SITE_KEY_PATTERN.fullmatch(site_key) or len(secret) < 10
            or len(secret) > 1024 or not HOST_PATTERN.fullmatch(hostname)):
        raise RuntimeError("Proteção anti-bot incompleta ou inválida")
    return TurnstileConfig(site_key, secret, hostname)


def verify_registration_token(token: str | None, config: TurnstileConfig) -> None:
    """Fail closed on invalid, expired, replayed or untrusted Turnstile proofs.

    The caller must use this only in a server-side registration action.
    Remote IP is deliberately omitted: the prototype has no trusted ingress
    from which to derive an anti-spoofed public address.
    """
    if (not isinstance(token, str) or not token or len(token) > 2048
            or not token.isascii() or any(ch.isspace() or not ch.isprintable() for ch in token)):
        raise PermissionError("Conclua a verificação de segurança para criar a conta")
    if not isinstance(config, TurnstileConfig):
        raise PermissionError("Verificação de segurança indisponível")
    data = urllib.parse.urlencode({
        "secret": config.secret_key,
        "response": token,
    }).encode("ascii")
    request = urllib.request.Request(
        SITEVERIFY_URL, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if response.status != 200:
                raise PermissionError("Verificação de segurança indisponível")
            raw = response.read(8193)
        if len(raw) > 8192:
            raise PermissionError("Verificação de segurança indisponível")
        result = json.loads(raw)
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
        raise PermissionError("Não foi possível validar a verificação de segurança") from exc
    if (not isinstance(result, dict) or result.get("success") is not True
            or result.get("hostname") != config.hostname
            or result.get("action") != "register"):
        raise PermissionError("Verificação de segurança inválida ou expirada")
