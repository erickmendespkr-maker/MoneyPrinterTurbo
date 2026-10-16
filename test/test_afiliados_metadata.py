import pytest
from app.afiliados.metadata import extract_product_metadata


def test_jsonld_product_takes_priority():
    html = '''<meta property="og:title" content="Outro nome">
    <script type="application/ld+json">{"@graph":[{"@type":"Product","name":"Aspirador portátil","description":"Compacto e leve","image":"https://example.org/photo.png"}]}</script>'''
    result = extract_product_metadata(html)
    assert result["name"] == "Aspirador portátil"
    assert result["description"] == "Compacto e leve"
    assert result["image_url"] == "https://example.org/photo.png"


def test_opengraph_fallback_and_no_download():
    result = extract_product_metadata('<meta property="og:title" content="Produto &amp; Oferta"><meta property="og:image" content="http://example.com/a.png">')
    assert result["name"] == "Produto & Oferta"
    assert "image_url" not in result


@pytest.mark.parametrize("data", ["", "x" * 2_000_001, None])
def test_invalid_html(data):
    with pytest.raises(ValueError):
        extract_product_metadata(data)


def test_malformed_jsonld_ignored():
    assert extract_product_metadata('<script type="application/ld+json">{bad}</script><meta property="og:title" content="Copo">')["name"] == "Copo"
