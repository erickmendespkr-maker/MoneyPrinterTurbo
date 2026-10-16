"""Server-side render boundary enforcing trusted entitlements and quotas.

This is a backend component, NOT a public HTTP endpoint. Real deployment needs
an authenticated job queue, bounded worker memory and durable media storage.
Clients must never supply their own plan, watermark entitlement or owner ID.
"""
from __future__ import annotations

import io
import zipfile

from app.afiliados.plans import get_plan_policy, require_feature
from app.afiliados.production_quota import SupabaseVideoQuota
from app.afiliados.render import MAX_IMAGES, VIDEO_VARIANTS


class ProductionGeneration:
    def __init__(self, quotas: SupabaseVideoQuota):
        if not isinstance(quotas, SupabaseVideoQuota):
            raise ValueError("Controle de cota inválido")
        self.quotas = quotas

    @staticmethod
    def _video_ok(data: object) -> bool:
        return (isinstance(data, bytes) and 12 <= len(data) <= 100 * 1024 * 1024
                and data[4:8] == b"ftyp")

    def render_one(
        self, access_token: str, images: list[bytes], duration: int, script: str,
        audio: bytes | None = None, audio_extension: str = ".mp3",
        variant: str = "impacto", *, renderer=None,
    ) -> bytes:
        plan = self.quotas.plan(access_token)
        policy = get_plan_policy(plan)
        if variant not in VIDEO_VARIANTS or (policy.videos_per_ad == 1 and variant != "impacto"):
            raise PermissionError("Versão de vídeo indisponível neste plano")
        if not isinstance(images, list) or not 1 <= len(images) <= MAX_IMAGES:
            raise ValueError("Quantidade de imagens inválida")
        # Trust only the plan returned by the server-side subscription RPC.
        reservation = self.quotas.reserve(access_token)
        try:
            if renderer is None:
                from app.afiliados.render import render_mp4
                renderer = render_mp4
            mp4 = renderer(
                images, duration, script, audio, audio_extension,
                watermark=policy.platform_watermark_required, variant=variant,
            )
            if not self._video_ok(mp4):
                raise ValueError("MP4 gerado inválido")
            self.quotas.complete(access_token, reservation)
        except Exception:
            try:
                self.quotas.release(access_token, reservation)
            except Exception:
                # Original failure remains visible; a reconciler must release
                # orphaned reservations if the database/network is unavailable.
                pass
            raise
        return mp4

    def render_bundle(
        self, access_token: str, images: list[bytes], product_name: str,
        duration: int, script: str, audio: bytes | None = None,
        audio_extension: str = ".mp3", *, bundler=None,
    ) -> bytes:
        plan = self.quotas.plan(access_token)
        require_feature(plan, "campaign")
        policy = get_plan_policy(plan)
        if not isinstance(images, list) or not 1 <= len(images) <= MAX_IMAGES:
            raise ValueError("Quantidade de imagens inválida")
        reservation = self.quotas.reserve(access_token, count=3)
        try:
            if bundler is None:
                from app.afiliados.campaign import build_campaign
                bundler = build_campaign
            archive = bundler(
                images, product_name, duration, script, audio, audio_extension,
                watermark=policy.platform_watermark_required, plan=plan,
            )
            if (not isinstance(archive, bytes) or not 1 <= len(archive) <= 350 * 1024 * 1024
                    or not zipfile.is_zipfile(io.BytesIO(archive))):
                raise ValueError("Pacote de vídeos inválido")
            self.quotas.complete(access_token, reservation)
        except Exception:
            try:
                self.quotas.release(access_token, reservation)
            except Exception:
                pass
            raise
        return archive
