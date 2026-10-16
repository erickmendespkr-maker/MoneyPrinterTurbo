"""Shopee API-first product import; no service credentials in the UI."""
from app.services.afiliados_product_importer import preview_product_link
from app.services.afiliados_shopee_ids import shopee_product_ids

def lookup_shopee_product(url: str, api) -> dict:
    ids = shopee_product_ids(url)
    resolved_url = url
    if ids is None:
        try:
            preview = preview_product_link(url)
        except (ValueError, OSError):
            preview = None
        if preview is not None:
            resolved_url = preview.resolved_url
            ids = shopee_product_ids(resolved_url)
    if ids is None:
        return {
            "status": "shortlink_unresolved",
            "original_url": url,
            "resolved_url": resolved_url,
            "message": "Não foi possível identificar o produto pelo link. Envie o link completo ou as fotos.",
        }
    shop_id, item_id = ids
    offer = api.product_offer(item_id=item_id, shop_id=shop_id)
    if not offer:
        return {
            "status": "product_not_in_affiliate_api",
            "original_url": url,
            "resolved_url": resolved_url,
            "shop_id": shop_id,
            "item_id": item_id,
        }
    return {
        "status": "product_found",
        "original_url": url,
        "resolved_url": resolved_url,
        "shop_id": shop_id,
        "item_id": item_id,
        "title": offer.get("productName"),
        "image_url": offer.get("imageUrl"),
        "price_min": offer.get("priceMin"),
        "price_max": offer.get("priceMax"),
        "affiliate_url": offer.get("offerLink") or url,
    }
