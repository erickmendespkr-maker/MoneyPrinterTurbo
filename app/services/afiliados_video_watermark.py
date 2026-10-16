"""Apply the approved translucent brand mark to finished free/pro MP4 files."""
import subprocess
from pathlib import Path
from PIL import Image, ImageOps
from app.afiliados.branding import overlay_brand_watermark

def requires_platform_watermark(plan: str) -> bool:
    if plan not in ("free", "pro", "premium", "creator"):
        raise ValueError("Unknown plan snapshot")
    return plan in ("free", "pro")

def apply_plan_watermark(video_path: Path, plan: str) -> Path:
    if not requires_platform_watermark(plan):
        return video_path
    video_path = Path(video_path).resolve(strict=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True, check=True, timeout=30
    )
    width, height = (int(v) for v in probe.stdout.strip().split(",")[:2])
    if width < 200 or height < 200 or width * height > 24_000_000:
        raise ValueError("Invalid output video dimensions")
    base = Image.new("RGB", (width, height), (0, 0, 0))
    branded = overlay_brand_watermark(base)
    alpha = ImageOps.grayscale(branded)
    watermark = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    watermark.putalpha(alpha)
    overlay_path = video_path.with_name(video_path.stem + "_brand_overlay.png")
    output_path = video_path.with_name(video_path.stem + "_branded.mp4")
    try:
        watermark.save(overlay_path)
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(video_path), "-loop", "1", "-i", str(overlay_path),
             "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1[v]",
             "-map", "[v]", "-map", "0:a?", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
             str(output_path)],
            check=True, timeout=600
        )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("Watermarked video missing")
        return output_path
    finally:
        overlay_path.unlink(missing_ok=True)
