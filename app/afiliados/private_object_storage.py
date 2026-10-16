"""Private Supabase Storage adapter for queued render inputs and outputs.

This adapter is strictly server/worker-side: service-role credentials MUST NOT
be passed into browser JavaScript, public client bundles or GitHub. Bucket must
be PRIVATE with no direct user-read policy; signed URLs require owner checks.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from uuid import UUID

from app.afiliados.production_auth import (
    AuthDenied, AuthServiceUnavailable, SupabaseAuth, _NoRedirects,
)
from app.afiliados.render_inputs import (
    MAX_BUNDLE_INPUT_BYTES, pack_inputs, unpack_inputs,
)

MAX_VIDEO_BYTES = 100 * 1024 * 1024
MAX_CAMPAIGN_BYTES = 350 * 1024 * 1024
BUCKET_NAME = "afiliados-private"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _uuid(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Identificador inválido")
    try:
        result = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Identificador inválido") from exc
    if result != value.lower():
        raise ValueError("Identificador inválido")
    return result


def _service_role_key(value: str) -> str:
    """Check role only to DENY wrong-shaped keys; provider verifies signature."""
    if not isinstance(value, str) or not 60 <= len(value) <= 4096:
        raise ValueError("Chave privada do servidor inválida")
    if value.count(".") != 2:
        raise ValueError("Configurar JWT service_role apenas no servidor")
    try:
        payload = value.split(".")[1]
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        if json.loads(decoded).get("role") != "service_role":
            raise ValueError("Exige chave service_role")
    except (UnicodeDecodeError, ValueError, AttributeError) as exc:
        raise ValueError("Chave privada do servidor inválida") from exc
    return value


class PrivateObjectStorage:
    def __init__(self, auth: SupabaseAuth, service_role_key: str):
        if not isinstance(auth, SupabaseAuth):
            raise ValueError("Autenticação confiável obrigatória")
        self.auth = auth
        self._service_key = _service_role_key(service_role_key)
        self.base_url = auth.auth_url.removesuffix("/auth/v1") + "/storage/v1"
        self._opener = urllib.request.build_opener(_NoRedirects())

    @classmethod
    def from_env(cls, auth: SupabaseAuth) -> PrivateObjectStorage:
        return cls(auth, os.environ.get("AFILIADOS_SUPABASE_SERVICE_ROLE_KEY", ""))

    @staticmethod
    def object_key(owner_id: str, job_id: str, kind: str) -> str:
        owner, job = _uuid(owner_id), _uuid(job_id)
        suffixes = {
            "input": "input.zip",
            "video": "output.mp4",
            "campaign": "output.zip",
        }
        if kind not in suffixes:
            raise ValueError("Tipo de objeto inválido")
        return f"{owner}/{job}/{suffixes[kind]}"

    def _request(self, method: str, endpoint: str, data: bytes | None = None,
                 *, media_type: str = "application/json", max_result: int = 8192,
                 upsert: bool = False) -> bytes:
        if (not isinstance(endpoint, str)
                or not endpoint.startswith("/object/")
                or "://" in endpoint or ".." in endpoint):
            raise ValueError("Caminho de armazenamento inválido")
        headers = {
            "apikey": self._service_key,
            "Authorization": "Bearer " + self._service_key,
            "Content-Type": media_type,
            "Accept": "application/json",
        }
        if upsert:
            headers["x-upsert"] = "true"
        request = urllib.request.Request(
            self.base_url + endpoint, data=data, headers=headers, method=method,
        )
        try:
            with self._opener.open(request, timeout=30) as response:
                if not 200 <= response.status < 300:
                    raise AuthServiceUnavailable("Armazenamento indisponível")
                result = response.read(max_result + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403, 404, 413, 429):
                raise AuthDenied("Operação de mídia recusada") from None
            raise AuthServiceUnavailable("Armazenamento indisponível") from None
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise AuthServiceUnavailable("Armazenamento indisponível") from exc
        if len(result) > max_result:
            raise AuthServiceUnavailable("Arquivo acima do limite permitido")
        return result

    @staticmethod
    def _path(key: str) -> str:
        # Generated keys contain only canonical UUIDs and fixed file names.
        return "/object/" + urllib.parse.quote(BUCKET_NAME, safe="") + "/" + urllib.parse.quote(key, safe="/")

    def stage_input(self, access_token: str, job_id: str, package: bytes) -> str:
        """Call from authenticated backend; never expose the service role key."""
        identity = self.auth.require_verified_user(access_token)
        unpack_inputs(package)  # Reject excessive/poisoned input before upload.
        key = self.object_key(identity.owner_id, job_id, "input")
        self._request("POST", self._path(key), data=package,
                      media_type="application/zip")
        return key

    def stage_inputs(self, access_token: str, job_id: str, **fields) -> str:
        return self.stage_input(access_token, job_id, pack_inputs(**fields))

    def fetch_input(self, owner_id: str, job_id: str) -> bytes:
        key = self.object_key(owner_id, job_id, "input")
        return self._request("GET", self._path(key),
                             max_result=MAX_BUNDLE_INPUT_BYTES)

    def put_output(self, owner_id: str, job_id: str, kind: str, data: bytes) -> tuple[str, str]:
        key = self.object_key(owner_id, job_id, kind)
        if kind == "video":
            if (not isinstance(data, bytes) or not 12 <= len(data) <= MAX_VIDEO_BYTES
                    or data[4:8] != b"ftyp"):
                raise ValueError("Vídeo de saída inválido")
            media_type = "video/mp4"
        elif kind == "campaign":
            if (not isinstance(data, bytes) or not 1 <= len(data) <= MAX_CAMPAIGN_BYTES
                    or not zipfile.is_zipfile(io.BytesIO(data))):
                raise ValueError("Pacote de campanha inválido")
            media_type = "application/zip"
        else:
            raise ValueError("Tipo de saída inválido")
        # Deterministic output key permits retry after a worker crash during
        # upload/finish. Never expose the file until DB status is completed.
        self._request("POST", self._path(key), data=data,
                      media_type=media_type, upsert=True)
        return key, hashlib.sha256(data).hexdigest()

    def signed_result_url(self, access_token: str, job_id: str,
                          quotas, expires_in: int = 60) -> str:
        """Verify ownership via a live authenticated RPC before signing.

        No caller-provided status, owner ID or object path is accepted.
        """
        from app.afiliados.production_quota import SupabaseVideoQuota
        if not isinstance(quotas, SupabaseVideoQuota):
            raise AuthDenied("Consulta de trabalho obrigatória")
        identity = self.auth.require_verified_user(access_token)
        status = quotas.job_status(access_token, job_id)
        if (status.status != "completed" or
                type(expires_in) is not int or not 1 <= expires_in <= 120):
            raise AuthDenied("Arquivo não disponível")
        key = self.object_key(identity.owner_id, job_id, status.kind)
        endpoint = "/object/sign/" + BUCKET_NAME + "/" + key
        raw = self._request("POST", endpoint,
                            json.dumps({"expiresIn": expires_in}).encode("ascii"))
        try:
            value = json.loads(raw)
            signed_path = value["signedURL"]
            expected = "/object/sign/" + BUCKET_NAME + "/" + key + "?token="
            if (not isinstance(signed_path, str) or not signed_path.startswith(expected)
                    or any(ch.isspace() for ch in signed_path)):
                raise ValueError("URL inválida")
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
            raise AuthServiceUnavailable("Link de download inválido") from exc
        return self.base_url + signed_path
