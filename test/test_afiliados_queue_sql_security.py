"""Guard security properties of pending queue/storage SQL migrations.

These static checks must be followed by PostgreSQL integration tests before
deployment; they don't execute SQL.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "infra" / "supabase"
QUEUE = ROOT / "002_affiliate_jobs.sql"
STORAGE = ROOT / "003_affiliate_private_storage.sql"


def test_queue_uses_only_trusted_workers_for_render_completion():
    sql = QUEUE.read_text(encoding="utf-8")
    for name, signature in (
        ("affiliate_reserve_videos", "integer"),
        ("affiliate_complete_videos", "uuid[]"),
        ("affiliate_release_videos", "uuid[]"),
    ):
        assert f"REVOKE ALL ON FUNCTION public.{name}({signature}) FROM authenticated;" in sql
    for name, signature in (
        ("affiliate_worker_claim", ""),
        ("affiliate_worker_heartbeat", "uuid,uuid"),
        ("affiliate_worker_finish", "uuid,uuid,text,bigint,bigint"),
        ("affiliate_worker_fail", "uuid,uuid,text"),
    ):
        assert f"REVOKE ALL ON FUNCTION public.{name}({signature}) FROM PUBLIC,anon,authenticated;" in sql
        assert f"GRANT EXECUTE ON FUNCTION public.{name}({signature}) TO service_role;" in sql
    assert sql.count("auth.role() IS DISTINCT FROM 'service_role'") == 4


def test_enqueue_is_atomic_with_authorized_quota_reservation():
    sql = QUEUE.read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION public.affiliate_enqueue_job(" in sql
    assert "v_user uuid := auth.uid()" in sql
    assert "v_reservations := public.affiliate_reserve_videos(v_count);" in sql
    assert "v_user::text || '/' || p_job_id::text || '/input.zip'" in sql
    assert "j.user_id=v_user" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "GRANT EXECUTE ON FUNCTION public.affiliate_enqueue_job(uuid,text,text) TO authenticated;" in sql
    assert "GRANT EXECUTE ON FUNCTION public.affiliate_job_status(uuid) TO authenticated;" in sql
    assert "REVOKE ALL ON affiliate_private.render_jobs FROM PUBLIC, anon, authenticated;" in sql


def test_worker_finalize_checks_lease_and_updates_credits_atomically():
    sql = QUEUE.read_text(encoding="utf-8")
    assert "j.lease_token=p_lease_token AND j.lease_expires_at > v_now" in sql
    assert "status='completed',completed_at=v_now" in sql
    assert "v_count <> cardinality(v_job.reservation_ids)" in sql
    assert "output_sha256=p_sha256" in sql
    assert "output_bytes=p_output_bytes,worker_wall_ms=p_wall_ms" in sql
    assert "p_output_bytes bigint,p_wall_ms bigint" in sql
    assert "lease_expires_at" in sql
    assert "'/output.mp4'" in sql
    assert "'/output.zip'" in sql


def test_private_bucket_disallows_public_access_by_default():
    sql = STORAGE.read_text(encoding="utf-8")
    assert "'afiliados-private', 'afiliados-private', false" in sql
    assert "public = false" in sql
    assert "CREATE POLICY" not in sql
    assert "GRANT SELECT" not in sql
    assert "GRANT INSERT" not in sql
    assert "GRANT UPDATE" not in sql



def test_owner_dashboard_list_does_not_expose_storage_keys():
    sql = QUEUE.read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION public.affiliate_my_jobs(" in sql
    assert "WHERE user_id=v_user" in sql
    assert "LIMIT p_limit" in sql
    assert "GRANT EXECUTE ON FUNCTION public.affiliate_my_jobs(integer) TO authenticated;" in sql
    listing = sql.split("CREATE OR REPLACE FUNCTION public.affiliate_my_jobs(", 1)[1]
    listing = listing.split("CREATE OR REPLACE FUNCTION public.affiliate_worker_claim(", 1)[0]
    assert "'input_key'" not in listing
    assert "'output_key'" not in listing
    assert "'lease_token'" not in listing
