import pytest
from PIL import Image, ImageChops

from app.afiliados.plans import can_generate, get_plan_policy, watermark_required
from app.afiliados.render import overlay_watermark


def test_daily_limits_and_entitlements():
    assert can_generate("gratis", 0)
    assert not can_generate("gratis", 1)
    assert can_generate("pro", 4)
    assert not can_generate("pro", 5)
    assert can_generate("creator", 1000000)
    assert watermark_required("gratis") and watermark_required("pro")
    assert not watermark_required("creator")
    assert get_plan_policy("creator").custom_watermark_allowed
    assert not get_plan_policy("pro").custom_watermark_allowed


@pytest.mark.parametrize("plan", ["", "premium", "Creator", None])
def test_unknown_plan_fails_closed(plan):
    with pytest.raises(ValueError):
        can_generate(plan, 0)


@pytest.mark.parametrize("usage", [-1, 1.5, True, "2"])
def test_invalid_usage_fails_closed(usage):
    with pytest.raises(ValueError):
        can_generate("gratis", usage)


def test_watermark_is_small_and_bottom_right():
    source = Image.new("RGB", (720, 1280), (60, 70, 80))
    result = overlay_watermark(source)
    diff = ImageChops.difference(source, result)
    assert diff.getbbox() is not None
    assert diff.getbbox()[0] > 500
    assert diff.getbbox()[1] > 1150
    assert result.getpixel((0, 0)) == source.getpixel((0, 0))


def test_watermark_rejects_invalid_input():
    with pytest.raises(ValueError):
        overlay_watermark(Image.new("RGB", (10, 10)))
    with pytest.raises(ValueError):
        overlay_watermark(Image.new("RGB", (720, 1280)), opacity=256)


def test_only_creator_has_multiple_videos_and_thumbnails():
    from app.afiliados.plans import require_feature
    for name in ("gratis", "pro"):
        policy = get_plan_policy(name)
        assert policy.videos_per_ad == 1
        assert policy.thumbnails_per_ad == 0
        for feature in ("thumbnails", "campaign"):
            with pytest.raises(PermissionError):
                require_feature(name, feature)
    creator = get_plan_policy("creator")
    assert creator.videos_per_ad == 3
    assert creator.thumbnails_per_ad == 9
    require_feature("creator", "thumbnails")
    require_feature("creator", "campaign")
