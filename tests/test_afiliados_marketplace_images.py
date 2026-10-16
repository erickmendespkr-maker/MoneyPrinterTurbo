"""Tests for marketplace image importer without external requests."""
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from PIL import Image
from app.services.afiliados_marketplace_images import validate_image_url, store_preview_image

PUBLIC_DNS = [(None, None, None, None, ("104.18.1.1", 443))]

@pytest.mark.parametrize("url", [
    "http://cf.shopee.com.br/photo.jpg",
    "https://example.com/photo.jpg",
    "https://cf.shopee.com.br.evil.test/photo.jpg",
    "https://cf.shopee.com.br:8443/photo.jpg",
    "https://user:pass@cf.shopee.com.br/photo.jpg",
])
def test_reject_untrusted_image_urls(url):
    with pytest.raises(ValueError):
        validate_image_url(url)

def test_reject_private_dns():
    with patch("app.services.afiliados_marketplace_images.socket.getaddrinfo",
               return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
        with pytest.raises(ValueError):
            validate_image_url("https://cf.shopee.com.br/photo.jpg")

def test_import_image_to_private_bucket():
    buf = BytesIO()
    Image.new("RGB", (200, 200), "blue").save(buf, "PNG")
    response = MagicMock()
    response.is_redirect = False
    response.headers = {"Content-Type": "image/png"}
    response.iter_content.return_value = [buf.getvalue()]
    backend = MagicMock()
    backend.url = "https://test.supabase.co"
    user_id = str(uuid4())
    with (
        patch("app.services.afiliados_marketplace_images.socket.getaddrinfo", return_value=PUBLIC_DNS),
        patch("app.services.afiliados_marketplace_images.requests.get", return_value=response),
    ):
        path = store_preview_image(backend, user_id, "https://cf.shopee.com.br/photo.jpg")
    assert path.startswith(user_id + "/")
    assert path.endswith(".jpg")
    assert "/storage/v1/object/product-images/" in backend.session.post.call_args.args[0]
    assert backend.session.post.call_args.kwargs["headers"]["Content-Type"] == "image/jpeg"
    response.close.assert_called_once()

def test_reject_image_redirect():
    response = MagicMock()
    response.is_redirect = True
    backend = MagicMock()
    with (
        patch("app.services.afiliados_marketplace_images.socket.getaddrinfo", return_value=PUBLIC_DNS),
        patch("app.services.afiliados_marketplace_images.requests.get", return_value=response),
    ):
        with pytest.raises(ValueError):
            store_preview_image(backend, str(uuid4()), "https://cf.shopee.com.br/photo.jpg")
    backend.session.post.assert_not_called()
