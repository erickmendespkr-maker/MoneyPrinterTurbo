"""Regression tests for rolling free cooldown and atomic render reservations."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import app.afiliados.video_quota as module
from app.afiliados.video_quota import VideoQuota, FREE_COOLDOWN_SECONDS

OWNER = "owner-test-12345"
OTHER = "other-test-12345"
TZ = ZoneInfo("America/Sao_Paulo")


def test_free_cooldown_crosses_midnight_and_expires_exactly_at_24h(tmp_path, monkeypatch):
    # 23:59 Sao Paulo -> next day 00:00, STILL locked for 23h59m.
    instant = int(datetime(2026, 10, 15, 23, 59, tzinfo=TZ).timestamp())
    clock = [instant]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    quota = VideoQuota(tmp_path / "quota.sqlite")
    assert quota.free_status(OWNER).can_generate
    ids = quota.reserve(OWNER, "gratis")
    assert quota.free_status(OWNER).in_progress
    quota.complete(OWNER, ids)
    assert quota.free_status(OWNER).remaining_seconds == 86400
    clock[0] += 60
    assert quota.free_status(OWNER).remaining_seconds == 86340
    with pytest.raises(PermissionError, match="24 horas"):
        quota.reserve(OWNER, "gratis")
    clock[0] = instant + FREE_COOLDOWN_SECONDS - 1
    assert quota.free_status(OWNER).remaining_seconds == 1
    with pytest.raises(PermissionError):
        quota.reserve(OWNER, "gratis")
    clock[0] += 1
    assert quota.free_status(OWNER).can_generate
    quota.complete(OWNER, quota.reserve(OWNER, "gratis"))
    assert quota.free_status(OWNER).remaining_seconds == 86400


def test_cooldown_starts_after_successful_completion(tmp_path, monkeypatch):
    clock = [1800000000]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    quota = VideoQuota(tmp_path / "quota.sqlite")
    reserved = quota.reserve(OWNER, "gratis")
    clock[0] += 480
    quota.complete(OWNER, reserved)
    assert quota.free_status(OWNER).remaining_seconds == 86400
    clock[0] += 86400
    assert quota.free_status(OWNER).can_generate


def test_failed_render_does_not_start_cooldown(tmp_path, monkeypatch):
    clock = [1800000000]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    quota = VideoQuota(tmp_path / "quota.sqlite")
    ids = quota.reserve(OWNER, "gratis")
    quota.release(OWNER, ids)
    assert quota.free_status(OWNER).can_generate
    quota.complete(OWNER, quota.reserve(OWNER, "gratis"))
    assert not quota.free_status(OWNER).can_generate


def test_multiple_tabs_cannot_reserve_a_second_free_video(tmp_path):
    path = tmp_path / "quota.sqlite"
    first = VideoQuota(path)
    first.reserve(OWNER, "gratis")
    with pytest.raises(PermissionError):
        VideoQuota(path).reserve(OWNER, "gratis")


def test_parallel_free_reservation_only_one_wins(tmp_path):
    path = tmp_path / "quota.sqlite"
    def attempt(_):
        try:
            return bool(VideoQuota(path).reserve(OWNER, "gratis"))
        except PermissionError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(attempt, range(4)))
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 3


def test_stale_reservation_releases_slot_without_successful_video(tmp_path, monkeypatch):
    clock = [1800000000]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    quota = VideoQuota(tmp_path / "quota.sqlite")
    abandoned = quota.reserve(OWNER, "gratis")
    clock[0] += module.RESERVATION_TTL_SECONDS
    assert quota.free_status(OWNER).can_generate
    with pytest.raises(ValueError, match="Reserva"):
        quota.complete(OWNER, abandoned)
    quota.complete(OWNER, quota.reserve(OWNER, "gratis"))


def test_usage_for_paid_calendar_quotas(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    for _ in range(3):
        quota.complete(OWNER, quota.reserve(OWNER, "pro"))
    with pytest.raises(PermissionError):
        quota.reserve(OWNER, "pro")
    for _ in range(5):
        quota.complete(OTHER, quota.reserve(OTHER, "premium"))
    with pytest.raises(PermissionError):
        quota.reserve(OTHER, "premium")


def test_creator_ten_per_day_and_batch(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    for _ in range(3):
        quota.complete(OWNER, quota.reserve(OWNER, "creator", count=3))
    quota.complete(OWNER, quota.reserve(OWNER, "creator"))
    with pytest.raises(PermissionError):
        quota.reserve(OWNER, "creator")


def test_free_and_pro_cannot_reserve_three_per_ad(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    for plan in ("gratis", "pro", "premium"):
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


def test_legacy_table_upgrade_preserves_completed_video(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite"
    instant = int(datetime(2026, 10, 15, 20, tzinfo=TZ).timestamp())
    clock = [instant + 60]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE affiliate_video_quota (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, day TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("INSERT INTO affiliate_video_quota VALUES (?,?,?,?,?)",
                   ("a" * 32, OWNER, "2026-10-15", "completed",
                    datetime.fromtimestamp(instant, TZ).isoformat()))
    quota = VideoQuota(path)
    assert quota.free_status(OWNER).remaining_seconds == 86340
    with pytest.raises(PermissionError):
        quota.reserve(OWNER, "gratis")


def test_downgraded_user_cannot_reset_cooldown(tmp_path):
    quota = VideoQuota(tmp_path / "quota.sqlite")
    quota.complete(OWNER, quota.reserve(OWNER, "pro"))
    assert not quota.free_status(OWNER).can_generate
    with pytest.raises(PermissionError):
        quota.reserve(OWNER, "gratis")


def test_free_failed_render_storm_limited_without_consuming_success_quota(tmp_path, monkeypatch):
    clock = [1800000000]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    quota = VideoQuota(tmp_path / "quota.sqlite")
    for _ in range(module.FREE_MAX_RENDER_ATTEMPTS):
        reservation = quota.reserve(OWNER, "gratis")
        quota.release(OWNER, reservation)
    assert quota.free_status(OWNER).attempt_retry_seconds == module.FREE_ATTEMPT_WINDOW_SECONDS
    assert not quota.free_status(OWNER).can_generate
    with pytest.raises(PermissionError, match="Muitas tentativas"):
        quota.reserve(OWNER, "gratis")
    clock[0] += module.FREE_ATTEMPT_WINDOW_SECONDS + 1
    assert quota.reserve(OWNER, "gratis")


def test_global_free_render_pool_limits_multiple_accounts(tmp_path, monkeypatch):
    clock = [1800000000]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    monkeypatch.setattr(module, "MAX_GLOBAL_FREE_ATTEMPTS_PER_HOUR", 2)
    quota = VideoQuota(tmp_path / "quota.sqlite")
    for owner in ("account_1", "account_2"):
        quota.release(owner, quota.reserve(owner, "gratis"))
    assert quota.free_status("account_3").capacity_retry_seconds == 3600
    with pytest.raises(PermissionError, match="Capacidade gratuita"):
        quota.reserve("account_3", "gratis")
    # The global limit rolls forward; it is not reset by a new email account.
    clock[0] += 3601
    assert quota.free_status("account_3").can_generate
    assert quota.reserve("account_3", "gratis")


def test_global_daily_budget_blocks_multi_account_exhaustion(tmp_path, monkeypatch):
    clock = [1800000000]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    monkeypatch.setattr(module, "MAX_GLOBAL_FREE_ATTEMPTS_PER_HOUR", 100)
    monkeypatch.setattr(module, "MAX_GLOBAL_FREE_ATTEMPTS_PER_DAY", 2)
    quota = VideoQuota(tmp_path / "quota.sqlite")
    for owner in ("account_a", "account_b"):
        quota.release(owner, quota.reserve(owner, "gratis"))
    assert quota.free_status("account_c").capacity_retry_seconds == 86400
    with pytest.raises(PermissionError, match="Capacidade gratuita"):
        quota.reserve("account_c", "gratis")
    clock[0] += 3601  # Hourly window passes, daily budget still protects resources
    assert not quota.free_status("account_c").can_generate
    clock[0] += 86400 - 3601 + 1
    assert quota.free_status("account_c").can_generate
