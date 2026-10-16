from pathlib import Path
from unittest.mock import patch
import pytest
from app.services.afiliados_video_watermark import (
    apply_plan_watermark, requires_platform_watermark
)

def test_plan_watermark_matrix():
    assert requires_platform_watermark("free")
    assert requires_platform_watermark("pro")
    assert not requires_platform_watermark("premium")
    assert not requires_platform_watermark("creator")
    with pytest.raises(ValueError):
        requires_platform_watermark("unknown")

def test_paid_plans_do_not_transcode(tmp_path: Path):
    missing = tmp_path / "not-rendered.mp4"
    with patch("app.services.afiliados_video_watermark.subprocess.run") as run:
        assert apply_plan_watermark(missing, "premium") == missing
        assert apply_plan_watermark(missing, "creator") == missing
    run.assert_not_called()

def test_watermark_on_synthetic_mp4(tmp_path: Path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg tools unavailable")
    sample = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "color=c=blue:s=320x568:r=12:d=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(sample)],
        check=True, timeout=45
    )
    result = apply_plan_watermark(sample, "free")
    assert result != sample
    assert result.is_file()
    assert result.stat().st_size > 0
    assert not list(tmp_path.glob("*_brand_overlay.png"))
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(result)],
        capture_output=True, text=True, check=True, timeout=20
    )
    assert abs(float(probe.stdout.strip()) - 2) < 0.3

def test_watermark_changes_corner_not_center(tmp_path: Path):
    import shutil
    import subprocess
    from PIL import Image
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg tools unavailable")
    sample = tmp_path / "product.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "color=c=black:s=720x1280:r=8:d=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(sample)],
        check=True, timeout=60
    )
    branded = apply_plan_watermark(sample, "pro")
    frame = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(branded), "-frames:v", "1", str(frame)],
        check=True, timeout=30
    )
    with Image.open(frame) as image:
        assert max(image.convert("RGB").getpixel((360, 500))) < 20
        corner = image.crop((400, 1050, 720, 1280)).convert("L")
        assert corner.getextrema()[1] >= 20
