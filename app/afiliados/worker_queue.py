"""Trusted worker-only Supabase RPC client for durable video jobs.

Worker credentials are NEVER used by a user-facing route. All claim/finalize
operations require a service_role JWT verified by Supabase, plus a live lease.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from uuid import UUID

from app.afiliados.plans import get_plan_policy
from app.afiliados.private_object_storage import PrivateObjectStorage
from app.afiliados.production_auth import AuthServiceUnavailable, _NoRedirects

SHA256 = re.compile(r"^[0-9a-f]{64}$")
FAIL_CODES = {"invalid_input", "render_failed", "storage_failed", "timeout", "worker_failed"}
ALLOWED_CALLS = {
    "affiliate_worker_claim", "affiliate_worker_heartbeat",
    "affiliate_worker_finish", "affiliate_worker_fail",
}


def _id(value: str) -> str:
    if not isinstance(value, str):
        raise AuthServiceUnavailable("Identificador inválido do trabalhador")
    try:
        result = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise AuthServiceUnavailable("Identificador inválido do trabalhador") from exc
    if result != value.lower():
        raise AuthServiceUnavailable("Identificador inválido do trabalhador")
    return result


@dataclass(frozen=True)
class WorkerLease:
    job_id: str
    owner_id: str
    kind: str
    variant: str
    plan: str
    input_key: str
    lease_token: str


class SupabaseWorkerQueue:
    def __init__(self, storage: PrivateObjectStorage):
        if not isinstance(storage, PrivateObjectStorage):
            raise ValueError("Armazenamento privado obrigatório")
        self.storage = storage
        self._secret = storage._service_key
        self.base_url = storage.auth.auth_url.removesuffix("/auth/v1") + "/rest/v1/rpc/"
        self._opener = urllib.request.build_opener(_NoRedirects())

    def _rpc(self, name: str, data: dict) -> object:
        if name not in ALLOWED_CALLS:
            raise ValueError("Operação do trabalhador inválida")
        request = urllib.request.Request(
            self.base_url + name, data=json.dumps(data).encode("utf-8"),
            method="POST",
            headers={
                "apikey": self._secret,
                "Authorization": "Bearer " + self._secret,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(request, timeout=15) as response:
                if not 200 <= response.status < 300:
                    raise AuthServiceUnavailable("Fila de trabalhos indisponível")
                raw = response.read(8193)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise AuthServiceUnavailable("Fila de trabalhos indisponível") from exc
        if len(raw) > 8192:
            raise AuthServiceUnavailable("Resposta da fila excedeu o limite")
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise AuthServiceUnavailable("Resposta da fila inválida") from exc

    def claim(self) -> WorkerLease | None:
        payload = self._rpc("affiliate_worker_claim", {})
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise AuthServiceUnavailable("Trabalho inválido")
        job = _id(payload.get("id"))
        owner = _id(payload.get("owner_id"))
        lease = _id(payload.get("lease_token"))
        kind, variant, plan = (payload.get("kind"), payload.get("variant"), payload.get("plan"))
        if (kind not in ("video", "campaign")
                or variant not in ("impacto", "beneficio", "curiosidade")
                or not isinstance(plan, str)):
            raise AuthServiceUnavailable("Plano ou vídeo inválido")
        policy = get_plan_policy(plan)
        if ((kind == "campaign" and (plan != "creator" or variant != "impacto"))
                or (kind == "video" and policy.videos_per_ad == 1
                    and variant != "impacto")):
            raise AuthServiceUnavailable("Trabalho incompatível com o plano")
        expected = self.storage.object_key(owner, job, "input")
        if payload.get("input_key") != expected:
            raise AuthServiceUnavailable("Arquivo de trabalho inválido")
        return WorkerLease(job, owner, kind, variant, plan, expected, lease)

    def heartbeat(self, lease: WorkerLease) -> bool:
        result = self._rpc("affiliate_worker_heartbeat", {
            "p_job_id": lease.job_id, "p_lease_token": lease.lease_token,
        })
        if type(result) is not bool:
            raise AuthServiceUnavailable("Resposta de lease inválida")
        return result

    def finish(self, lease: WorkerLease, sha256: str,
               *, output_bytes: int, wall_ms: int) -> str:
        if not isinstance(sha256, str) or not SHA256.fullmatch(sha256):
            raise ValueError("Hash de saída inválido")
        max_bytes = 367001600 if lease.kind == "campaign" else 104857600
        if (type(output_bytes) is not int or not 12 <= output_bytes <= max_bytes
                or type(wall_ms) is not int or not 0 <= wall_ms <= 21600000):
            raise ValueError("Métricas de processamento inválidas")
        result = self._rpc("affiliate_worker_finish", {
            "p_job_id": lease.job_id, "p_lease_token": lease.lease_token,
            "p_sha256": sha256, "p_output_bytes": output_bytes, "p_wall_ms": wall_ms,
        })
        expected = self.storage.object_key(lease.owner_id, lease.job_id, lease.kind)
        if result != expected:
            raise AuthServiceUnavailable("Resultado de gravação inconsistente")
        return expected

    def fail(self, lease: WorkerLease, code: str) -> bool:
        if code not in FAIL_CODES:
            raise ValueError("Código de falha inválido")
        result = self._rpc("affiliate_worker_fail", {
            "p_job_id": lease.job_id, "p_lease_token": lease.lease_token,
            "p_error_code": code,
        })
        if type(result) is not bool:
            raise AuthServiceUnavailable("Resposta de falha inválida")
        return result
