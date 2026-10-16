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
