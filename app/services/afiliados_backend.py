"""Supabase job lifecycle adapter for Afiliados Creator.

Use only on the trusted rendering server. Never expose SUPABASE_SERVICE_ROLE_KEY
to browsers, mobile apps, logs, or user-controlled configuration.
"""
import os
from pathlib import Path
from typing import Optional
import requests


class AfiliadosBackend:
    def __init__(self):
        self.url = os.environ["SUPABASE_URL"].rstrip("/")
        self.key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        })

    def _rpc(self, name: str, payload: dict):
        response = self.session.post(
            f"{self.url}/rest/v1/rpc/{name}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def start(self, generation_id: str) -> bool:
        """Atomically claim a reserved job; False means already claimed/closed."""
        return bool(self._rpc("worker_start_generation", {
            "p_generation_id": generation_id,
        }))

    def finish(
        self,
        generation_id: str,
        success: bool,
        storage_path: Optional[str] = None,
        error_code: Optional[str] = None,
        cost_usd: float = 0,
    ) -> bool:
        return bool(self._rpc("worker_finish_generation", {
            "p_generation_id": generation_id,
            "p_success": success,
            "p_storage_path": storage_path,
            "p_error_code": error_code,
            "p_cost_usd": cost_usd,
        }))

    def upload_video(self, user_id: str, generation_id: str, file_path: str) -> str:
        """Upload a completed MP4 to the user's private bucket folder."""
        path = Path(file_path)
        if path.suffix.lower() != ".mp4":
            raise ValueError("Only MP4 uploads are supported by this adapter")
        storage_path = f"{user_id}/{generation_id}.mp4"
        with path.open("rb") as stream:
            response = self.session.post(
                f"{self.url}/storage/v1/object/generated-videos/{storage_path}",
                data=stream,
                headers={"Content-Type": "video/mp4", "x-upsert": "false"},
                timeout=300,
            )
        response.raise_for_status()
        return storage_path

    def fail_stale(self, older_than_minutes: int = 60) -> int:
        return int(self._rpc("worker_fail_stale_generations", {
            "p_older_than_minutes": older_than_minutes,
        }))

    def claim_next(self):
        """Claim one queued job atomically, or return None if queue is empty."""
        jobs = self._rpc("worker_claim_next_generation", {})
        return jobs[0] if jobs else None
    def heartbeat(self, generation_id: str) -> bool:
        """Refresh processing activity to prevent a healthy job timing out."""
        return bool(self._rpc("worker_heartbeat_generation", {
            "p_generation_id": generation_id,
        }))
