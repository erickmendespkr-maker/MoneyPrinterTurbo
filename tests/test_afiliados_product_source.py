import pytest
from pydantic import ValidationError
from app.models.afiliados_product_source import ProductSource, validate_image_ownership

UID = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"

def test_link_mode():
    source = ProductSource(mode="link", product_url="https://s.shopee.com.br/2gBxBxjFFB")
    assert source.image_paths == []

def test_images_mode():
    source = ProductSource(mode="images", image_paths=[f"{UID}/item.jpg"])
    validate_image_ownership(source, UID)

def test_both_mode():
    source = ProductSource(mode="both", product_url="https://example.com/item", image_paths=[f"{UID}/item.webp"])
    validate_image_ownership(source, UID)

@pytest.mark.parametrize("url", ["http://example.com", "file:///etc/passwd", "https://user:pass@example.com"])
def test_reject_unsafe_url(url):
    with pytest.raises(ValidationError):
        ProductSource(mode="link", product_url=url)

def test_reject_foreign_image():
    source = ProductSource(mode="images", image_paths=[f"{UID}/item.png"])
    with pytest.raises(ValueError):
        validate_image_ownership(source, "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")

def test_reject_path_traversal():
    with pytest.raises(ValidationError):
        ProductSource(mode="images", image_paths=[f"{UID}/../secret.jpg"])
