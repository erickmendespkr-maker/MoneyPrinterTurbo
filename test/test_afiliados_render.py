from io import BytesIO

import pytest
from PIL import Image

from app.afiliados.render import normalize_photo, render_mp4


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
