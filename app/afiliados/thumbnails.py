"""Generate three offline cover designs from a real supplied product photo."""
from __future__ import annotations

import io
from PIL import ImageDraw, ImageFont
from app.afiliados.render import VIDEO_VARIANTS, normalize_photo, overlay_watermark

STYLES = ("impacto", "beneficio", "curiosidade")


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def generate_thumbnails(photo: bytes, product_name: str, *, watermark: bool = True, video_variant: str | None = None) -> dict[str, bytes]:
    """Return three 720x1280 PNG covers; never fabricate product imagery or claims."""
    if not isinstance(product_name, str) or not product_name.strip() or len(product_name) > 140:
        raise ValueError("Nome do produto inválido")
    if type(watermark) is not bool:
        raise ValueError("Configuração de marca-d'água inválida")
    if video_variant is not None and video_variant not in VIDEO_VARIANTS:
        raise ValueError("Variação de vídeo inválida")
    base = normalize_photo(photo)
    title = " ".join(product_name.split())
    styles = {
        "impacto": ("CONHEÇA ESTE PRODUTO", (22, 26, 42)),
        "beneficio": ("VEJA OS DETALHES", (23, 70, 63)),
        "curiosidade": ("VOCÊ JÁ CONHECE?", (65, 34, 82)),
    }
    result = {}
    for style, (headline, background) in styles.items():
        canvas = base.copy()
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((25, 65, 695, 295), radius=24, fill=background)
        if video_variant is not None:
            draw.rounded_rectangle((25, 310, 695, 370), radius=14, fill=background)
            draw.text((360, 320), f"VÍDEO: {video_variant.upper()}", font=_font(24), anchor="mt", fill="white")
        draw.text((360, 90), headline, font=_font(29), anchor="mt", fill="white")
        words = title.split()
        lines = []
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if draw.textbbox((0, 0), candidate, font=_font(31))[2] <= 600:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if len(lines) > 3:
            lines = lines[:2] + ["…"]
        for index, line in enumerate(lines):
            # Clip unbroken identifiers without allowing text to escape the design.
            while line and draw.textbbox((0, 0), line, font=_font(31))[2] > 600:
                line = line[:-2] + "…"
            draw.text((360, 145 + index * 41), line, font=_font(31), anchor="mt", fill="white")
        if watermark:
            canvas = overlay_watermark(canvas)
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        result[style] = buffer.getvalue()
    return result
