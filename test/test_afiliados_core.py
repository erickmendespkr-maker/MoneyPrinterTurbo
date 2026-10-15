import pytest

from app.afiliados.core import AffiliateBrief, make_openai_prompt, prepare_draft, validate_product_url


def test_valid_product():
    assert validate_product_url("https://shopee.com.br/example") == "https://shopee.com.br/example"


@pytest.mark.parametrize("url", [
    "http://shopee.com.br/x",
    "https://shopee.com.br.evil.test/x",
    "https://127.0.0.1/private",
    "file:///etc/passwd",
    "https://user:pass@shopee.com.br/x",
    "https://shopee.com.br:8443/x",
])
def test_unsafe_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_product_url(url)


def test_prompt_avoids_fabricated_claims():
    brief = AffiliateBrief("Potes", "https://shopee.com.br/potes", "Tampa hermética")
    prompt = make_openai_prompt(brief)
    assert "Não invente preço" in prompt["system"]
    assert "Tampa hermética" in prompt["user"]
    draft = prepare_draft(brief)
    assert draft["generation"]["kling_enabled"] is False
    assert draft["status"] == "aguardando_aprovacao"
