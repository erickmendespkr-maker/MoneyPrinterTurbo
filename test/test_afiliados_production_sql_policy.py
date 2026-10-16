"""Static guardrails for the unapplied Supabase quota migration.

This does NOT replace a PostgreSQL integration test on a real project.
"""
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "infra" / "supabase" / "001_affiliate_quota.sql"


def test_each_security_definer_function_has_well_formed_dollar_quotes():
    sql = SCHEMA.read_text(encoding="utf-8")
    assert sql.count("CREATE OR REPLACE FUNCTION public.affiliate_") == 5
    assert sql.count("AS $$\n") == 5
    assert sql.count("END\n$$;") == 5
    assert sql.count("SECURITY DEFINER SET search_path = ''") == 5


def test_no_authenticated_user_can_write_plan_or_quota_tables_directly():
    sql = SCHEMA.read_text(encoding="utf-8")
    assert "REVOKE ALL ON SCHEMA affiliate_private FROM PUBLIC, anon, authenticated;" in sql
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA affiliate_private FROM PUBLIC, anon, authenticated;" in sql
    assert "REVOKE ALL ON ALL SEQUENCES IN SCHEMA affiliate_private FROM PUBLIC, anon, authenticated;" in sql
    assert "GRANT INSERT" not in sql
    assert "GRANT UPDATE" not in sql
    assert "GRANT DELETE" not in sql


def test_backend_functions_derive_verified_identity_from_auth_uid():
    sql = SCHEMA.read_text(encoding="utf-8")
    assert sql.count("v_user uuid := auth.uid()") == 5
    assert "email_confirmed_at IS NOT NULL" in sql
    assert "CREATE OR REPLACE FUNCTION public.affiliate_my_plan()" in sql
    assert "COALESCE(v_plan, 'gratis')" in sql
    for fn in ("affiliate_reserve_videos(integer)", "affiliate_complete_videos(uuid[])",
               "affiliate_release_videos(uuid[])", "affiliate_free_status()",
               "affiliate_my_plan()"):
        assert f"REVOKE ALL ON FUNCTION public.{fn} FROM PUBLIC, anon;" in sql
        assert f"GRANT EXECUTE ON FUNCTION public.{fn} TO authenticated;" in sql


def test_rolling_free_quota_limits_are_shared_and_persisted():
    sql = SCHEMA.read_text(encoding="utf-8")
    assert "completed_at > v_now - INTERVAL '24 hours'" in sql
    assert "a.started_at > v_now - INTERVAL '24 hours'" in sql
    assert "a.started_at > v_now - INTERVAL '1 hour'" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "12" in sql and "40" in sql and "5" in sql
