"""Supabase Auth adapter for the future public Afiliados Creator backend.

No service-role key, no browser-provided owner IDs, and no unverified JWT
payload used as identity. Supabase Auth /user validates the bearer token.
Network requests occur only when a method is explicitly invoked.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from uuid import UUID

from app.afiliados.storage import _owner

SUPABASE_HOST = re.compile(r"^https://[a-z0-9-]+\.supabase\.co/?$", re.ASCII)
MAX_JSON_BYTES = 64 * 1024


@dataclass(frozen=True)
class VerifiedIdentity:
    owner_id: str
    email: str
    email_verified: bool


class AuthServiceUnavailable(RuntimeError):
    pass


class AuthDenied(PermissionError):
    pass


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class SupabaseAuth:
    """Use only a publishable/anon key. Never accept a service-role secret."""

    def __init__(self, project_url: str, publishable_key: str):
        if (not isinstance(project_url, str)
                or not SUPABASE_HOST.fullmatch(project_url)
                or not isinstance(publishable_key, str)
                or not 20 <= len(publishable_key) <= 4096
                or publishable_key.startswith(("sb_secret_", "service_role"))):
            raise ValueError("Configuração do Supabase Auth inválida")
        self.auth_url = project_url.rstrip("/") + "/auth/v1"
        self.publishable_key = publishable_key
        self._opener = urllib.request.build_opener(_NoRedirects())

    @classmethod
    def from_env(cls) -> SupabaseAuth:
        return cls(
            os.environ.get("AFILIADOS_SUPABASE_URL", ""),
            os.environ.get("AFILIADOS_SUPABASE_PUBLISHABLE_KEY", ""),
        )

    def _request(self, method: str, endpoint: str, payload: dict | None = None,
                 *, access_token: str | None = None) -> dict:
        # Routes are fixed in source: users cannot choose arbitrary endpoints.
        if endpoint not in (
            "/signup", "/token?grant_type=password",
            "/token?grant_type=refresh_token", "/user", "/logout", "/recover",
        ):
            raise ValueError("Rota de autenticação inválida")
        if access_token is not None and (not isinstance(access_token, str)
                                         or not 20 <= len(access_token) <= 8192
                                         or any(ch.isspace() for ch in access_token)):
            raise AuthDenied("Sessão inválida")
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
        headers = {
            "apikey": self.publishable_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if access_token is not None:
            headers["Authorization"] = "Bearer " + access_token
        req = urllib.request.Request(
            self.auth_url + endpoint, data=data, method=method,
            headers=headers,
        )
        try:
            with self._opener.open(req, timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise AuthServiceUnavailable("Autenticação indisponível")
                raw = response.read(MAX_JSON_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403, 422, 429):
                raise AuthDenied("Credenciais inválidas, não verificadas ou temporariamente limitadas") from None
            raise AuthServiceUnavailable("Autenticação indisponível") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AuthServiceUnavailable("Autenticação indisponível") from exc
        if len(raw) > MAX_JSON_BYTES:
            raise AuthServiceUnavailable("Resposta da autenticação excedeu o limite")
        if not raw.strip():
            return {}
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise AuthServiceUnavailable("Resposta inválida da autenticação") from exc
        if not isinstance(result, dict):
            raise AuthServiceUnavailable("Resposta inválida da autenticação")
        return result

    @staticmethod
    def _credentials(email: str, password: str) -> tuple[str, str]:
        if (not isinstance(email, str) or not isinstance(password, str)
                or not 3 <= len(email) <= 254 or "@" not in email
                or any(ch.isspace() for ch in email) or not 12 <= len(password) <= 128):
            raise ValueError("E-mail ou senha inválidos")
        return email.strip().casefold(), password

    def register(self, email: str, password: str, *, captcha_token: str) -> None:
        """Require server-validated Turnstile before every public signup."""
        from app.afiliados.turnstile import load_turnstile_config, verify_registration_token
        email, password = self._credentials(email, password)
        config = load_turnstile_config(required=True)
        verify_registration_token(captcha_token, config)
        result = self._request("POST", "/signup", {"email": email, "password": password})
        # Fail closed when the provider is configured to auto-confirm signups.
        if result.get("access_token") or result.get("refresh_token"):
            raise AuthServiceUnavailable(
                "Confirmação de e-mail não está obrigatória no provedor"
            )

    def login(self, email: str, password: str) -> dict:
        email, password = self._credentials(email, password)
        result = self._request("POST", "/token?grant_type=password",
                               {"email": email, "password": password})
        session = self._session(result)
        self.require_verified_user(session["access_token"])
        return session

    def refresh(self, refresh_token: str) -> dict:
        if (not isinstance(refresh_token, str) or not 20 <= len(refresh_token) <= 4096
                or any(ch.isspace() for ch in refresh_token)):
            raise AuthDenied("Sessão expirada")
        result = self._request("POST", "/token?grant_type=refresh_token",
                               {"refresh_token": refresh_token})
        session = self._session(result)
        self.require_verified_user(session["access_token"])
        return session

    @staticmethod
    def _session(data: dict) -> dict:
        token = data.get("access_token")
        refresh = data.get("refresh_token")
        expiry = data.get("expires_in")
        if (not isinstance(token, str) or len(token) < 20
                or not isinstance(refresh, str) or len(refresh) < 20
                or type(expiry) is not int or not 1 <= expiry <= 86400):
            raise AuthDenied("Sessão inválida")
        return {"access_token": token, "refresh_token": refresh,
                "expires_in": expiry}

    def require_verified_user(self, access_token: str) -> VerifiedIdentity:
        """Always look up the authenticated user server-side before mutation."""
        user = self._request("GET", "/user", access_token=access_token)
        try:
            owner_id = str(UUID(user["id"]))
            _owner(owner_id)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise AuthDenied("Identidade do usuário inválida") from exc
        email = user.get("email")
        if not isinstance(email, str) or not email or len(email) > 254:
            raise AuthDenied("Identidade do usuário inválida")
        verified = bool(user.get("email_confirmed_at"))
        if not verified:
            raise AuthDenied("Confirme seu e-mail antes de gerar vídeos")
        return VerifiedIdentity(owner_id, email, True)

    def recover(self, email: str) -> None:
        if not isinstance(email, str) or len(email) > 254 or "@" not in email:
            raise ValueError("E-mail inválido")
        self._request("POST", "/recover", {"email": email.strip().casefold()})

    def logout(self, access_token: str) -> None:
        self._request("POST", "/logout", {}, access_token=access_token)
