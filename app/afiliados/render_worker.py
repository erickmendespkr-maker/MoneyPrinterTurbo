"""One-job-at-a-time worker for Afiliados Creator's persistent render queue.

The worker only runs when invoked from the server with service-role secrets.
The public Streamlit showcase does not start workers or charge paid APIs.
"""
from __future__ import annotations

import logging
import os
import threading
import time

from app.afiliados.plans import get_plan_policy
from app.afiliados.private_object_storage import PrivateObjectStorage
from app.afiliados.production_auth import AuthServiceUnavailable, SupabaseAuth
from app.afiliados.render_inputs import unpack_inputs
from app.afiliados.worker_queue import SupabaseWorkerQueue

LOG = logging.getLogger(__name__)


class WorkerLeaseLost(RuntimeError):
    pass


class RenderWorker:
    def __init__(self, queue: SupabaseWorkerQueue, storage: PrivateObjectStorage,
                 *, renderer=None, bundler=None, heartbeat_seconds: int = 120):
        if not isinstance(queue, SupabaseWorkerQueue) or not isinstance(storage, PrivateObjectStorage):
            raise ValueError("Fila e armazenamento privados obrigatórios")
        if queue.storage is not storage:
            raise ValueError("Fila e armazenamento devem usar a mesma configuração")
        if type(heartbeat_seconds) is not int or not 5 <= heartbeat_seconds <= 600:
            raise ValueError("Intervalo de heartbeat inválido")
        self.queue = queue
        self.storage = storage
        self.renderer = renderer
        self.bundler = bundler
        self.heartbeat_seconds = heartbeat_seconds

    def _render(self, job):
        package = self.storage.fetch_input(job.owner_id, job.job_id)
        data = unpack_inputs(package)
        policy = get_plan_policy(job.plan)  # plan snapshot from protected queue
        if job.kind == "campaign":
            from app.afiliados.plans import require_feature
            require_feature(job.plan, "campaign")
            if self.bundler is None:
                from app.afiliados.campaign import build_campaign
                bundle = build_campaign
            else:
                bundle = self.bundler
            return bundle(
                data.images, data.product_name, data.duration,
                data.script, data.audio, data.audio_extension,
                plan=job.plan, watermark=policy.platform_watermark_required,
            )
        if self.renderer is None:
            from app.afiliados.render import render_mp4
            render = render_mp4
        else:
            render = self.renderer
        return render(
            data.images, data.duration, data.script,
            data.audio, data.audio_extension,
            watermark=policy.platform_watermark_required,
            variant=job.variant,
        )

    def run_once(self) -> bool:
        """Claim and settle one job. Return False only when queue is empty.

        A broken job is finalized with a generic failure code; no product
        names, user photos, tokens or error details are logged.
        """
        job = self.queue.claim()
        if job is None:
            return False
        started_at = time.perf_counter()
        stop = threading.Event()
        lost = threading.Event()

        def heartbeat():
            while not stop.wait(self.heartbeat_seconds):
                try:
                    if not self.queue.heartbeat(job):
                        lost.set()
                        return
                except Exception:
                    lost.set()
                    return

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()
        error_code = "worker_failed"
        try:
            try:
                output = self._render(job)
            except ValueError:
                error_code = "invalid_input"
                raise
            except Exception:
                error_code = "render_failed"
                raise
            if lost.is_set():
                raise WorkerLeaseLost("Lease não pôde ser renovada")
            try:
                _key, checksum = self.storage.put_output(
                    job.owner_id, job.job_id, job.kind, output,
                )
            except Exception:
                error_code = "storage_failed"
                raise
            if lost.is_set():
                raise WorkerLeaseLost("Lease não pôde ser renovada")
            wall_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            self.queue.finish(job, checksum, output_bytes=len(output), wall_ms=wall_ms)
            LOG.info("Render job completed id=%s kind=%s bytes=%d wall_ms=%d",
                     job.job_id, job.kind, len(output), wall_ms)
        except Exception:
            # Do not log exception string: upstream encoders sometimes include
            # sensitive filenames, remote URLs, or customer-authored scripts.
            LOG.warning("Render job failed id=%s code=%s", job.job_id, error_code)
            if not lost.is_set():
                try:
                    self.queue.fail(job, error_code)
                except Exception:
                    # Worker lease will expire and job can be retried or timed
                    # out by a subsequent worker. Never mark complete locally.
                    LOG.warning("Unable to release job id=%s; await lease reconciliation",
                                job.job_id)
        finally:
            stop.set()
            heartbeat_thread.join(timeout=2)
        return True


def main() -> None:
    """Opt-in CLI; does not connect or provision anything during import."""
    if os.environ.get("AFILIADOS_WORKER_ENABLED") != "1":
        raise SystemExit("Worker desativado. Exige AFILIADOS_WORKER_ENABLED=1.")
    auth = SupabaseAuth.from_env()
    storage = PrivateObjectStorage.from_env(auth)
    worker = RenderWorker(SupabaseWorkerQueue(storage), storage)
    LOG.info("Afiliados Creator worker started")
    while True:
        try:
            if not worker.run_once():
                time.sleep(4)
        except AuthServiceUnavailable:
            LOG.warning("Queue temporarily unavailable; backing off")
            time.sleep(15)


if __name__ == "__main__":
    main()
