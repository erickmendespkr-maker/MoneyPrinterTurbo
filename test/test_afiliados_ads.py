import pytest

from app.afiliados.ads import ads_enabled, ad_placement, validated_adsense_config


def test_ads_are_free_only():
    assert ads_enabled("gratis")
    assert not ads_enabled("pro")
    assert not ads_enabled("creator")
    with pytest.raises(ValueError):
        ads_enabled("premium")


def test_adsense_requires_valid_publisher_and_slots():
    assert validated_adsense_config(None, {}) is None
    assert validated_adsense_config("ca-pub-123", {}) is None
    assert validated_adsense_config("ca-pub-1234567890123456", {"dashboard": "12345678"}) is None
    config = validated_adsense_config(
        "ca-pub-1234567890123456",
        {"dashboard": "12345678", "render_complete": "87654321"},
    )
    assert ad_placement("gratis", "dashboard", config)["slot"] == "12345678"
    assert ad_placement("gratis", "render_complete", config)["slot"] == "87654321"
    assert ad_placement("pro", "dashboard", config) is None
    assert ad_placement("creator", "dashboard", config) is None
    assert ad_placement("gratis", "dashboard", None) is None
    with pytest.raises(ValueError):
        ad_placement("gratis", "unknown", config)
