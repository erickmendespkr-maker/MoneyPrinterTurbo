"""Integration smoke test without external marketplace or paid APIs."""
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import pytest
from app.services.afiliados_link_smoke import render_smoke

def test_smoke_rejects_unsupported_host(tmp_path: Path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (200, 200), "blue").save(photo)
    with pytest.raises(ValueError):
        render_smoke("https://untrusted.example/item", [photo], tmp_path / "out.mp4", fetch_metadata=False)

def test_smoke_requires_real_photo(tmp_path: Path):
    with pytest.raises(ValueError):
        render_smoke("https://shopee.com.br/item", [], tmp_path / "out.mp4", fetch_metadata=False)

def test_smoke_builds_ffmpeg_video(tmp_path: Path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (400, 500), "blue").save(photo)
    output = tmp_path / "out.mp4"
    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"synthetic-test-placeholder")
    with patch("app.services.afiliados_link_smoke.subprocess.run", side_effect=fake_run) as run:
        result = render_smoke("https://shopee.com.br/item", [photo], output, fetch_metadata=False)
    assert result["photo_count"] == 1
    assert result["platform"] == "shopee"
    assert output.is_file()
    assert "-f" in run.call_args.args[0]
