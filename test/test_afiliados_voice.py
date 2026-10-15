import pytest

from app.afiliados.voice import VOICE_IDS, synthesize_voice


@pytest.mark.asyncio
async def test_voice_rejects_empty_script():
    with pytest.raises(ValueError):
        await synthesize_voice("")


@pytest.mark.asyncio
async def test_voice_rejects_invalid_voice():
    with pytest.raises(ValueError):
        await synthesize_voice("Texto", "desconhecida")


def test_voice_allowlist():
    assert VOICE_IDS["feminina"].startswith("pt-BR-")
    assert VOICE_IDS["masculina"].startswith("pt-BR-")
