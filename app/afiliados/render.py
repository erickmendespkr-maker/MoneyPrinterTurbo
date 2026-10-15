"""Offline MP4 rendering from user-provided photos and optional audio.

No downloads, shell=True, subprocess calls, external providers or billing.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_IMAGES = 8


def normalize_photo(data: bytes, target: tuple[int, int] = (720, 1280)) -> Image.Image:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Imagem vazia ou acima de 12 MB")
    try:
        with Image.open(io.BytesIO(data)) as src:
            if src.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Use JPEG, PNG ou WEBP")
            if src.width * src.height > 30_000_000:
                raise ValueError("Imagem grande demais")
            src.load()
            photo = ImageOps.exif_transpose(src).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Arquivo de imagem inválido ou não suportado") from exc
    canvas = Image.new("RGB", target, (20, 20, 20))
    contained = ImageOps.contain(photo, target, method=Image.Resampling.LANCZOS)
    canvas.paste(contained, ((target[0] - contained.width) // 2, (target[1] - contained.height) // 2))
    return canvas


def render_mp4(
    images: list[bytes],
    duration: int,
    script: str,
    audio: bytes | None = None,
    audio_extension: str = ".mp3",
) -> bytes:
    """Render a vertical slideshow. Audio is optional; generation is local only."""
    if not (1 <= len(images) <= MAX_IMAGES):
        raise ValueError("Envie de 1 a 8 imagens")
    if duration not in (15, 20, 30):
        raise ValueError("Duração inválida")
    if len(script) > 1400:
        raise ValueError("Roteiro longo demais")
    if audio is not None and (not audio or len(audio) > MAX_AUDIO_BYTES):
        raise ValueError("Áudio inválido ou acima de 25 MB")
    if audio is not None and audio_extension not in (".mp3", ".wav", ".m4a"):
        raise ValueError("Formato de áudio não suportado")

    # Lazy imports avoid loading video engines while editing a product brief.
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

    with tempfile.TemporaryDirectory(prefix="mpt-affiliate-") as temp:
        directory = Path(temp)
        paths = []
        for index, data in enumerate(images):
            photo = normalize_photo(data)
            path = directory / f"photo-{index}.png"
            photo.save(path)
            paths.append(path)
        seconds = duration / len(paths)
        clips = [ImageClip(str(path)).with_duration(seconds) for path in paths]
        video = concatenate_videoclips(clips, method="chain")
        audio_clip = None
        try:
            if audio is not None:
                audio_path = directory / ("narration" + audio_extension)
                audio_path.write_bytes(audio)
                audio_clip = AudioFileClip(str(audio_path))
                video = video.with_audio(audio_clip.subclipped(0, min(duration, audio_clip.duration)))
            output = directory / "afiliados.mp4"
            video.write_videofile(
                str(output),
                fps=24,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                threads=2,
                logger=None,
            )
            return output.read_bytes()
        finally:
            video.close()
            for clip in clips:
                clip.close()
            if audio_clip is not None:
                audio_clip.close()
