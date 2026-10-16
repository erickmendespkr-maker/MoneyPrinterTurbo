"""Private Shopee integration diagnostic for Render shell / trusted CI.

Usage:
    python -m app.services.afiliados_shopee_diagnostic https://s.shopee.com.br/...
Prints no credentials and performs no storage writes or video generation.
"""
import json
import os
import sys

from app.services.afiliados_shopee_api import ShopeeAffiliateClient, ShopeeAffiliateError
from app.services.afiliados_shopee_lookup import lookup_shopee_product


def diagnostic(url: str, client=None) -> dict:
    if not os.environ.get("SHOPEE_AFFILIATE_APP_ID") or not os.environ.get("SHOPEE_AFFILIATE_SECRET"):
        return {"status": "credentials_missing", "message": "Configure as credenciais Shopee no backend."}
    try:
        result = lookup_shopee_product(url, client or ShopeeAffiliateClient.from_env())
    except (ValueError, ShopeeAffiliateError) as exc:
        return {"status": "lookup_failed", "error_type": type(exc).__name__}
    except Exception as exc:
        return {"status": "request_failed", "error_type": type(exc).__name__}
    return {
        "status": result["status"],
        "shop_id": result.get("shop_id"),
        "item_id": result.get("item_id"),
        "has_title": bool(result.get("title")),
        "has_image": bool(result.get("image_url")),
        "has_affiliate_url": bool(result.get("affiliate_url")),
    }


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Uso: python -m app.services.afiliados_shopee_diagnostic URL")
        return 2
    result = diagnostic(args[0])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "product_found" else 1


if __name__ == "__main__":
    raise SystemExit(main())
