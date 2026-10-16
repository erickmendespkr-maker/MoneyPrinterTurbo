import pytest

from app.afiliados.link_hint import suggest_name_from_link


def test_slug_suggests_title():
    assert suggest_name_from_link("https://www.mercadolivre.com.br/aspirador-portatil-sem-fio/p/MLB123456") == "aspirador portatil sem fio"


def test_unknown_product_id_does_not_invent_name():
    assert suggest_name_from_link("https://www.amazon.com.br/dp/B012345678") == ""


def test_rejects_untrusted_hosts():
    with pytest.raises(ValueError):
        suggest_name_from_link("https://mercadolivre.com.br.evil.example/aspirador-portatil")
