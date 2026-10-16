"""Offline Shopee Affiliate API contract tests; never use real secrets."""
import hashlib
import json
from unittest.mock import MagicMock, patch
import pytest
from app.services.afiliados_shopee_api import ShopeeAffiliateClient, ShopeeAffiliateError, ENDPOINT

def test_signed_query_matches_exact_payload():
    response = MagicMock()
    response.json.return_value = {"data": {"productOfferV2": {"nodes": []}}}
    session = MagicMock()
    session.post.return_value = response
    client = ShopeeAffiliateClient("app123", "secret456", session=session)
    with patch("app.services.afiliados_shopee_api.time.time", return_value=1700000000):
        result = client.query("{ productOfferV2(limit: 1) { nodes { itemId } } }")
    assert result["productOfferV2"]["nodes"] == []
    args, kwargs = session.post.call_args
    assert args[0] == ENDPOINT
    body = kwargs["data"].decode("utf-8")
    expected = hashlib.sha256(("app1231700000000" + body + "secret456").encode()).hexdigest()
    assert kwargs["headers"]["Authorization"] == (
        f"SHA256 Credential=app123, Timestamp=1700000000, Signature={expected}"
    )
    assert json.loads(body)["query"].startswith("{ productOfferV2")

def test_product_offer_matches_requested_id():
    client = ShopeeAffiliateClient("id", "secret")
    with patch.object(client, "query", return_value={"productOfferV2": {"nodes": [
        {"itemId": 123, "shopId": 456, "productName": "Produto"}
    ]}}):
        assert client.product_offer(123, 456)["productName"] == "Produto"
        assert client.product_offer(124, 456) is None

def test_api_error_fails_closed():
    response = MagicMock()
    response.json.return_value = {"errors": [{"message": "Invalid Credential"}]}
    session = MagicMock()
    session.post.return_value = response
    with pytest.raises(ShopeeAffiliateError):
        ShopeeAffiliateClient("id", "secret", session=session).query("{ test }")
