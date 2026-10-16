"""Private Supabase Storage requests: owner isolation and no client secret exposure."""
import base64
import io
import json
import zipfile
from uuid import uuid4

import pytest

from app.afiliados.private_object_storage import (
    BUCKET_NAME, PrivateObjectStorage,
)
from app.afiliados.production_auth import (
    AuthDenied, AuthServiceUnavailable, SupabaseAuth, VerifiedIdentity,
)
from app.afiliados.production_quota import RenderJobStatus, SupabaseVideoQuota
from app.afiliados.render_inputs import pack_inputs

OWNER = str(uuid4())
OTHER = str(uuid4())
JOB = str(uuid4())
TOKEN = "user_session_opaque"


def fake_service_role(role="service_role"):
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"role": role}).encode("utf-8")).decode().rstrip("=")
    return header + "." + payload + "." + "x" * 72


class FakeResponse:
    status = 200
    def __init__(self, content=b"{}"):
        self.content = content
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self, length):
        return self.content[:length]


class FakeOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        assert timeout == 30
        answer = next(self.responses)
        if isinstance(answer, Exception):
            raise answer
        return FakeResponse(answer)


class FakeQuotas(SupabaseVideoQuota):
    def __init__(self, auth, status):
        self.auth = auth
        self.result = status
        self.calls = []
    def job_status(self, token, job_id):
        self.calls.append((token, job_id))
        return self.result


def storage(*responses):
    auth = SupabaseAuth("https://example-project.supabase.co",
                        "sb_publishable_example_public_key_1234")
    auth.require_verified_user = lambda token: VerifiedIdentity(OWNER, "verified@example.com", True)
    store = PrivateObjectStorage(auth, fake_service_role())
    store._opener = FakeOpener(responses)
    return store


def test_rejects_browser_or_anon_as_storage_credentials():
    auth = SupabaseAuth("https://example-project.supabase.co",
                        "sb_publishable_example_public_key_1234")
    with pytest.raises(ValueError):
        PrivateObjectStorage(auth, "sb_publishable_public_key_not_a_secret")
    with pytest.raises(ValueError):
        PrivateObjectStorage(auth, fake_service_role("anon"))


def test_staged_input_is_private_and_owner_scoped():
    store = storage()
    package = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    key = store.stage_input(TOKEN, JOB, package)
    assert key == f"{OWNER}/{JOB}/input.zip"
    req = store._opener.requests[0]
    assert req.full_url.endswith(f"/storage/v1/object/{BUCKET_NAME}/{key}")
    assert req.get_method() == "POST"
    assert req.get_header("Authorization").startswith("Bearer ")
    assert req.data == package


def test_bad_input_never_reaches_network():
    store = storage()
    with pytest.raises(ValueError):
        store.stage_input(TOKEN, JOB, b"invalid zip")
    assert store._opener.requests == []


def test_output_paths_can_never_be_chosen_by_browser():
    store = storage()
    path, digest = store.put_output(OWNER, JOB, "video",
                                   b"\x00\x00\x00\x18ftyp-demo")
    assert path == f"{OWNER}/{JOB}/output.mp4"
    assert len(digest) == 64
    req = store._opener.requests[0]
    assert req.get_header("X-upsert") == "true"
    assert req.full_url.endswith(f"{OWNER}/{JOB}/output.mp4")


def test_campaign_output_requires_zip_archive():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zip_file:
        zip_file.writestr("videos/impacto.mp4", b"video")
    store = storage()
    path, _ = store.put_output(OWNER, JOB, "campaign", output.getvalue())
    assert path.endswith("/output.zip")
    with pytest.raises(ValueError):
        store.put_output(OWNER, JOB, "campaign", b"not-a-zip")


def test_download_signed_only_for_completed_server_scoped_job():
    key = f"{OWNER}/{JOB}/output.mp4"
    signed = f"/object/sign/{BUCKET_NAME}/{key}?token=temporary".encode("utf-8")
    store = storage(json.dumps({"signedURL": signed.decode()}).encode("utf-8"))
    q = FakeQuotas(store.auth, RenderJobStatus(JOB, "completed", "video", None))
    result = store.signed_result_url(TOKEN, JOB, q)
    assert result.endswith("?token=temporary")
    assert q.calls == [(TOKEN, JOB)]
    assert store._opener.requests[0].get_method() == "POST"


@pytest.mark.parametrize("status", ["queued", "running", "failed"])
def test_cannot_download_unfinished_job(status):
    store = storage()
    q = FakeQuotas(store.auth, RenderJobStatus(JOB, status, "video", None))
    with pytest.raises(AuthDenied):
        store.signed_result_url(TOKEN, JOB, q)
    assert store._opener.requests == []


def test_untrusted_signed_url_host_rejected():
    store = storage(json.dumps({"signedURL": "//evil.example.com/?token=abc"}).encode())
    q = FakeQuotas(store.auth, RenderJobStatus(JOB, "completed", "video", None))
    with pytest.raises(AuthServiceUnavailable):
        store.signed_result_url(TOKEN, JOB, q)


def test_owner_and_job_id_path_traversal_rejected():
    for candidate in ("../escape", "/etc/passwd", "prefix-" + OWNER):
        with pytest.raises(ValueError):
            PrivateObjectStorage.object_key(candidate, JOB, "input")
    with pytest.raises(ValueError):
        PrivateObjectStorage.object_key(OWNER, "../job", "video")
