"""Single-job Afiliados Creator worker entrypoint.

Run from a trusted, isolated rendering host only. Does not start a public API.
Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import argparse
import os
import subprocess
import sys
import threading
import tempfile
from pathlib import Path

from loguru import logger

from app.services.afiliados_backend import AfiliadosBackend
from app.services.afiliados_render_params import build_video_params
from app.services.afiliados_product_media import download_product_photos
from app.services.afiliados_video_watermark import apply_plan_watermark
from app.utils import utils


def _duration_seconds(file_path: Path) -> float:
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(file_path),
        ],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return float(probe.stdout.strip())


def _heartbeat_loop(backend, generation_id: str, stop: threading.Event) -> None:
    while not stop.wait(60):
        try:
            if not backend.heartbeat(generation_id):
                logger.warning("Heartbeat rejected for {}", generation_id)
                return
        except Exception:
            logger.exception("Heartbeat failed for {}", generation_id)


def process_one() -> bool:
    backend = AfiliadosBackend()
    job = backend.claim_next()
    if not job:
        logger.info("No reserved jobs")
        return False

    generation_id = job["generation_id"]
    user_id = job["user_id"]
    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop, args=(backend, generation_id, stop_heartbeat), daemon=True,
    )
    heartbeat_thread.start()
    try:
        plan_snapshot = backend.get_generation_plan(generation_id, user_id)
        from app.services import task as task_service

        # Prevent unrelated Pexels footage being published as a real product.
        source = job["brief"].get("source")
        if not isinstance(source, dict) or source.get("mode") not in ("images", "both"):
            raise RuntimeError("product_images_required")
        with tempfile.TemporaryDirectory(prefix="afiliados_", dir=utils.storage_dir("local_videos", create=True)) as workdir:
            photos = download_product_photos(backend, source, user_id, Path(workdir))
            if not photos:
                raise RuntimeError("product_images_required")
            params = build_video_params(job["brief"], job["duration_seconds"], [str(p) for p in photos])
            if params.video_source != "local":
                raise RuntimeError("stock_media_forbidden")
            result = task_service.start(generation_id, params, stop_at="video")
        if not isinstance(result, dict):
            raise RuntimeError("render_failed")
        paths = result.get("videos") or []
        if not paths:
            raise RuntimeError("render_no_output")
        file_path = Path(paths[0]).resolve(strict=True)
        if not file_path.is_file() or file_path.suffix.lower() != ".mp4":
            raise RuntimeError("render_invalid_output")
        actual = _duration_seconds(file_path)
        if abs(actual - job["duration_seconds"]) > 2.0:
            raise RuntimeError("render_duration_mismatch")
        branded_path = apply_plan_watermark(file_path, plan_snapshot)
        if abs(_duration_seconds(branded_path) - job["duration_seconds"]) > 2.0:
            raise RuntimeError("watermark_duration_mismatch")
        storage_path = backend.upload_video(user_id, generation_id, str(branded_path))
        if not backend.finish(generation_id, True, storage_path=storage_path):
            raise RuntimeError("job_no_longer_processing")
        logger.info("Completed generation {}", generation_id)
    except Exception as exc:
        logger.exception("Generation {} failed: {}", generation_id, type(exc).__name__)
        # Never store raw provider errors, user content, or credentials in the DB.
        try:
            backend.finish(generation_id, False, error_code="render_or_upload_failed")
        except Exception:
            logger.exception("Unable to record failure for {}", generation_id)
        return False
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=5)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", required=True)
    parser.parse_args()
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        sys.exit("Missing server-side Supabase credentials")
    sys.exit(0 if process_one() else 1)
