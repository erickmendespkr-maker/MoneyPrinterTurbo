import io
import pytest
from PIL import Image
from app.afiliados.thumbnails import generate_thumbnails


def sample_photo():
    out = io.BytesIO()
    Image.new("RGB", (400, 600), (110, 90, 80)).save(out, format="PNG")
    return out.getvalue()


def test_three_distinct_png_thumbnails():
    result = generate_thumbnails(sample_photo(), "Mini aspirador portátil")
    assert set(result) == {"impacto", "beneficio", "curiosidade"}
    assert len(set(result.values())) == 3
    for data in result.values():
        with Image.open(io.BytesIO(data)) as image:
            assert image.size == (720, 1280)
            assert image.format == "PNG"


def test_thumbnails_validate_input():
    with pytest.raises(ValueError):
        generate_thumbnails(sample_photo(), "")
    with pytest.raises(ValueError):
        generate_thumbnails(sample_photo(), "Produto", watermark="false")
    with pytest.raises(ValueError):
        generate_thumbnails(b"not an image", "Produto")


def test_watermark_setting_changes_output():
    with_mark = generate_thumbnails(sample_photo(), "Produto", watermark=True)
    without_mark = generate_thumbnails(sample_photo(), "Produto", watermark=False)
    assert with_mark["impacto"] != without_mark["impacto"]
