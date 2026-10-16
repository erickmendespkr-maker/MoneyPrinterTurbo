"""Production rendering never accepts client-selected watermark/plan."""
import io
import zipfile
from uuid import uuid4

import pytest

from app.afiliados.production_generation import ProductionGeneration
from app.afiliados.production_quota import SupabaseVideoQuota

BEARER = "token-from-verified-session"
MP4 = b"\x00\x00\x00\x18ftypisom-video-encoded"


class FakeQuotas(SupabaseVideoQuota):
    def __init__(self, plan="gratis"):
        self.server_plan = plan
        self.actions = []
        self.fail_reserve = False
    def plan(self, access_token):
        self.actions.append(("plan", access_token))
        return self.server_plan
    def reserve(self, access_token, count=1):
        self.actions.append(("reserve", count))
        if self.fail_reserve:
            raise PermissionError("Cota atingida")
        return [str(uuid4()) for _ in range(count)]
    def complete(self, access_token, ids):
        self.actions.append(("complete", len(ids)))
    def release(self, access_token, ids):
        self.actions.append(("release", len(ids)))


def renderer_seen(target):
    def render(images, duration, script, audio, audio_extension, *, watermark, variant):
        target.append({"watermark": watermark, "variant": variant})
        return MP4
    return render


@pytest.mark.parametrize("plan,watermark", [
    ("gratis", True), ("pro", True), ("premium", False), ("creator", False),
])
def test_entitlements_control_watermark_from_db_not_browser(plan, watermark):
    quota = FakeQuotas(plan)
    seen = []
    rendered = ProductionGeneration(quota).render_one(
        BEARER, [b"photo"], 15, "Roteiro aprovado",
        renderer=renderer_seen(seen),
    )
    assert rendered == MP4
    assert seen == [{"watermark": watermark, "variant": "impacto"}]
    assert [step[0] for step in quota.actions] == ["plan", "reserve", "complete"]


@pytest.mark.parametrize("plan", ["gratis", "pro", "premium"])
def test_non_creator_cannot_request_creator_variant(plan):
    quota = FakeQuotas(plan)
    with pytest.raises(PermissionError):
        ProductionGeneration(quota).render_one(
            BEARER, [b"photo"], 15, "Roteiro",
            variant="beneficio", renderer=lambda *_a, **_k: MP4,
        )
    assert not any(step[0] == "reserve" for step in quota.actions)


def test_creator_can_request_variant():
    quota = FakeQuotas("creator")
    seen = []
    ProductionGeneration(quota).render_one(
        BEARER, [b"photo"], 15, "Roteiro", variant="curiosidade",
        renderer=renderer_seen(seen),
    )
    assert seen[0] == {"watermark": False, "variant": "curiosidade"}


def test_failed_render_releases_quota_instead_of_consume():
    quota = FakeQuotas()
    def failed(*_args, **_kwargs):
        raise RuntimeError("Encoding error")
    with pytest.raises(RuntimeError, match="Encoding"):
        ProductionGeneration(quota).render_one(
            BEARER, [b"photo"], 15, "Roteiro", renderer=failed,
        )
    assert [x[0] for x in quota.actions] == ["plan", "reserve", "release"]


def test_malformed_video_not_charged():
    quota = FakeQuotas()
    with pytest.raises(ValueError, match="MP4"):
        ProductionGeneration(quota).render_one(
            BEARER, [b"photo"], 15, "Roteiro",
            renderer=lambda *_a, **_k: b"not-an-mp4",
        )
    assert quota.actions[-1][0] == "release"


def test_quota_denial_precedes_render():
    quota = FakeQuotas()
    quota.fail_reserve = True
    with pytest.raises(PermissionError):
        ProductionGeneration(quota).render_one(
            BEARER, [b"photo"], 15, "Roteiro",
            renderer=lambda *_a, **_k: pytest.fail("never render"),
        )


def fake_bundle():
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as archive:
        archive.writestr("videos/impacto.mp4", MP4)
    return memory.getvalue()


def test_creator_bundle_consumes_three_video_slots():
    quota = FakeQuotas("creator")
    values = []
    def build(images, name, duration, script, audio, audio_extension, *, watermark, plan):
        values.append((watermark, plan))
        return fake_bundle()
    out = ProductionGeneration(quota).render_bundle(
        BEARER, [b"photo"], "Produto", 15, "Roteiro", bundler=build,
    )
    assert zipfile.is_zipfile(io.BytesIO(out))
    assert values == [(False, "creator")]
    assert [x[0] for x in quota.actions] == ["plan", "reserve", "complete"]
    assert quota.actions[1] == ("reserve", 3)
    assert quota.actions[2] == ("complete", 3)


@pytest.mark.parametrize("plan", ["gratis", "pro", "premium"])
def test_bundle_restricted_to_creator(plan):
    quota = FakeQuotas(plan)
    with pytest.raises(PermissionError):
        ProductionGeneration(quota).render_bundle(
            BEARER, [b"photo"], "Produto", 15, "Roteiro",
            bundler=lambda *_a, **_k: fake_bundle(),
        )
    assert not any(a[0] == "reserve" for a in quota.actions)


def test_invalid_bundle_releases_all_reservations():
    quota = FakeQuotas("creator")
    with pytest.raises(ValueError, match="Pacote"):
        ProductionGeneration(quota).render_bundle(
            BEARER, [b"photo"], "Produto", 15, "Roteiro",
            bundler=lambda *_a, **_k: b"not-zip",
        )
    assert quota.actions[-1] == ("release", 3)
