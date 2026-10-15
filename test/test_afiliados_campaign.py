import io
import json
import zipfile

import pytest
from PIL import Image

from app.afiliados.campaign import build_campaign


def sample():
    buffer = io.BytesIO()
    Image.new("RGB", (120, 120), "orange").save(buffer, "PNG")
    return buffer.getvalue()


def fake_renderer(images, duration, script, audio, audio_extension, *, watermark, variant):
    assert images and duration == 15 and script == "Roteiro aprovado"
    assert watermark is True
    return b"\x00\x00\x00\x18ftypisom" + variant.encode()


def test_campaign_contains_three_videos_and_nine_unique_covers():
    payload = build_campaign([sample()], "Aspirador portátil", 15, "Roteiro aprovado",
                             renderer=fake_renderer, plan="creator")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        assert len([x for x in names if x.startswith("videos/")]) == 3
        assert len([x for x in names if x.startswith("covers/")]) == 9
        assert len(names) == 13
        assert len({archive.read(x) for x in names if x.endswith(".png")}) == 9
        manifest = json.loads(archive.read("manifest.json"))
        assert set(manifest["variants"]) == {"impacto", "beneficio", "curiosidade"}


def test_campaign_does_not_return_partial_archive_when_render_fails():
    def broken(*args, **kwargs):
        if kwargs["variant"] == "beneficio":
            raise RuntimeError("Encoder failed")
        return b"video"
    with pytest.raises(RuntimeError, match="Encoder"):
        build_campaign([sample()], "Produto", 15, "Roteiro aprovado", renderer=broken, plan="creator")


@pytest.mark.parametrize("images,name,duration,script", [
    ([], "Produto", 15, "Roteiro"),
    ([b"corrupt"], "Produto", 15, "Roteiro"),
    ([sample()], "", 15, "Roteiro"),
    ([sample()], "Produto", 12, "Roteiro"),
    ([sample()], "Produto", 15, ""),
])
def test_campaign_rejects_bad_input_before_render(images, name, duration, script):
    with pytest.raises(ValueError):
        build_campaign(images, name, duration, script, renderer=fake_renderer)


@pytest.mark.parametrize("plan", ["gratis", "pro"])
def test_batch_denied_for_lower_plans(plan):
    with pytest.raises(PermissionError, match="Creator"):
        build_campaign([sample()], "Produto", 15, "Roteiro", renderer=fake_renderer, plan=plan)
