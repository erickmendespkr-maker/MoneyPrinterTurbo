from app.services.afiliados_product_media import validate_product_paths


def test_reject_unowned_photo():
    owner = '11111111-1111-4111-8111-111111111111'
    source = {'mode': 'images', 'image_paths': ['22222222-2222-4222-8222-222222222222/photo.jpg']}
    try:
        validate_product_paths(source, owner)
    except ValueError:
        return
    raise AssertionError('foreign photo accepted')

from io import BytesIO
from unittest.mock import MagicMock
from pathlib import Path
from PIL import Image
from app.services.afiliados_product_media import download_product_photos

def test_photo_download_normalizes_png_to_jpeg(tmp_path: Path):
    image = Image.new("RGB", (128, 128), (200, 20, 20))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    backend = MagicMock()
    backend.url = "https://example.invalid"
    backend.session.get.return_value.iter_content.return_value = [buffer.getvalue()]
    owner = "11111111-1111-4111-8111-111111111111"
    result = download_product_photos(
        backend, {"mode": "images", "image_paths": [owner + "/photo.png"]},
        owner, tmp_path
    )
    assert len(result) == 1
    with Image.open(result[0]) as normalized:
        assert normalized.format == "JPEG"
        assert normalized.size == (128, 128)

def test_invalid_photo_rejected(tmp_path: Path):
    backend = MagicMock()
    backend.url = "https://example.invalid"
    backend.session.get.return_value.iter_content.return_value = [b"not an image"]
    owner = "11111111-1111-4111-8111-111111111111"
    try:
        download_product_photos(
            backend, {"mode": "images", "image_paths": [owner + "/photo.png"]},
            owner, tmp_path
        )
    except ValueError:
        assert not list(tmp_path.glob("*.jpg"))
        return
    raise AssertionError("invalid image accepted")
