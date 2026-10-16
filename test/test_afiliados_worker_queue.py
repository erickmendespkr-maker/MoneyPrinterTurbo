"""Worker queue validates database claims and never accepts caller identities."""
import base64
import json
from uuid import uuid4

import pytest

from app.afiliados.private_object_storage import PrivateObjectStorage
from app.afiliados.production_auth import AuthServiceUnavailable, SupabaseAuth
from app.afiliados.worker_queue import SupabaseWorkerQueue

OWNER = str(uuid4())
JOB = str(uuid4())
LEASE = str(uuid4())


def service_key():
    payload = base64.urlsafe_b64encode(b'{"role":"service_role"}').decode().rstrip("=")
    return "eyJhbGciOiJIUzI1NiJ9." + payload + "." + "x" * 72


class FakeResponse:
    status = 200
    def __init__(self, answer):
        self.answer = json.dumps(answer).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self, length):
        return self.answer[:length]


class Opener:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []
    def open(self, request, timeout):
        assert timeout == 15
        self.requests.append(request)
        return FakeResponse(next(self.responses))


def worker(*responses):
    auth = SupabaseAuth("https://example-project.supabase.co",
                        "sb_publishable_example_public_key_1234")
    store = PrivateObjectStorage(auth, service_key())
    client = SupabaseWorkerQueue(store)
    client._opener = Opener(*responses)
    return client


def claim_payload(**updates):
    data = {
        "id": JOB, "owner_id": OWNER, "kind": "video",
        "variant": "impacto", "plan": "gratis",
        "input_key": f"{OWNER}/{JOB}/input.zip",
        "lease_token": LEASE,
    }
    data.update(updates)
    return data


def test_no_work_is_reported_without_error():
    q = worker(None)
    assert q.claim() is None


def test_valid_lease_enforces_user_and_input_namespace():
    q = worker(claim_payload(), True, f"{OWNER}/{JOB}/output.mp4")
    lease = q.claim()
    assert lease.owner_id == OWNER
    assert lease.plan == "gratis"
    assert lease.input_key == f"{OWNER}/{JOB}/input.zip"
    assert q.heartbeat(lease) is True
    assert q.finish(lease, "a" * 64, output_bytes=1024, wall_ms=1200) == f"{OWNER}/{JOB}/output.mp4"
    assert [r.full_url.rsplit("/", 1)[-1] for r in q._opener.requests] == [
        "affiliate_worker_claim", "affiliate_worker_heartbeat",
        "affiliate_worker_finish",
    ]


@pytest.mark.parametrize("malformed", [
    {"input_key": "../escape.zip"},
    {"input_key": f"{OWNER}/{JOB}/input-other.zip"},
    {"owner_id": "not-uuid"},
    {"lease_token": "forged"},
    {"plan": "unknown"},
    {"plan": "gratis", "variant": "beneficio"},
    {"kind": "campaign", "plan": "premium"},
])
def test_forged_claim_from_database_is_rejected(malformed):
    with pytest.raises((AuthServiceUnavailable, ValueError)):
        worker(claim_payload(**malformed)).claim()


def test_fail_requires_whitelisted_error_code():
    q = worker(True)
    lease = worker(claim_payload()).claim()
    assert q.fail(lease, "invalid_input") is True
    with pytest.raises(ValueError):
        q.fail(lease, "debug: user secret")


def test_invalid_output_checksum_rejected_before_api_call():
    q = worker()
    lease = worker(claim_payload()).claim()
    with pytest.raises(ValueError):
        q.finish(lease, "short", output_bytes=1024, wall_ms=1200)
    assert q._opener.requests == []


@pytest.mark.parametrize("bytes_count,wall_ms", [
    (0, 100), (104857601, 100), (1024, -1),
    (1024, 21600001), (True, 100), (1024, 1.4),
])
def test_rejects_invalid_worker_metrics_before_network(bytes_count, wall_ms):
    q = worker()
    lease = worker(claim_payload()).claim()
    with pytest.raises(ValueError, match="Métricas"):
        q.finish(lease, "a" * 64, output_bytes=bytes_count, wall_ms=wall_ms)
    assert q._opener.requests == []
