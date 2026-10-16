"""Authenticated submission and delivery facade for the queued video backend.

The facade does NOT expose service credentials or run CPU-intensive rendering
in the user's request. Workers complete jobs asynchronously.
"""
from __future__ import annotations

from uuid import uuid4

from app.afiliados.private_object_storage import PrivateObjectStorage
from app.afiliados.production_quota import RenderJobStatus, SupabaseVideoQuota
from app.afiliados.render_inputs import pack_inputs


class ProductionJobService:
    def __init__(self, quotas: SupabaseVideoQuota, storage: PrivateObjectStorage):
        if not isinstance(quotas, SupabaseVideoQuota) or not isinstance(storage, PrivateObjectStorage):
            raise ValueError("Provedores autenticados de cota e armazenamento obrigatórios")
        if quotas.auth is not storage.auth:
            raise ValueError("Provedores precisam compartilhar a autenticação")
        self.quotas = quotas
        self.storage = storage

    def submit(
        self, access_token: str, images: list[bytes], product_name: str,
        duration: int, script: str, audio: bytes | None = None,
        audio_extension: str = ".mp3", *, kind: str = "video",
        variant: str = "impacto",
    ) -> str:
        if kind not in ("video", "campaign") or variant not in (
                "impacto", "beneficio", "curiosidade"):
            raise ValueError("Tipo de anúncio inválido")
        # Reject known quota/plan violations BEFORE uploading costly media.
        # This is only a preflight: the enqueue RPC remains the atomic authority.
        from app.afiliados.plans import get_plan_policy, require_feature
        plan = self.quotas.plan(access_token)
        policy = get_plan_policy(plan)
        if kind == "campaign":
            require_feature(plan, "campaign")
            if variant != "impacto":
                raise PermissionError("Versão indisponível neste plano")
        elif variant != "impacto" and policy.videos_per_ad == 1:
            raise PermissionError("Versão indisponível neste plano")
        if plan == "gratis" and not self.quotas.free_status(access_token).can_generate:
            raise PermissionError("Aguarde a liberação da próxima geração gratuita")
        # Construct safe, bounded inputs *before* paying for network/storage.
        package = pack_inputs(images, product_name, duration, script, audio, audio_extension)
        job_id = str(uuid4())
        self.storage.stage_input(access_token, job_id, package)
        # Reserve credits and enqueue in one PostgreSQL transaction. Failure may
        # leave an unreferenced *private* input that a lifecycle cleaner removes.
        return self.quotas.enqueue_job(access_token, job_id, kind, variant)

    def status(self, access_token: str, job_id: str) -> RenderJobStatus:
        return self.quotas.job_status(access_token, job_id)

    def download_link(self, access_token: str, job_id: str) -> str:
        # The object store re-checks ownership via live job-status RPC.
        return self.storage.signed_result_url(access_token, job_id, self.quotas)
