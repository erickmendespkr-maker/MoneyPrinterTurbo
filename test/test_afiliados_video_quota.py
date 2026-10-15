import pytest

from app.afiliados.video_quota import VideoQuota

OWNER = "owner-test-12345"
OTHER = "other-test-12345"


def test_free_one_success_per_day(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    reservation = quota.reserve(OWNER, "gratis")
    assert quota.usage(OWNER) == 0
    quota.complete(OWNER, reservation)
    assert quota.usage(OWNER) == 1
    with pytest.raises(PermissionError, match="Limite diário"):
        quota.reserve(OWNER, "gratis")


def test_failed_render_does_not_consume_quota(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    ids = quota.reserve(OWNER, "gratis")
    quota.release(OWNER, ids)
    assert quota.usage(OWNER) == 0
    quota.complete(OWNER, quota.reserve(OWNER, "gratis"))
    assert quota.usage(OWNER) == 1


def test_pro_five_videos_and_creator_batch(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    for _ in range(5):
        quota.complete(OWNER, quota.reserve(OWNER, "pro"))
    with pytest.raises(PermissionError):
        quota.reserve(OWNER, "pro")
    ids = quota.reserve(OTHER, "creator", count=3)
    quota.complete(OTHER, ids)
    assert quota.usage(OTHER) == 3


def test_free_and_pro_cannot_reserve_three_per_ad(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    for plan in ("gratis", "pro"):
        with pytest.raises(ValueError, match="Quantidade"):
            quota.reserve(OWNER, plan, count=3)


def test_cross_owner_completion_and_double_completion_rejected(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    ids = quota.reserve(OWNER, "gratis")
    with pytest.raises(ValueError):
        quota.complete(OTHER, ids)
    quota.complete(OWNER, ids)
    with pytest.raises(ValueError):
        quota.complete(OWNER, ids)
    assert quota.usage(OWNER) == 1


def test_reserved_video_blocks_concurrent_extra_reservation(tmp_path):
    path = tmp_path / "quota.sqlite"
    first = VideoQuota(path)
    first.reserve(OWNER, "gratis")
    with pytest.raises(PermissionError):
        VideoQuota(path).reserve(OWNER, "gratis")
