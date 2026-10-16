from unittest.mock import MagicMock, patch
import pytest
from app.services.afiliados_shopee_ids import shopee_product_ids
from app.services.afiliados_shopee_lookup import lookup_shopee_product
from app.services.afiliados_product_importer import ProductLinkPreview

@pytest.mark.parametrize("url,expected", [
    ("https://shopee.com.br/product/123/456", (123,456)),
    ("https://shopee.com.br/example-i.123.456", (123,456)),
    ("https://shopee.com.br/a?shopid=123&itemid=456", (123,456)),
    ("https://s.shopee.com.br/60SPo2qmRw", None),
])
def test_ids(url, expected):
    assert shopee_product_ids(url) == expected

def test_shortlink_resolves_and_queries_api():
    url = "https://s.shopee.com.br/60SPo2qmRw"
    preview = ProductLinkPreview(platform="shopee", original_url=url,
        resolved_url="https://shopee.com.br/product/123/456")
    api = MagicMock()
    api.product_offer.return_value = {"itemId":456, "shopId":123, "productName":"Produto",
        "imageUrl":"https://cf.shopee.com.br/photo.jpg", "priceMin":"19.90"}
    with patch("app.services.afiliados_shopee_lookup.preview_product_link", return_value=preview):
        result = lookup_shopee_product(url, api)
    assert result["status"] == "product_found"
    assert result["title"] == "Produto"
    api.product_offer.assert_called_once_with(item_id=456, shop_id=123)

def test_unresolved_shortlink_does_not_guess_ids():
    url = "https://s.shopee.com.br/60SPo2qmRw"
    preview = ProductLinkPreview(platform="shopee", original_url=url, resolved_url=url)
    api = MagicMock()
    with patch("app.services.afiliados_shopee_lookup.preview_product_link", return_value=preview):
        result = lookup_shopee_product(url, api)
    assert result["status"] == "shortlink_unresolved"
    api.product_offer.assert_not_called()
