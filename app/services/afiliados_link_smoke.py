"""Offline integration smoke test: marketplace URL + real local product photos -> MP4.

This is a diagnostic video, not the production AI pipeline. No Supabase
credentials, paid APIs, or marketplace image downloads are needed.
Usage:
 python -m app.services.afiliados_link_smoke --url https://s.shopee.com.br/... --photo /path/product.jpg --output /tmp/affiliate-smoke.mp4
"""
import argparse
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
from app.services.afiliados_product_importer import preview_product_link, _platform
from app.afiliados.branding import overlay_brand_watermark

def render_smoke(url: str, photos: list[Path], output: Path, *, duration: int = 15, fetch_metadata: bool = True) -> dict:
    if duration not in (15, 20, 30):
        raise ValueError("Unsupported test duration")
    platform = _platform(url)
    if not photos or len(photos) > 8:
        raise ValueError("Supply between one and eight real product photos")
    output = Path(output).resolve()
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must be an MP4")
    if any(Path(p).resolve() == output for p in photos):
        raise ValueError("Output must not overwrite input photos")
    preview = preview_product_link(url) if fetch_metadata else None
    title = preview.title if preview and preview.title else "Produto enviado para teste"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="afiliados_link_test_") as temp:
        folder = Path(temp)
        frames = []
        for index, photo in enumerate(photos):
            with Image.open(photo) as original:
                original.verify()
            with Image.open(photo) as original:
                if original.width * original.height > 24_000_000:
                    raise ValueError("Photo exceeds pixel limit")
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((660, 980), Image.Resampling.LANCZOS)
            frame = Image.new("RGB", (720, 1280), "#f3f0ec")
            frame.paste(image, ((720-image.width)//2, (1180-image.height)//2))
            draw = ImageDraw.Draw(frame)
            draw.rectangle((0, 0, 720, 100), fill="#201b40")
            draw.text((25, 35), title[:65], fill="white")
            draw.rectangle((0, 1170, 720, 1280), fill="#201b40")
            draw.text((35, 1210), "Confira o produto e comente EU QUERO", fill="white")
            frame = overlay_brand_watermark(frame)
            target = folder / f"frame_{index:02d}.png"
            frame.save(target)
            frames.append(target)
        playlist = folder / "slides.txt"
        seconds = duration / len(frames)
        lines = []
        for frame in frames:
            lines.extend([f"file '{frame.as_posix()}'", f"duration {seconds:.6f}"])
        lines.append(f"file '{frames[-1].as_posix()}'")
        playlist.write_text("\n".join(lines)+"\n", encoding="utf-8")
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(playlist),
            "-vf", "fps=24,format=yuv420p", "-t", str(duration),
            "-c:v", "libx264", "-preset", "veryfast", "-movflags", "+faststart",
            str(output),
        ], check=True, timeout=180)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("Smoke MP4 not created")
    return {"output": str(output), "platform": platform, "title": title,
            "metadata_status": preview.status if preview else "skipped",
            "photo_count": len(photos), "duration_target": duration}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--photo", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--skip-metadata", action="store_true")
    args = parser.parse_args()
    print(render_smoke(args.url, [Path(p) for p in args.photo], Path(args.output),
                       duration=args.duration, fetch_metadata=not args.skip_metadata))

if __name__ == "__main__":
    main()
