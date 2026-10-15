import pytest

from app.afiliados.voice import VOICE_IDS, synthesize_voice


def test_voice_rejects_empty_script():
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(synthesize_voice(""))


def test_voice_rejects_invalid_voice():
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(synthesize_voice("Texto", "desconhecida"))


def test_voice_allowlist():
    assert VOICE_IDS["feminina"].startswith("pt-BR-")
    assert VOICE_IDS["masculina"].startswith("pt-BR-")


def test_voice_rejects_non_string_selector():
    import asyncio
    with pytest.raises(ValueError):
        asyncio.run(synthesize_voice("Texto", []))
