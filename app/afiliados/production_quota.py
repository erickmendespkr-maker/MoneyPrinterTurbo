"""Transactional Supabase PostgREST quota client for the public backend.

Never accepts user IDs or subscription plan names from requests. A verified
Supabase Auth session is required for each action; SQL functions derive both
owner and plan from authenticated server-side records.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from uuid import UUID

from app.afiliados.production_auth import (
    AuthDenied, AuthServiceUnavailable, SupabaseAuth, _NoRedirects,
)

MAX_RPC_RESPONSE = 8192


@dataclass(frozen=True)
class PublicFreeStatus:
    remaining_seconds: int
    in_progress: bool
    attempt_retry_seconds: int
    capacity_retry_seconds: int

    @property
    def can_generate(self) -> bool:
        return (not self.in_progress and self.remaining_seconds == 0
                and self.attempt_retry_seconds == 0 and self.capacity_retry_seconds == 0)


class SupabaseVideoQuota:
    def __init__(self, auth: SupabaseAuth):
        if not isinstance(auth, SupabaseAuth):
            raise ValueError("Provedor de autenticação inválido")
        self.auth = auth
        self._opener = urllib.request.build_opener(_NoRedirects())
        self.rest_url = auth.auth_url.removesuffix("/auth/v1") + "/rest/v1/rpc/"

    def _rpc(self, name: str, bearer: str, payload: dict) -> object:
        if name not in (
            "affiliate_reserve_videos", "affiliate_complete_videos",
            "affiliate_release_videos", "affiliate_free_status", "affiliate_my_plan",
        ):
            raise ValueError("Operação de cota inválida")
        # This performs a live Auth /user check; no session token is trusted
        # based on JWT decoding or client-provided user metadata.
        self.auth.require_verified_user(bearer)
        request = urllib.request.Request(
            self.rest_url + name,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={
                "apikey": self.auth.publishable_key,
                "Authorization": "Bearer " + bearer,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(request, timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise AuthServiceUnavailable("Cotas indisponíveis")
                raw = response.read(MAX_RPC_RESPONSE + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403, 404, 409, 422, 429):
                raise AuthDenied("Geração não permitida ou limite temporariamente atingido") from None
            raise AuthServiceUnavailable("Cotas indisponíveis") from None
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise AuthServiceUnavailable("Cotas indisponíveis") from exc
        if len(raw) > MAX_RPC_RESPONSE:
            raise AuthServiceUnavailable("Resposta das cotas excedeu o limite")
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise AuthServiceUnavailable("Resposta de cota inválida") from exc

    def plan(self, access_token: str) -> str:
        """Plan is fetched from privileged billing data, never request metadata."""
        from app.afiliados.plans import PLANS
        plan = self._rpc("affiliate_my_plan", access_token, {})
        if not isinstance(plan, str) or plan not in PLANS:
            raise AuthServiceUnavailable("Plano inválido no servidor")
        return plan

    def reserve(self, access_token: str, count: int = 1) -> list[str]:
        if type(count) is not int or not 1 <= count <= 3:
            raise ValueError("Quantidade inválida")
        result = self._rpc("affiliate_reserve_videos", access_token,
                           {"p_count": count})
        if not isinstance(result, list) or len(result) != count:
            raise AuthServiceUnavailable("Resposta de reserva inválida")
        try:
            return [str(UUID(value)) for value in result]
        except (ValueError, AttributeError, TypeError) as exc:
            raise AuthServiceUnavailable("Resposta de reserva inválida") from exc

    @staticmethod
    def _ids(reservation_ids: list[str]) -> list[str]:
        if (not isinstance(reservation_ids, list) or not 1 <= len(reservation_ids) <= 3
                or any(not isinstance(item, str) for item in reservation_ids)
                or len(set(reservation_ids)) != len(reservation_ids)):
            raise ValueError("Reservas inválidas")
        try:
            return [str(UUID(value)) for value in reservation_ids]
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Reservas inválidas") from exc

    def complete(self, access_token: str, reservation_ids: list[str]) -> None:
        self._rpc("affiliate_complete_videos", access_token,
                  {"p_ids": self._ids(reservation_ids)})

    def release(self, access_token: str, reservation_ids: list[str]) -> None:
        self._rpc("affiliate_release_videos", access_token,
                  {"p_ids": self._ids(reservation_ids)})

    def free_status(self, access_token: str) -> PublicFreeStatus:
        data = self._rpc("affiliate_free_status", access_token, {})
        if not isinstance(data, dict):
            raise AuthServiceUnavailable("Estado de cota inválido")
        keys = ("remaining_seconds", "attempt_retry_seconds", "capacity_retry_seconds")
        if (any(type(data.get(k)) is not int or not 0 <= data[k] <= 172800 for k in keys)
                or type(data.get("in_progress")) is not bool):
            raise AuthServiceUnavailable("Estado de cota inválido")
        return PublicFreeStatus(
            data["remaining_seconds"], data["in_progress"],
            data["attempt_retry_seconds"], data["capacity_retry_seconds"],
        )
