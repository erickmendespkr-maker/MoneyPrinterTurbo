from PIL import Image
import pytest

from app.afiliados.branding import WATERMARK_ALPHA, overlay_brand_watermark
from app.afiliados.render import overlay_watermark


def test_approved_watermark_uses_80_percent_transparency():
    assert WATERMARK_ALPHA == 51
    original = Image.new("RGB", (720, 1280), (0, 0, 0))
    marked = overlay_watermark(original)
    assert marked.size == original.size
    assert marked.getpixel((0, 0)) == (0, 0, 0)
    # White pixels at 20% opacity should not become fully white.
    changed = [pixel for pixel in marked.crop((400, 1160, 720, 1280)).getdata() if pixel != (0, 0, 0)]
    assert changed
    assert max(max(pixel) for pixel in changed) <= 55


def test_watermark_can_be_disabled_via_zero_alpha():
    original = Image.new("RGB", (720, 1280), (120, 80, 40))
    assert overlay_brand_watermark(original, opacity=0).tobytes() == original.tobytes()


@pytest.mark.parametrize("alpha", [-1, 256, "51", True])
def test_watermark_rejects_invalid_alpha(alpha):
    with pytest.raises(ValueError):
        overlay_brand_watermark(Image.new("RGB", (720, 1280)), opacity=alpha)


def test_monochrome_watermark_works_on_light_background():
    original = Image.new("RGB", (720, 1280), (240, 240, 240))
    marked = overlay_brand_watermark(original)
    assert marked.size == original.size
    assert marked.getpixel((0, 0)) == (240, 240, 240)
    assert marked.tobytes() != original.tobytes()
