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
