"""Contract tests for Afiliados Creator parameter mapping.

Run: pytest tests/test_afiliados_render_params.py
"""
import pytest
from pydantic import ValidationError

from app.services.afiliados_render_params import build_video_params


@pytest.mark.parametrize("duration", [15, 20, 30])
def test_supported_durations(duration):
    params = build_video_params(
        {"product_name": "Mini aspirador portátil", "description": "Aspirador recarregável"},
        duration,
    )
    assert params.video_aspect.value == "9:16"
    assert params.video_language == "pt-BR"
    assert params.video_count == 1
    assert params.subtitle_enabled is True
    assert "Mini aspirador portátil" in params.video_subject
    assert str(duration) in params.video_script_prompt


@pytest.mark.parametrize("duration", [0, 10, 60, -1])
def test_invalid_duration(duration):
    with pytest.raises(ValueError):
        build_video_params({"product_name": "Produto teste"}, duration)


def test_reject_unknown_fields():
    with pytest.raises(ValidationError):
        build_video_params(
            {"product_name": "Produto teste", "custom_audio_file": "/etc/passwd"},
            15,
        )


def test_reject_unsupported_voice():
    with pytest.raises(ValidationError):
        build_video_params(
            {"product_name": "Produto teste", "voice": "arbitrary-voice"},
            15,
        )


def test_does_not_use_user_text_as_system_prompt():
    params = build_video_params(
        {"product_name": "Produto teste", "description": "Texto fornecido pelo vendedor"},
        15,
    )
    assert params.custom_system_prompt == ""
    assert params.custom_audio_file is None


def test_verified_product_photos_disable_stock_source():
    params = build_video_params(
        {"product_name": "Mini aspirador portátil"},
        15,
        ["/tmp/verified-product-photo.jpg"],
    )
    assert params.video_source == "local"
    assert len(params.video_materials) == 1
    assert params.video_materials[0].url == "/tmp/verified-product-photo.jpg"
