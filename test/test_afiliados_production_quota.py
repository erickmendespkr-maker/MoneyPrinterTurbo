"""Production RPC layer: only server-verified bearer sessions, never IDs."""
import json
import urllib.error
from uuid import uuid4

import pytest

from app.afiliados.production_auth import (
    AuthDenied, AuthServiceUnavailable, SupabaseAuth,
)
from app.afiliados.production_quota import SupabaseVideoQuota

PROJECT = "https://quota-project.supabase.co"
KEY = "sb_publishable_example_public_key_1234"
USER_ID = str(uuid4())
RESERVATION = str(uuid4())
BEARER = "auth_token_" + "x" * 50


class FakeResponse:
    status = 200
    def __init__(self, content):
        self.content = json.dumps(content).encode() if content is not None else b""
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self, length):
        return self.content[:length]


class FakeOpener:
    def __init__(self, items):
        self.items = iter(items)
        self.requests = []
    def open(self, req, timeout):
        assert timeout == 10
        self.requests.append(req)
        item = next(self.items)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)


def client(*rpc_answers):
    auth = SupabaseAuth(PROJECT, KEY)
    auth.require_verified_user = lambda access_token: (
        USER_ID if access_token == BEARER else (_ for _ in ()).throw(AuthDenied("no"))
    )
    quota = SupabaseVideoQuota(auth)
    quota._opener = FakeOpener(rpc_answers)
    return quota


def test_reserve_gets_owner_and_plan_from_sql_not_client():
    quota = client([RESERVATION])
    assert quota.reserve(BEARER, count=1) == [RESERVATION]
    req = quota._opener.requests[0]
    assert req.full_url == PROJECT + "/rest/v1/rpc/affiliate_reserve_videos"
    assert json.loads(req.data) == {"p_count": 1}
    assert req.get_header("Authorization") == "Bearer " + BEARER


def test_cannot_reserve_without_verified_session():
    quota = client([RESERVATION])
    with pytest.raises(AuthDenied):
        quota.reserve("invalid-user-token_" + "x" * 40)
    assert not quota._opener.requests


def test_status_parses_server_owned_cooldown():
    quota = client({
        "remaining_seconds": 86399, "in_progress": False,
        "attempt_retry_seconds": 0, "capacity_retry_seconds": 0,
    })
    state = quota.free_status(BEARER)
    assert not state.can_generate
    assert state.remaining_seconds == 86399


def test_available_free_status():
    quota = client({
        "remaining_seconds": 0, "in_progress": False,
        "attempt_retry_seconds": 0, "capacity_retry_seconds": 0,
    })
    assert quota.free_status(BEARER).can_generate


@pytest.mark.parametrize("bad", [
    [], ["not-uuid"], [RESERVATION, RESERVATION],
    [RESERVATION] * 4, [None],
])
def test_invalid_completion_reservations_rejected_before_call(bad):
    quota = client()
    with pytest.raises(ValueError):
        quota.complete(BEARER, bad)
    assert not quota._opener.requests


def test_complete_and_release_only_server_issued_ids():
    quota = client(None, None)
    quota.complete(BEARER, [RESERVATION])
    quota.release(BEARER, [RESERVATION])
    assert [req.full_url.rsplit("/", 1)[1] for req in quota._opener.requests] == [
        "affiliate_complete_videos", "affiliate_release_videos",
    ]
    assert all(json.loads(req.data) == {"p_ids": [RESERVATION]}
               for req in quota._opener.requests)


def test_rpc_network_failure_never_grants_generations():
    quota = client(urllib.error.URLError("offline"))
    with pytest.raises(AuthServiceUnavailable):
        quota.reserve(BEARER)


def test_provider_denied_fails_closed():
    quota = client(urllib.error.HTTPError(PROJECT, 403, "Forbidden", {}, None))
    with pytest.raises(AuthDenied):
        quota.reserve(BEARER)


@pytest.mark.parametrize("malformed", [
    {"in_progress": False, "remaining_seconds": "0",
     "attempt_retry_seconds": 0, "capacity_retry_seconds": 0},
    {"in_progress": False, "remaining_seconds": -1,
     "attempt_retry_seconds": 0, "capacity_retry_seconds": 0},
    {"in_progress": False, "remaining_seconds": 0,
     "attempt_retry_seconds": 0, "capacity_retry_seconds": 9999999},
    [],
])
def test_malformed_status_fails_closed(malformed):
    with pytest.raises(AuthServiceUnavailable):
        client(malformed).free_status(BEARER)


def test_only_authenticated_owner_can_list_jobs():
    task_id = str(uuid4())
    quota = client([{
        "id": task_id, "status": "running", "kind": "video",
        "created_at": "2026-10-15T15:30:00Z", "finished_at": None,
        "error_code": None,
    }])
    jobs = quota.list_jobs(BEARER, limit=5)
    assert len(jobs) == 1
    assert jobs[0].id == task_id
    assert jobs[0].status == "running"
    req = quota._opener.requests[0]
    assert req.full_url.endswith("/affiliate_my_jobs")
    assert json.loads(req.data) == {"p_limit": 5}


@pytest.mark.parametrize("bad", [
    [{"id": str(uuid4()), "status": "unknown", "kind": "video"}],
    [{"id": str(uuid4()), "status": "completed", "kind": "invalid"}],
    [{"id": "../invalid", "status": "completed", "kind": "video"}],
    [{"id": str(uuid4()), "status": "running", "kind": "video",
      "error_code": "z" * 60}],
    {"error": "unexpected"},
])
def test_malformed_job_list_fails_closed(bad):
    with pytest.raises(AuthServiceUnavailable):
        client(bad).list_jobs(BEARER)


def test_duplicate_job_list_rejected():
    task_id = str(uuid4())
    item = {"id": task_id, "status": "queued", "kind": "video"}
    with pytest.raises(AuthServiceUnavailable, match="duplicados"):
        client([item, item]).list_jobs(BEARER)


@pytest.mark.parametrize("limit", [0, 21, -1, 1.5, True])
def test_rejects_unbounded_history_list(limit):
    quota = client([])
    with pytest.raises(ValueError):
        quota.list_jobs(BEARER, limit)
    assert not quota._opener.requests


def test_invalid_session_cannot_list_queue():
    quota = client([])
    with pytest.raises(AuthDenied):
        quota.list_jobs("invalid-user-token_" + "x" * 40)
    assert not quota._opener.requests
