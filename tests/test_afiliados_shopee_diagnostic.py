from unittest.mock import patch, MagicMock
from app.services.afiliados_shopee_diagnostic import diagnostic

URL = "https://s.shopee.com.br/60SPo2qmRw"

def test_missing_credentials_does_not_call_api():
    with patch.dict("os.environ", {"SHOPEE_AFFILIATE_APP_ID": "", "SHOPEE_AFFILIATE_SECRET": ""}):
        assert diagnostic(URL)["status"] == "credentials_missing"

def test_found_product_only_reports_safe_fields():
    with patch.dict("os.environ", {"SHOPEE_AFFILIATE_APP_ID": "test", "SHOPEE_AFFILIATE_SECRET": "hidden"}):
        with patch("app.services.afiliados_shopee_diagnostic.lookup_shopee_product", return_value={
            "status": "product_found", "shop_id": 123, "item_id": 456,
            "title": "Produto", "image_url": "https://example.com/image",
            "affiliate_url": "https://example.com/link",
        }):
            result = diagnostic(URL, MagicMock())
    assert result["status"] == "product_found"
    assert result["has_image"] is True
    assert "hidden" not in str(result)
    assert "Produto" not in str(result)
