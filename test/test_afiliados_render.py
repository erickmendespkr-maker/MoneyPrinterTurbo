from io import BytesIO

import pytest
from PIL import Image

from app.afiliados.render import caption_segments, normalize_photo, overlay_caption, render_mp4


def test_photo_is_letterboxed_without_distortion():
    image = Image.new("RGB", (300, 200), "red")
    output = BytesIO()
    image.save(output, format="PNG")
    result = normalize_photo(output.getvalue(), target=(720, 1280))
    assert result.size == (720, 1280)
    assert result.getpixel((360, 640)) == (255, 0, 0)
    assert result.getpixel((0, 0)) == (20, 20, 20)


@pytest.mark.parametrize("payload", [b"", b"not-an-image", b"X" * (12 * 1024 * 1024 + 1)])
def test_invalid_image_rejected(payload):
    with pytest.raises(ValueError):
        normalize_photo(payload)


def test_renderer_rejects_missing_images():
    with pytest.raises(ValueError):
        render_mp4([], 15, "")


def test_caption_segments_preserve_words():
    script = "Potes de cozinha com tampa e vedação"
    captions = caption_segments(script, 3)
    assert " ".join(captions) == script


def test_overlay_caption_changes_pixels_without_resizing():
    original = Image.new("RGB", (720, 1280), "red")
    captioned = overlay_caption(original, "Produto real e prático")
    assert captioned.size == original.size
    assert captioned.getpixel((360, 1120)) != original.getpixel((360, 1120))
    assert original.getpixel((360, 1120)) == (255, 0, 0)


@pytest.mark.parametrize("script", [None, "", "  ", "x" * 1401])
def test_renderer_rejects_invalid_script(script):
    image = Image.new("RGB", (40, 40), "red")
    data = BytesIO()
    image.save(data, format="PNG")
    with pytest.raises(ValueError):
        render_mp4([data.getvalue()], 15, script)


def test_renderer_rejects_invalid_audio_without_invoking_encoder():
    image = Image.new("RGB", (40, 40), "red")
    data = BytesIO()
    image.save(data, format="PNG")
    with pytest.raises(ValueError):
        render_mp4([data.getvalue()], 15, "Teste", audio=b"")


@pytest.mark.parametrize("images,duration", [(None, 15), ([], 15), ([b"x"], True), ([b"x"], "15")])
def test_renderer_rejects_bad_argument_types(images, duration):
    with pytest.raises(ValueError):
        render_mp4(images, duration, "Teste")


def test_normalizer_rejects_non_bytes():
    with pytest.raises(ValueError):
        normalize_photo("not bytes")


def test_caption_with_unbroken_product_identifier_keeps_canvas_dimensions():
    photo = Image.new("RGB", (720, 1280), "white")
    output = overlay_caption(photo, "A" * 250)
    assert output.size == photo.size
    assert output.getpixel((360, 1100)) != (255, 255, 255)


def test_caption_with_many_words_does_not_crash():
    photo = Image.new("RGB", (720, 1280), "white")
    assert overlay_caption(photo, "produto " * 400).size == (720, 1280)


def test_real_mp4_smoke_when_explicitly_enabled(monkeypatch):
    """Opt-in full encoder check: requires ffmpeg and takes longer than unit tests."""
    import os
    if os.environ.get("AFILIADOS_MP4_SMOKE") != "1":
        pytest.skip("Defina AFILIADOS_MP4_SMOKE=1 para testar codificação MP4 real")
    import imageio_ffmpeg
    from moviepy import VideoFileClip
    imageio_ffmpeg.get_ffmpeg_exe()
    source = Image.new("RGB", (100, 100), "orange")
    payload = BytesIO()
    source.save(payload, format="PNG")
    video = render_mp4([payload.getvalue()], 15, "Conheça o produto. Confira o link na bio.")
    assert len(video) > 1000
    assert b"ftyp" in video[:64]
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp) / "smoke.mp4"
        target.write_bytes(video)
        with VideoFileClip(str(target)) as clip:
            assert clip.size == [720, 1280]
            assert abs(clip.duration - 15) < 0.2


def test_renderer_rejects_corrupt_second_photo_before_encoding(monkeypatch):
    """Never invoke MoviePy/ffmpeg after a later image fails validation."""
    import sys
    image = Image.new("RGB", (40, 40), "red")
    data = BytesIO()
    image.save(data, format="PNG")
    monkeypatch.setitem(sys.modules, "moviepy", None)
    with pytest.raises(ValueError, match="imagem inválido|imagem vazia|imagem inválida|Arquivo de imagem"):
        render_mp4([data.getvalue(), b"corrupt"], 15, "Roteiro válido")


def test_renderer_rejects_too_many_images_without_encoding():
    with pytest.raises(ValueError, match="1 a 8"):
        render_mp4([b"x"] * 9, 15, "Roteiro válido")


@pytest.mark.parametrize("extension", [".exe", ".ogg", "../file.mp3", ".MP3"])
def test_renderer_rejects_unsupported_audio_extension(extension):
    image = Image.new("RGB", (40, 40), "red")
    data = BytesIO()
    image.save(data, format="PNG")
    with pytest.raises(ValueError, match="Formato de áudio"):
        render_mp4([data.getvalue()], 15, "Teste", audio=b"audio", audio_extension=extension)


@pytest.mark.parametrize("duration", [0, 10, 31, -15, 15.0])
def test_renderer_rejects_unsupported_duration(duration):
    with pytest.raises(ValueError, match="Duração inválida"):
        render_mp4([b"placeholder"], duration, "Roteiro válido")


def test_long_caption_preserves_last_call_to_action(monkeypatch):
    from PIL import ImageDraw
    drawn = []
    original = ImageDraw.ImageDraw.text

    def recording_text(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", recording_text)
    photo = Image.new("RGB", (720, 1280), "white")
    overlay_caption(photo, ("benefício " * 150) + 'Comente "EU QUERO"')
    assert any("EU QUERO" in text for text in drawn)
    assert drawn[0] == "…"


@pytest.mark.parametrize("target", [(0, 1280), (720, 5000), (-1, 20), (True, 100), (720.0, 1280), [720, 1280]])
def test_normalizer_rejects_invalid_target_dimensions(target):
    with pytest.raises(ValueError, match="Dimensões"):
        normalize_photo(b"placeholder", target=target)


def test_caption_rejects_tiny_canvas():
    with pytest.raises(ValueError, match="pequena demais"):
        overlay_caption(Image.new("RGB", (64, 64), "white"), "Teste")


@pytest.mark.parametrize("extension,payload", [
    (".mp3", b"not an mp3"),
    (".wav", b"RIFF" + b"0" * 8),
    (".m4a", b"not an m4a"),
])
def test_renderer_rejects_bad_audio_magic_before_encoding(extension, payload, monkeypatch):
    import sys
    image = Image.new("RGB", (40, 40), "red")
    data = BytesIO()
    image.save(data, format="PNG")
    monkeypatch.setitem(sys.modules, "moviepy", None)
    with pytest.raises(ValueError, match="Arquivo .* inválido"):
        render_mp4([data.getvalue()], 15, "Roteiro válido", audio=payload, audio_extension=extension)


@pytest.mark.parametrize("script", [None, 15, ["texto"]])
def test_caption_segments_rejects_non_text(script):
    with pytest.raises(ValueError, match="Roteiro inválido"):
        caption_segments(script, 2)


@pytest.mark.parametrize("caption", [None, 10, ["teste"]])
def test_overlay_rejects_non_string_caption(caption):
    with pytest.raises(ValueError, match="Legenda inválida"):
        overlay_caption(Image.new("RGB", (720, 1280), "white"), caption)


@pytest.mark.parametrize("count", [None, True, 2.5, "2", 0, 9])
def test_caption_segments_rejects_bad_count(count):
    with pytest.raises(ValueError, match="Quantidade de slides inválida"):
        caption_segments("Roteiro", count)


@pytest.mark.parametrize("photo", [None, b"not a photo", "image"])
def test_overlay_rejects_non_image(photo):
    with pytest.raises(ValueError, match="Imagem inválida para legenda"):
        overlay_caption(photo, "Teste")


@pytest.mark.parametrize("variant", ["impacto", "beneficio", "curiosidade"])
def test_video_variant_changes_caption_position(variant):
    from app.afiliados.render import VIDEO_VARIANTS
    assert variant in VIDEO_VARIANTS
    photo = Image.new("RGB", (720, 1280), "white")
    rendered = overlay_caption(photo, "Produto real", variant=variant)
    assert rendered.size == photo.size
    assert rendered.tobytes() != photo.tobytes()


def test_video_variants_have_distinct_compositions():
    photo = Image.new("RGB", (720, 1280), "white")
    variants = [overlay_caption(photo, "Produto real", variant=v).tobytes()
                for v in ("impacto", "beneficio", "curiosidade")]
    assert len(set(variants)) == 3


def test_video_variant_rejects_invalid_value_before_encoding():
    with pytest.raises(ValueError, match="Variação"):
        render_mp4([b"invalid"], 15, "Roteiro", variant="unknown")
