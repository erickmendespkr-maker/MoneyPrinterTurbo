"""Build a downloadable offline campaign: three MP4 videos and nine PNG covers.

Rendering is synchronous and CPU-intensive. This module does not invoke paid APIs.
"""
from __future__ import annotations

import io
import json
import zipfile

from app.afiliados.render import VIDEO_VARIANTS, MAX_IMAGES, normalize_photo, render_mp4
from app.afiliados.plans import require_feature
from app.afiliados.thumbnails import generate_thumbnails

MAX_BUNDLE_BYTES = 350 * 1024 * 1024


def build_campaign(
    images: list[bytes], product_name: str, duration: int, script: str,
    audio: bytes | None = None, audio_extension: str = ".mp3",
    watermark: bool = True,
    renderer=None,
    *, plan: str = "gratis",
) -> bytes:
    """Return ZIP with videos/<variant>.mp4 and covers/<variant>/<style>.png.

    Fail the whole package if any render fails; never label an incomplete ZIP
    as a successful three-video campaign.
    """
    require_feature(plan, "campaign")
    if not isinstance(images, list) or not (1 <= len(images) <= MAX_IMAGES):
        raise ValueError("Envie de 1 a 8 fotos reais")
    if not isinstance(product_name, str) or not product_name.strip() or len(product_name) > 140:
        raise ValueError("Nome do produto inválido")
    if type(watermark) is not bool:
        raise ValueError("Configuração de marca-d'água inválida")
    if type(duration) is not int or duration not in (15, 20, 30):
        raise ValueError("Duração inválida")
    if not isinstance(script, str) or not script.strip() or len(script) > 1400:
        raise ValueError("Roteiro inválido")
    # Validate all photos before rendering or creating any ZIP members.
    for image in images:
        normalize_photo(image)
    encode = render_mp4 if renderer is None else renderer
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_STORED) as archive:
        manifest = {"product_name": product_name, "duration": duration, "variants": {}}
        for index, variant in enumerate(VIDEO_VARIANTS):
            mp4 = encode(images, duration, script, audio, audio_extension,
                         watermark=watermark, variant=variant)
            if not isinstance(mp4, bytes) or not mp4 or len(mp4) > 100 * 1024 * 1024:
                raise ValueError("Vídeo gerado inválido ou acima de 100 MB")
            video_path = f"videos/{variant}.mp4"
            archive.writestr(video_path, mp4)
            # Rotate source photo for variety when multiple real photos exist.
            photo = images[index % len(images)]
            covers = generate_thumbnails(photo, product_name, watermark=watermark,
                                         video_variant=variant)
            manifest["variants"][variant] = {"video": video_path, "covers": []}
            for style, cover in covers.items():
                cover_path = f"covers/{variant}/{style}.png"
                archive.writestr(cover_path, cover)
                manifest["variants"][variant]["covers"].append(cover_path)
            if result.tell() > MAX_BUNDLE_BYTES:
                raise ValueError("Pacote de anúncios acima do limite")
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    if result.tell() > MAX_BUNDLE_BYTES:
        raise ValueError("Pacote de anúncios acima do limite")
    return result.getvalue()
