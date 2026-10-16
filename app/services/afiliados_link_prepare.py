"""Trusted-only link-to-owned-product-photo preparation.

Do not call from an unauthenticated UI. Service-role backend stays on server.
"""
from uuid import UUID
from app.services.afiliados_product_importer import preview_product_link
from app.services.afiliados_marketplace_images import store_preview_image
from app.services.afiliados_shopee_lookup import lookup_shopee_product
from app.services.afiliados_product_importer import _platform

def prepare_product_from_link(backend, user_id: str, url: str, shopee_api=None) -> dict:
    UUID(user_id)
    platform = _platform(url)
    if platform == 'shopee' and shopee_api is not None:
        api_result = lookup_shopee_product(url, shopee_api)
        if api_result['status'] == 'product_found' and api_result.get('image_url'):
            try:
                path = store_preview_image(backend, user_id, api_result['image_url'])
            except (ValueError, OSError):
                pass
            else:
                return {
                    'status': 'ready_for_review', 'platform': 'shopee',
                    'product_url': api_result['resolved_url'],
                    'product_name': api_result['title'], 'description': None,
                    'source': {'mode': 'both', 'product_url': api_result['resolved_url'], 'image_paths': [path]},
                }
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
