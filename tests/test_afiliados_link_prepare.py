from unittest.mock import MagicMock, patch
from uuid import uuid4
from app.services.afiliados_link_prepare import prepare_product_from_link
from app.services.afiliados_product_importer import ProductLinkPreview

def test_prepares_reviewable_draft_with_private_image():
    uid = str(uuid4())
    preview = ProductLinkPreview(
        platform="shopee", original_url="https://s.shopee.com.br/example",
        resolved_url="https://shopee.com.br/item", title="Produto de teste",
        image_url="https://cf.shopee.com.br/item.jpg", status="metadata_found",
    )
    with (
        patch("app.services.afiliados_link_prepare.preview_product_link", return_value=preview),
        patch("app.services.afiliados_link_prepare.store_preview_image", return_value=uid + "/photo.jpg"),
    ):
        result = prepare_product_from_link(MagicMock(), uid, preview.original_url)
    assert result["status"] == "ready_for_review"
    assert result["source"]["mode"] == "both"
    assert result["source"]["image_paths"] == [uid + "/photo.jpg"]
    assert result["source"]["product_url"] == preview.resolved_url

def test_missing_image_requires_manual_upload():
    uid = str(uuid4())
    preview = ProductLinkPreview(
        platform="shopee", original_url="https://shopee.com.br/item",
        resolved_url="https://shopee.com.br/item", title="Produto",
    )
    with patch("app.services.afiliados_link_prepare.preview_product_link", return_value=preview):
        result = prepare_product_from_link(MagicMock(), uid, preview.original_url)
    assert result["status"] == "manual_images_required"
    assert result["source"] is None

def test_authenticated_shopee_api_photo_preferred():
    uid = str(uuid4())
    url = "https://s.shopee.com.br/60SPo2qmRw"
    api_result = {
        "status": "product_found", "resolved_url": "https://shopee.com.br/product/123/456",
        "title": "Produto da API", "image_url": "https://cf.shopee.com.br/real.jpg",
    }
    with (
        patch("app.services.afiliados_link_prepare.lookup_shopee_product", return_value=api_result) as lookup,
        patch("app.services.afiliados_link_prepare.store_preview_image", return_value=uid + "/api.jpg"),
        patch("app.services.afiliados_link_prepare.preview_product_link") as html_preview,
    ):
        result = prepare_product_from_link(MagicMock(), uid, url, shopee_api=MagicMock())
    assert result["status"] == "ready_for_review"
    assert result["product_name"] == "Produto da API"
    assert result["source"]["image_paths"] == [uid + "/api.jpg"]
    lookup.assert_called_once()
    html_preview.assert_not_called()

def test_shopee_api_failure_uses_public_metadata_fallback():
    from app.services.afiliados_shopee_api import ShopeeAffiliateError
    uid = str(uuid4())
    url = "https://s.shopee.com.br/60SPo2qmRw"
    preview = ProductLinkPreview(platform="shopee", original_url=url,
        resolved_url="https://shopee.com.br/product/123/456",
        title="Produto real", image_url="https://cf.shopee.com.br/real.jpg")
    with (
        patch("app.services.afiliados_link_prepare.lookup_shopee_product",
              side_effect=ShopeeAffiliateError("API rejected request")),
        patch("app.services.afiliados_link_prepare.preview_product_link", return_value=preview),
        patch("app.services.afiliados_link_prepare.store_preview_image", return_value=uid + "/photo.jpg"),
    ):
        result = prepare_product_from_link(MagicMock(), uid, url, shopee_api=MagicMock())
    assert result["status"] == "ready_for_review"
    assert result["product_name"] == "Produto real"
