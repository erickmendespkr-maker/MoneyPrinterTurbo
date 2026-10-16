"""Approved Afiliados Creator monochrome watermark.

The A inside an open C is drawn as vector-like Pillow paths, without external
assets or paid services. Transparency is 80% (alpha 20%).
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

WATERMARK_ALPHA = 51


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def overlay_brand_watermark(photo: Image.Image, *, opacity: int = WATERMARK_ALPHA) -> Image.Image:
    """Place a small grayscale A-in-C brand lockup in the bottom-right corner."""
    if not isinstance(photo, Image.Image) or photo.width < 200 or photo.height < 200:
        raise ValueError("Imagem inválida para marca-d'água")
    if type(opacity) is not int or not 0 <= opacity <= 255:
        raise ValueError("Opacidade inválida")
    base = photo.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    scale = min(photo.width / 720, photo.height / 1280)
    size = max(22, round(46 * scale))
    font_size = max(11, round(18 * scale))
    font = _font(font_size)
    margin = max(12, round(24 * scale))
    gap = max(5, round(8 * scale))
    line_height = max(12, round(21 * scale))
    label_width = max(draw.textbbox((0, 0), line, font=font)[2] for line in ("Afiliados", "Creator"))
    x = base.width - margin - size - gap - label_width
    y = base.height - margin - max(size, line_height * 2)
    white = (255, 255, 255, opacity)
    # C: open circular arc; A: two diagonals plus crossbar. Monochrome only.
    stroke = max(3, round(7 * scale))
    draw.arc((x + stroke, y + stroke, x + size - stroke, y + size - stroke),
             start=40, end=320, fill=white, width=stroke)
    draw.line([(x + size * .30, y + size * .72),
               (x + size * .50, y + size * .27),
               (x + size * .71, y + size * .72)],
              fill=white, width=max(2, round(5 * scale)), joint="curve")
    draw.line([(x + size * .39, y + size * .57), (x + size * .62, y + size * .57)],
              fill=white, width=max(2, round(4 * scale)))
    text_x = x + size + gap
    for i, line in enumerate(("Afiliados", "Creator")):
        draw.text((text_x, y + i * line_height), line, font=font, fill=white)
    return Image.alpha_composite(base, layer).convert("RGB")
