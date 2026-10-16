"""Translate a validated Afiliados Creator brief into MoneyPrinterTurbo parameters.

This mapper is deliberately independent of task execution. The underlying
pipeline does not guarantee exact final duration; output must be probed before
publishing. Product-specific media upload is not supported here yet.
"""
from app.models.afiliados_brief import ProductVideoBrief
from app.models.schema import VideoParams, VideoAspect


def build_video_params(brief_payload: dict, duration_seconds: int) -> VideoParams:
    if duration_seconds not in (15, 20, 30):
        raise ValueError("Unsupported duration")
    brief = ProductVideoBrief.model_validate({
        **brief_payload,
        "duration_seconds": duration_seconds,
    })
    # Never pass untrusted user text as a system prompt or local file path.
    subject = f"Vídeo curto de divulgação de produto: {brief.product_name}"
    context = brief.description or brief.product_name
    script_instruction = (
        "Crie um roteiro publicitário em português brasileiro, com afirmações "
        "verificáveis e sem inventar descontos, avaliações, estoque ou resultados. "
        f"Produto: {brief.product_name}. Informações fornecidas: {context}. "
        f"Tom: {brief.tone}. Chamada final: {brief.cta}. "
        f"Objetivo de duração: aproximadamente {duration_seconds} segundos. "
        "Não inclua alegações não verificadas."
    )[:2000]
    return VideoParams(
        video_subject=subject,
        video_aspect=VideoAspect.portrait,
        video_language="pt-BR",
        voice_name=brief.voice,
        video_source="pexels",
        video_count=1,
        video_clip_duration=5,
        video_script_prompt=script_instruction,
        subtitle_enabled=True,
        bgm_type="random",
        bgm_volume=0.12,
        n_threads=2,
    )
