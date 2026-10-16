"""Offline tests: no network or marketplace credentials."""
from unittest.mock import MagicMock, patch
import pytest
from app.services.afiliados_product_importer import preview_product_link

PUBLIC_DNS = [(None, None, None, None, ("104.18.1.1", 443))]

def test_shopee_open_graph_preview():
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.iter_content.return_value = [
        b'<html><meta property="og:title" content="Mini aspirador portatil">'
        b'<meta property="og:description" content="Produto de teste">'
        b'<meta property="og:image" content="https://cf.shopee.com.br/item.jpg"></html>'
    ]
    client = MagicMock()
    client.get.return_value = response
    with patch("app.services.afiliados_product_importer.socket.getaddrinfo", return_value=PUBLIC_DNS):
        result = preview_product_link("https://s.shopee.com.br/abc", session=client)
    assert result.platform == "shopee"
    assert result.title == "Mini aspirador portatil"
    assert result.status == "metadata_found"
    assert result.image_url == "https://cf.shopee.com.br/item.jpg"
    response.close.assert_called_once()

@pytest.mark.parametrize("url", [
    "http://shopee.com.br/item", "https://localhost/test",
    "https://evil.example/shopee.com.br",
    "https://shopee.com.br.evil.example/item",
    "https://user:password@shopee.com.br/item",
])
def test_reject_unsafe_links(url):
    with pytest.raises(ValueError):
        preview_product_link(url)

def test_reject_redirect_to_untrusted_domain():
    response = MagicMock()
    response.status_code = 302
    response.headers = {"Location": "https://example.com/private"}
    client = MagicMock()
    client.get.return_value = response
    with patch("app.services.afiliados_product_importer.socket.getaddrinfo", return_value=PUBLIC_DNS):
        with pytest.raises(ValueError):
            preview_product_link("https://s.shopee.com.br/abc", session=client)
    assert client.get.call_count == 1

def test_nonpublic_dns_rejected():
    with patch("app.services.afiliados_product_importer.socket.getaddrinfo",
               return_value=[(None,None,None,None,("127.0.0.1",443))]):
        with pytest.raises(ValueError):
            preview_product_link("https://shopee.com.br/item")
