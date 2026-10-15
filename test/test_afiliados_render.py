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


@pytest.mark.parametrize("script", [None, "x" * 1401])
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
