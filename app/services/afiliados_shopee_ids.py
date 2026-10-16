"""Extract marketplace item/shop identifiers from validated Shopee product URLs.

Short affiliate URLs must first be resolved through an approved redirect
resolver. A short code alone is not an item ID.
"""
import re
from urllib.parse import urlsplit, parse_qs
from app.services.afiliados_product_importer import _platform

def shopee_product_ids(url: str) -> tuple[int, int] | None:
    if _platform(url) != "shopee":
        raise ValueError("Shopee URL required")
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if host == "s.shopee.com.br":
        return None
    path = parsed.path
    for pattern in (r"/product/(\d+)/(\d+)(?:/|$)", r"-i\.(\d+)\.(\d+)(?:/|$)"):
        match = re.search(pattern, path)
        if match:
            return int(match.group(1)), int(match.group(2))
    query = parse_qs(parsed.query)
    shop = query.get("shopid", query.get("shop_id", []))
    item = query.get("itemid", query.get("item_id", []))
    if shop and item and shop[0].isdigit() and item[0].isdigit():
        return int(shop[0]), int(item[0])
    return None
