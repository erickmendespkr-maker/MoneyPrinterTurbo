"""Restricted marketplace preview image importer (trusted worker only)."""
import ipaddress
import socket
from io import BytesIO
from urllib.parse import urlsplit
from uuid import UUID, uuid4
import requests
from PIL import Image, ImageOps

ALLOWED_IMAGE_HOSTS = frozenset({
    "cf.shopee.com.br", "down-br.img.susercontent.com", "http2.mlstatic.com",
})
MAX_IMAGE_BYTES = 8 * 1024 * 1024

def validate_image_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_IMAGE_HOSTS:
        raise ValueError("Unsupported marketplace image host")
    if parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("Unsafe marketplace image URL")
    addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("Image host DNS unavailable")
    if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Image host must resolve to public IP addresses")
    return url

def store_preview_image(backend, user_id: str, image_url: str) -> str:
    UUID(user_id)
    validate_image_url(image_url)
    response = requests.get(image_url, stream=True, allow_redirects=False, timeout=(5, 20))
    try:
        if response.is_redirect:
            raise ValueError("Image redirects are not allowed")
        response.raise_for_status()
        if response.headers.get("Content-Type", "").split(";")[0].lower() not in {
            "image/jpeg", "image/png", "image/webp",
        }:
            raise ValueError("Unexpected image content type")
        content = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            content.extend(chunk)
            if len(content) > MAX_IMAGE_BYTES:
                raise ValueError("Marketplace image too large")
    finally:
        response.close()
    with Image.open(BytesIO(content)) as img:
        img.verify()
    with Image.open(BytesIO(content)) as img:
        if img.width * img.height > 24_000_000:
            raise ValueError("Marketplace image resolution too large")
        normalized = ImageOps.exif_transpose(img).convert("RGB")
        output = BytesIO()
        normalized.save(output, format="JPEG", quality=90)
    key = f"{user_id}/{uuid4().hex}.jpg"
    upload = backend.session.post(
        f"{backend.url}/storage/v1/object/product-images/{key}",
        data=output.getvalue(),
        headers={"Content-Type": "image/jpeg", "x-upsert": "false"},
        timeout=45,
    )
    upload.raise_for_status()
    return key
