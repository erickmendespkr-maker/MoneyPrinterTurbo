"""Strict, portable render-input packages for the asynchronous worker.

Input archives carry product media and approved copy ONLY. They never contain
identity, plan, watermark or quota fields. Those come from the job ledger.
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass

from app.afiliados.render import MAX_IMAGE_BYTES, MAX_AUDIO_BYTES, MAX_IMAGES

MAX_BUNDLE_INPUT_BYTES = MAX_IMAGES * MAX_IMAGE_BYTES + MAX_AUDIO_BYTES + 64 * 1024
MAX_MANIFEST_BYTES = 16 * 1024
ALLOWED_AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a")


@dataclass(frozen=True)
class RenderInputs:
    images: list[bytes]
    product_name: str
    duration: int
    script: str
    audio: bytes | None
    audio_extension: str


def _validate_inputs(images, product_name, duration, script, audio, audio_extension):
    if (not isinstance(images, list) or not 1 <= len(images) <= MAX_IMAGES
            or any(not isinstance(x, bytes) or not x or len(x) > MAX_IMAGE_BYTES
                   for x in images)):
        raise ValueError("Fotos reais inválidas ou acima do limite")
    if not isinstance(product_name, str) or not 1 <= len(product_name.strip()) <= 140:
        raise ValueError("Nome do produto inválido")
    if type(duration) is not int or duration not in (15, 20, 30):
        raise ValueError("Duração inválida")
    if not isinstance(script, str) or not script.strip() or len(script) > 1400:
        raise ValueError("Roteiro inválido")
    if (audio is not None and (not isinstance(audio, bytes) or not audio
                               or len(audio) > MAX_AUDIO_BYTES)):
        raise ValueError("Áudio inválido ou acima do limite")
    if not isinstance(audio_extension, str) or audio_extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError("Extensão de áudio inválida")


def pack_inputs(
    images: list[bytes], product_name: str, duration: int, script: str,
    audio: bytes | None = None, audio_extension: str = ".mp3",
) -> bytes:
    """Package accepted media with fixed internal member names and size caps."""
    _validate_inputs(images, product_name, duration, script, audio, audio_extension)
    manifest = {
        "version": 1, "product_name": product_name.strip(),
        "duration": duration, "script": script.strip(),
        "photos": len(images),
        "audio_extension": audio_extension if audio is not None else None,
    }
    header = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(header) > MAX_MANIFEST_BYTES:
        raise ValueError("Metadados acima do limite")
    result = io.BytesIO()
    with zipfile.ZipFile(result, mode="w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", header)
        for idx, data in enumerate(images):
            archive.writestr(f"photos/{idx}.bin", data)
        if audio is not None:
            archive.writestr("audio.bin", audio)
    package = result.getvalue()
    if len(package) > MAX_BUNDLE_INPUT_BYTES:
        raise ValueError("Pacote acima do limite")
    return package


def unpack_inputs(package: bytes) -> RenderInputs:
    """Reject malformed ZIPs, duplicate paths, decompression bombs and extras."""
    if not isinstance(package, bytes) or not package or len(package) > MAX_BUNDLE_INPUT_BYTES:
        raise ValueError("Pacote de entrada inválido")
    try:
        with zipfile.ZipFile(io.BytesIO(package), mode="r") as archive:
            members = archive.infolist()
            if not 2 <= len(members) <= MAX_IMAGES + 2:
                raise ValueError("Quantidade de arquivos inválida")
            names = [item.filename for item in members]
            if (len(set(names)) != len(names)
                    or any(item.is_dir() or item.flag_bits & 1 or
                           item.compress_type != zipfile.ZIP_STORED for item in members)
                    or "manifest.json" not in names):
                raise ValueError("Arquivos do pacote inválidos")
            meta = archive.getinfo("manifest.json")
            if meta.file_size > MAX_MANIFEST_BYTES:
                raise ValueError("Metadados acima do limite")
            manifest = json.loads(archive.read("manifest.json", pwd=None))
            if (not isinstance(manifest, dict) or set(manifest) != {
                "version", "product_name", "duration", "script",
                "photos", "audio_extension",
            } or type(manifest["photos"]) is not int
                    or type(manifest["version"]) is not int
                    or manifest["version"] != 1
                    or not 1 <= manifest["photos"] <= MAX_IMAGES):
                raise ValueError("Manifesto de vídeo inválido")
            total = manifest["photos"]
            has_audio = manifest["audio_extension"] is not None
            expected = {"manifest.json"} | {
                f"photos/{i}.bin" for i in range(total)
            }
            if has_audio:
                expected.add("audio.bin")
            if set(names) != expected:
                raise ValueError("Arquivos inesperados no pacote")
            for item in members:
                limit = (MAX_MANIFEST_BYTES if item.filename == "manifest.json"
                         else MAX_AUDIO_BYTES if item.filename == "audio.bin"
                         else MAX_IMAGE_BYTES)
                if item.file_size < 1 or item.file_size > limit:
                    raise ValueError("Arquivo individual acima do limite")
            if sum(item.file_size for item in members) > MAX_BUNDLE_INPUT_BYTES:
                raise ValueError("Pacote excede o limite de leitura")
            photos = [archive.read(f"photos/{i}.bin") for i in range(total)]
            audio = archive.read("audio.bin") if has_audio else None
            _validate_inputs(
                photos, manifest["product_name"], manifest["duration"],
                manifest["script"], audio, manifest["audio_extension"] or ".mp3",
            )
            return RenderInputs(
                photos, manifest["product_name"], manifest["duration"],
                manifest["script"], audio, manifest["audio_extension"] or ".mp3",
            )
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError,
            RuntimeError, EOFError, OSError) as exc:
        raise ValueError("Pacote ZIP inválido ou danificado") from exc
