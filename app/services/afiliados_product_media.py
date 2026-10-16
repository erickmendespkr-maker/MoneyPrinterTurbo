"""Download private, user-owned product photos into the worker's local media area.

Only trusted worker code calls this module. The service-role key never reaches
the browser. No arbitrary URLs, signed URLs or filesystem paths are accepted.
"""
from pathlib import Path
from uuid import UUID, uuid4
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from app.models.afiliados_product_source import ProductSource, validate_image_ownership

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

def validate_product_paths(payload: dict, user_id: str) -> list[str]:
    UUID(user_id)
    source = ProductSource.model_validate(payload)
    validate_image_ownership(source, user_id)
    if not source.image_paths:
        raise ValueError("Product photos are required for image-based rendering")
    return source.image_paths

def download_product_photos(backend, payload: dict, user_id: str, destination: Path) -> list[Path]:
    """Retrieve and normalize private images; reject malformed/oversized media."""
    paths = validate_product_paths(payload, user_id)
    destination.mkdir(parents=True, exist_ok=True)
    outputs = []
    try:
        for storage_path in paths:
            response = backend.session.get(
                f"{backend.url}/storage/v1/object/product-images/{storage_path}",
                stream=True,
                timeout=(10, 45),
            )
            response.raise_for_status()
            try:
                data = bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    data.extend(chunk)
                    if len(data) > MAX_IMAGE_BYTES:
                        raise ValueError("Product image exceeds 8 MiB")
            finally:
                response.close()
            try:
                with Image.open(BytesIO(data)) as img:
                    img.verify()
                with Image.open(BytesIO(data)) as img:
                    if img.width * img.height > MAX_IMAGE_PIXELS:
                        raise ValueError("Product image resolution too large")
                    normalized = ImageOps.exif_transpose(img).convert("RGB")
                    target = destination / f"{uuid4().hex}.jpg"
                    normalized.save(target, format="JPEG", quality=92)
                    outputs.append(target)
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise ValueError("Invalid product image") from exc
        return outputs
    except Exception:
        for item in outputs:
            item.unlink(missing_ok=True)
        raise
