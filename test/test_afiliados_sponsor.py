from app.afiliados.sponsor import sponsor_destination


def test_sponsor_link_free_only():
    url = "https://sponsor.example/offer?source=creator"
    assert sponsor_destination("gratis", url) == url
    assert sponsor_destination("pro", url) is None
    assert sponsor_destination("creator", url) is None


def test_rejects_unsafe_destinations():
    for url in ("http://sponsor.example", "javascript:alert(1)", "https://localhost/ad",
                "https://user:pass@sponsor.example", "https://sponsor.example:444/ad",
                "https://sponsor.example/#fragment", "https://sponsor.example/ ad"):
        assert sponsor_destination("gratis", url) is None
