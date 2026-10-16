"""Asynchronous rendering tests with fake queues/storage and no paid APIs."""
from uuid import uuid4

import pytest

from app.afiliados.private_object_storage import PrivateObjectStorage
from app.afiliados.production_auth import SupabaseAuth
from app.afiliados.production_jobs import ProductionJobService
from app.afiliados.production_quota import RenderJobStatus, SupabaseVideoQuota
from app.afiliados.render_inputs import pack_inputs, unpack_inputs
from app.afiliados.render_worker import RenderWorker
from app.afiliados.worker_queue import SupabaseWorkerQueue, WorkerLease

OWNER = str(uuid4())
JOB = str(uuid4())
LEASE = str(uuid4())
TOKEN = "test-bearer-token"
MP4 = b"\x00\x00\x00\x18ftypisom-encoded-video"


class MemoryStore(PrivateObjectStorage):
    def __init__(self):
        self.auth = SupabaseAuth("https://exampleproject.supabase.co",
                                 "sb_publishable_example_public_key_1234")
        self.contents = {}
        self.outputs = []
        self.auth.require_verified_user = lambda _: type("Owner", (), {
            "owner_id": OWNER, "email": "email@example.com",
            "email_verified": True,
        })()

    def stage_input(self, bearer, job_id, package):
        assert bearer == TOKEN
        unpack_inputs(package)
        self.contents[job_id] = package
        return self.object_key(OWNER, job_id, "input")

    def fetch_input(self, owner_id, job_id):
        assert owner_id == OWNER
        return self.contents[job_id]

    def put_output(self, owner_id, job_id, kind, output):
        assert owner_id == OWNER
        self.outputs.append((job_id, kind, output))
        return self.object_key(owner_id, job_id, kind), "a" * 64

    def signed_result_url(self, bearer, job_id, quotas):
        status = quotas.job_status(bearer, job_id)
        if status.status != "completed":
            raise PermissionError("Not completed")
        return "https://exampleproject.supabase.co/storage/v1/object/sign/valid"


class MemoryQuotas(SupabaseVideoQuota):
    def __init__(self, auth):
        self.auth = auth
        self.items = []
        self.state = "completed"

    def enqueue_job(self, bearer, job_id, kind, variant):
        assert bearer == TOKEN
        self.items.append((job_id, kind, variant))
        return job_id

    def job_status(self, bearer, job_id):
        assert bearer == TOKEN
        return RenderJobStatus(job_id, self.state, "video", None)


class MemoryQueue(SupabaseWorkerQueue):
    def __init__(self, store, job):
        self.storage = store
        self.job = job
        self.calls = []

    def claim(self):
        job, self.job = self.job, None
        return job

    def heartbeat(self, lease):
        self.calls.append(("heartbeat", lease.job_id))
        return True

    def finish(self, lease, checksum):
        self.calls.append(("finish", lease.job_id, checksum))
        assert checksum == "a" * 64
        return self.storage.object_key(lease.owner_id, lease.job_id, lease.kind)

    def fail(self, lease, code):
        self.calls.append(("fail", lease.job_id, code))
        return True


def lease(kind="video", plan="gratis", variant="impacto"):
    return WorkerLease(JOB, OWNER, kind, variant, plan,
                       f"{OWNER}/{JOB}/input.zip", LEASE)


def test_submission_only_enqueues_after_private_file_upload():
    store = MemoryStore()
    quotas = MemoryQuotas(store.auth)
    service = ProductionJobService(quotas, store)
    job_id = service.submit(TOKEN, [b"photo"], "Produto", 15, "Roteiro")
    assert job_id in store.contents
    assert quotas.items == [(job_id, "video", "impacto")]
    assert service.status(TOKEN, job_id).status == "completed"
    assert service.download_link(TOKEN, job_id).startswith("https://")


def test_invalid_inputs_never_enqueue_or_upload():
    store = MemoryStore()
    quotas = MemoryQuotas(store.auth)
    service = ProductionJobService(quotas, store)
    with pytest.raises(ValueError):
        service.submit(TOKEN, [b"photo"], "Produto", 99, "Roteiro")
    assert not store.contents
    assert not quotas.items


@pytest.mark.parametrize("plan,watermark", [
    ("gratis", True), ("pro", True), ("premium", False), ("creator", False),
])
def test_worker_enforces_plan_watermark_without_browser_decision(plan, watermark):
    store = MemoryStore()
    store.contents[JOB] = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    queue = MemoryQueue(store, lease(plan=plan))
    seen = []
    def renderer(images, duration, script, audio, ext, *, watermark, variant):
        seen.append((watermark, variant))
        return MP4
    worker = RenderWorker(queue, store, renderer=renderer, heartbeat_seconds=5)
    assert worker.run_once() is True
    assert seen == [(watermark, "impacto")]
    assert queue.calls[0] == ("finish", JOB, "a" * 64)
    assert store.outputs == [(JOB, "video", MP4)]
    assert worker.run_once() is False


def test_queued_creator_package_uses_three_output_videos():
    store = MemoryStore()
    store.contents[JOB] = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    queue = MemoryQueue(store, lease(kind="campaign", plan="creator"))
    received = []
    def bundler(images, product, duration, script, audio, ext, *, plan, watermark):
        received.append((plan, watermark))
        return b"fake-zip-from-test"
    assert RenderWorker(queue, store, bundler=bundler, heartbeat_seconds=5).run_once()
    assert received == [("creator", False)]
    assert store.outputs[-1][1] == "campaign"
    assert queue.calls[0][0] == "finish"


def test_invalid_package_fails_and_releases_quota_instead_of_marking_complete():
    store = MemoryStore()
    store.contents[JOB] = b"not a zip"
    queue = MemoryQueue(store, lease())
    assert RenderWorker(queue, store, heartbeat_seconds=5).run_once()
    assert queue.calls == [("fail", JOB, "invalid_input")]
    assert not store.outputs


def test_encoder_failure_can_retry_later_without_false_success():
    store = MemoryStore()
    store.contents[JOB] = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    queue = MemoryQueue(store, lease())
    def broken(*args, **kwargs):
        raise RuntimeError("Sensitive product name must not enter logs")
    assert RenderWorker(queue, store, renderer=broken, heartbeat_seconds=5).run_once()
    assert queue.calls == [("fail", JOB, "render_failed")]
    assert not store.outputs


def test_input_package_never_carries_plan_or_owner():
    store = MemoryStore()
    data = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    parsed = unpack_inputs(data)
    assert parsed.product_name == "Produto"
    assert "owner_id" not in vars(parsed)
    assert "plan" not in vars(parsed)
    assert "watermark" not in vars(parsed)
