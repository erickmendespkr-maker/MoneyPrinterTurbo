"""Shopee Brazil Affiliate GraphQL API client (trusted backend only).

Credentials must be injected through environment variables. This module
does not use browser sessions or consumer account passwords.
"""
import hashlib
import json
import os
import time
import requests

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"

class ShopeeAffiliateError(RuntimeError):
    pass

class ShopeeAffiliateClient:
    def __init__(self, app_id: str, secret: str, session=None):
        if not app_id or not secret:
            raise ValueError("Shopee Affiliate API credentials required")
        self.app_id = str(app_id)
        self.secret = str(secret)
        self.session = session or requests.Session()

    @classmethod
    def from_env(cls):
        return cls(os.environ["SHOPEE_AFFILIATE_APP_ID"],
                   os.environ["SHOPEE_AFFILIATE_SECRET"])

    def query(self, query: str, variables: dict | None = None) -> dict:
        payload = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        timestamp = str(int(time.time()))
        signature = hashlib.sha256(
            (self.app_id + timestamp + body + self.secret).encode("utf-8")
        ).hexdigest()
        authorization = (
            f"SHA256 Credential={self.app_id}, Timestamp={timestamp}, Signature={signature}"
        )
        response = self.session.post(
            ENDPOINT, data=body.encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": authorization},
            timeout=(10, 30),
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("errors"):
            raise ShopeeAffiliateError("Shopee Affiliate API rejected the request")
        return result.get("data") or {}

    def product_offer(self, item_id: int, shop_id: int | None = None) -> dict | None:
        if item_id <= 0 or (shop_id is not None and shop_id <= 0):
            raise ValueError("Invalid Shopee item or shop ID")
        arguments = f"itemId: {int(item_id)}, limit: 1"
        if shop_id is not None:
            arguments += f", shopId: {int(shop_id)}"
        data = self.query(
            "{ productOfferV2(" + arguments + ") { nodes { "
            "itemId shopId productName productLink offerLink imageUrl "
            "priceMin priceMax priceDiscountRate commissionRate "
            "} } }"
        )
        nodes = (data.get("productOfferV2") or {}).get("nodes") or []
        for node in nodes:
            if str(node.get("itemId")) == str(item_id) and (
                shop_id is None or str(node.get("shopId")) == str(shop_id)
            ):
                return node
        return None
