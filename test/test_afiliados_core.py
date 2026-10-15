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
    "https://shopee.com.br:invalid/x",
    "https://shopee.com.br:999999/x",
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


def test_offline_script_is_created_without_api():
    brief = AffiliateBrief("Mini aspirador", "https://shopee.com.br/item", "Portátil e recarregável")
    draft = prepare_draft(brief)
    assert "Mini aspirador" in draft["script"]
    assert "Portátil e recarregável" in draft["script"]
    assert 'Comente "EU QUERO"' in draft["script"]
    assert draft["generation"]["openai_enabled"] is False


def test_manual_script_takes_priority():
    brief = AffiliateBrief("Potes", "https://shopee.com.br/item", "Com tampa")
    assert prepare_draft(brief, "Texto revisado")["script"] == "Texto revisado"


def test_input_control_characters_are_removed():
    brief = AffiliateBrief("Potes", "https://shopee.com.br/item", "Com tampa")
    draft = prepare_draft(brief, "Oferta" + chr(0) + " revisada")
    assert draft["script"] == "Oferta revisada"


def test_long_product_description_keeps_cta_and_limit():
    brief = AffiliateBrief("Potes", "https://shopee.com.br/item", "vedação " * 375)
    draft = prepare_draft(brief)
    assert len(draft["script"]) <= 1400
    assert draft["script"].endswith('Comente "EU QUERO" para receber o link!')
