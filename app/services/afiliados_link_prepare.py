"""Trusted-only link-to-owned-product-photo preparation.

Do not call from an unauthenticated UI. Service-role backend stays on server.
"""
from uuid import UUID
from app.services.afiliados_product_importer import preview_product_link
from app.services.afiliados_marketplace_images import store_preview_image

def prepare_product_from_link(backend, user_id: str, url: str) -> dict:
    UUID(user_id)
    preview = preview_product_link(url)
    if not preview.title or not preview.image_url:
        return {
            "status": "manual_images_required",
            "platform": preview.platform,
            "product_url": preview.original_url,
            "product_name": preview.title,
            "description": preview.description,
            "source": None,
        }
    try:
        path = store_preview_image(backend, user_id, preview.image_url)
    except (ValueError, OSError):
        return {
            "status": "manual_images_required",
            "platform": preview.platform,
            "product_url": preview.original_url,
            "product_name": preview.title,
            "description": preview.description,
            "source": None,
        }
    return {
        "status": "ready_for_review",
        "platform": preview.platform,
        "product_url": preview.original_url,
        "product_name": preview.title,
        "description": preview.description,
        "source": {"mode": "both", "product_url": preview.original_url, "image_paths": [path]},
    }
