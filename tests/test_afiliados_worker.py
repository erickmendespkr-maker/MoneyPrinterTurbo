"""Tests for isolated Afiliados worker orchestration (no external APIs)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services import afiliados_worker as worker


def test_no_job_does_not_render():
    backend = MagicMock()
    backend.claim_next.return_value = None
    with patch.object(worker, "AfiliadosBackend", return_value=backend):
        assert worker.process_one() is False
    backend.finish.assert_not_called()


def test_success_uploads_and_finishes(tmp_path: Path):
    output = tmp_path / "video.mp4"
    output.write_bytes(b"placeholder")
    backend = MagicMock()
    backend.claim_next.return_value = {
        "generation_id": "job-123",
        "user_id": "user-123",
        "duration_seconds": 15,
        "brief": {"product_name": "Mini aspirador"},
    }
    backend.upload_video.return_value = "user-123/job-123.mp4"
    backend.finish.return_value = True
    with (
        patch.object(worker, "AfiliadosBackend", return_value=backend),
        patch.object(worker, "build_video_params", return_value=MagicMock()),
        patch("app.services.task.start", return_value={"videos": [str(output)]}),
        patch.object(worker, "_duration_seconds", return_value=15.1),
    ):
        assert worker.process_one() is True
    backend.upload_video.assert_called_once()
    backend.finish.assert_called_once_with(
        "job-123", True, storage_path="user-123/job-123.mp4"
    )


def test_duration_mismatch_marks_failure(tmp_path: Path):
    output = tmp_path / "video.mp4"
    output.write_bytes(b"placeholder")
    backend = MagicMock()
    backend.claim_next.return_value = {
        "generation_id": "job-123",
        "user_id": "user-123",
        "duration_seconds": 15,
        "brief": {"product_name": "Mini aspirador"},
    }
    with (
        patch.object(worker, "AfiliadosBackend", return_value=backend),
        patch.object(worker, "build_video_params", return_value=MagicMock()),
        patch("app.services.task.start", return_value={"videos": [str(output)]}),
        patch.object(worker, "_duration_seconds", return_value=22.0),
    ):
        assert worker.process_one() is False
    backend.upload_video.assert_not_called()
    backend.finish.assert_called_once_with(
        "job-123", False, error_code="render_or_upload_failed"
    )
