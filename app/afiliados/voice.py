"""Optional Brazilian Portuguese speech synthesis; no paid API credentials required.

Edge TTS uses Microsoft's online speech endpoint, so it is opt-in and NOT offline.
"""
from __future__ import annotations

import asyncio

VOICE_IDS = {
    "feminina": "pt-BR-FranciscaNeural",
    "masculina": "pt-BR-AntonioNeural",
}
MAX_SCRIPT_LENGTH = 1400
MAX_VOICE_BYTES = 25 * 1024 * 1024


async def synthesize_voice(script: str, voice: str = "feminina") -> bytes:
    """Generate MP3 narration, using only an allowlisted voice and bounded text."""
    if not isinstance(script, str) or not script.strip() or len(script) > MAX_SCRIPT_LENGTH:
        raise ValueError("Roteiro inválido para narração")
    if voice not in VOICE_IDS:
        raise ValueError("Voz não suportada")
    import edge_tts

    output = bytearray()
    communicator = edge_tts.Communicate(text=script.strip(), voice=VOICE_IDS[voice])
    async for chunk in communicator.stream():
        if chunk.get("type") == "audio":
            output.extend(chunk["data"])
            if len(output) > MAX_VOICE_BYTES:
                raise ValueError("Narração excede 25 MB")
    if not output:
        raise ValueError("O serviço de voz não retornou áudio")
    return bytes(output)


def generate_voice(script: str, voice: str = "feminina") -> bytes:
    """Sync entry point for Streamlit; never called without a user click."""
    return asyncio.run(synthesize_voice(script, voice))
