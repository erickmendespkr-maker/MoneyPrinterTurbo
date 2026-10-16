-- Afiliados Creator / Supabase: durable async render queue (NOT applied).
-- Apply after 001_affiliate_quota.sql. Never expose the service_role credential.
-- User JWT may enqueue a job and read its status, but ONLY a trusted worker may
-- claim, finalize, fail or alter an output/usage reservation.
BEGIN;
CREATE TABLE IF NOT EXISTS affiliate_private.render_jobs (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('video','campaign')),
  variant text NOT NULL CHECK (variant IN ('impacto','beneficio','curiosidade')),
  plan_at_enqueue text NOT NULL CHECK (plan_at_enqueue IN ('gratis','pro','premium','creator')),
  input_key text NOT NULL,
  output_key text,
  reservation_ids uuid[] NOT NULL,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','failed')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
  lease_token uuid,
  lease_expires_at timestamptz,
  output_sha256 text,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at timestamptz,
  CONSTRAINT render_job_input_is_private CHECK (length(input_key) <= 150),
  CONSTRAINT render_job_result_is_private CHECK (output_key IS NULL OR length(output_key) <= 150),
  CONSTRAINT render_job_bundle_count CHECK (
    cardinality(reservation_ids) IN (1,3)
    AND ((kind='video' AND cardinality(reservation_ids)=1)
      OR (kind='campaign' AND cardinality(reservation_ids)=3))
  )
);
CREATE INDEX IF NOT EXISTS idx_affiliate_jobs_claim
  ON affiliate_private.render_jobs(status, lease_expires_at, created_at);
CREATE INDEX IF NOT EXISTS idx_affiliate_jobs_owner
  ON affiliate_private.render_jobs(user_id, created_at DESC);
REVOKE ALL ON affiliate_private.render_jobs FROM PUBLIC, anon, authenticated;

-- Closing a permission gap in migration 001: verified users may not directly
-- reserve, complete, or release jobs outside the controlled enqueue/worker flow.
REVOKE ALL ON FUNCTION public.affiliate_reserve_videos(integer) FROM authenticated;
REVOKE ALL ON FUNCTION public.affiliate_complete_videos(uuid[]) FROM authenticated;
REVOKE ALL ON FUNCTION public.affiliate_release_videos(uuid[]) FROM authenticated;

-- Enqueue is atomic with quota reservation. A trusted web backend must upload
-- and validate the private input object BEFORE invoking this RPC.
-- input_key is derived, not supplied; owner_id/plan/watermark are server-owned.
CREATE OR REPLACE FUNCTION public.affiliate_enqueue_job(
  p_job_id uuid, p_kind text, p_variant text DEFAULT 'impacto'
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_user uuid := auth.uid();
  v_plan text;
  v_reservations uuid[];
  v_count integer;
  v_now timestamptz;
BEGIN
  IF v_user IS NULL OR NOT EXISTS (
    SELECT 1 FROM auth.users u
    WHERE u.id=v_user AND u.email_confirmed_at IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'Confirmacao de e-mail obrigatoria' USING ERRCODE='42501';
  END IF;
  IF p_job_id IS NULL OR p_kind NOT IN ('video','campaign')
     OR p_variant NOT IN ('impacto','beneficio','curiosidade')
     OR p_kind IS NULL OR p_variant IS NULL THEN
    RAISE EXCEPTION 'Trabalho invalido' USING ERRCODE='22023';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(819320123888::bigint);
  v_now := clock_timestamp();
  SELECT s.plan INTO v_plan FROM affiliate_private.subscriptions s
    WHERE s.user_id=v_user;
  v_plan := COALESCE(v_plan, 'gratis');
  IF (p_kind='campaign' AND (v_plan <> 'creator' OR p_variant <> 'impacto'))
     OR (p_kind='video' AND p_variant <> 'impacto' AND v_plan <> 'creator') THEN
    RAISE EXCEPTION 'Recurso indisponivel para o plano' USING ERRCODE='42501';
  END IF;
  IF (SELECT count(*) FROM affiliate_private.render_jobs j
      WHERE j.user_id=v_user AND j.status IN ('queued','running')) >= 2 THEN
    RAISE EXCEPTION 'Aguarde seus trabalhos em andamento' USING ERRCODE='P0001';
  END IF;
  IF (SELECT count(*) FROM affiliate_private.render_jobs j
      WHERE j.status IN ('queued','running')) >= 100 THEN
    RAISE EXCEPTION 'Fila temporariamente cheia' USING ERRCODE='P0001';
  END IF;
  v_count := CASE WHEN p_kind='campaign' THEN 3 ELSE 1 END;
  -- Called as the SECURITY DEFINER owner. If job insertion fails, quota rolls
  -- back as part of the same database transaction.
  v_reservations := public.affiliate_reserve_videos(v_count);
  INSERT INTO affiliate_private.render_jobs(
    id,user_id,kind,variant,plan_at_enqueue,input_key,reservation_ids,status,created_at
  ) VALUES (
    p_job_id,v_user,p_kind,p_variant,v_plan,
    v_user::text || '/' || p_job_id::text || '/input.zip',
    v_reservations,'queued',v_now
  );
  RETURN p_job_id;
END
$$;

-- Public polling returns only the authenticated owner's own job,
-- and never exposes private storage keys or lease tokens.
CREATE OR REPLACE FUNCTION public.affiliate_job_status(p_job_id uuid)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_user uuid := auth.uid();
  v_job affiliate_private.render_jobs%ROWTYPE;
BEGIN
  IF v_user IS NULL OR p_job_id IS NULL THEN
    RAISE EXCEPTION 'Autenticacao obrigatoria' USING ERRCODE='42501';
  END IF;
  SELECT * INTO v_job FROM affiliate_private.render_jobs j
    WHERE j.id=p_job_id AND j.user_id=v_user;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Trabalho nao encontrado' USING ERRCODE='P0002';
  END IF;
  RETURN jsonb_build_object(
    'id',v_job.id,'status',v_job.status,'kind',v_job.kind,
    'created_at',v_job.created_at,'finished_at',v_job.finished_at,
    'error_code',v_job.error_code
  );
END
$$;

-- Owner-scoped read-only listing for the beta dashboard. No private
-- input/output keys, token, or worker lease are ever returned.
CREATE OR REPLACE FUNCTION public.affiliate_my_jobs(p_limit integer DEFAULT 10)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $
DECLARE
  v_user uuid := auth.uid();
  v_jobs jsonb;
BEGIN
  IF v_user IS NULL THEN
    RAISE EXCEPTION 'Autenticacao obrigatoria' USING ERRCODE='42501';
  END IF;
  IF p_limit IS NULL OR p_limit < 1 OR p_limit > 20 THEN
    RAISE EXCEPTION 'Limite de listagem invalido' USING ERRCODE='22023';
  END IF;
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'id',j.id,'status',j.status,'kind',j.kind,
      'created_at',j.created_at,'finished_at',j.finished_at,
      'error_code',j.error_code) ORDER BY j.created_at DESC),
    '[]'::jsonb)
  INTO v_jobs
  FROM (
    SELECT id,status,kind,created_at,finished_at,error_code
    FROM affiliate_private.render_jobs
    WHERE user_id=v_user
    ORDER BY created_at DESC
    LIMIT p_limit
  ) j;
  RETURN v_jobs;
END
$;

-- Worker RPCs require the service_role JWT and do not accept owner IDs
-- from callers. A lease UUID ensures stale workers cannot finalize twice.
CREATE OR REPLACE FUNCTION public.affiliate_worker_claim()
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_job affiliate_private.render_jobs%ROWTYPE;
  v_now timestamptz;
BEGIN
  IF auth.role() IS DISTINCT FROM 'service_role' THEN
    RAISE EXCEPTION 'Worker autorizado obrigatorio' USING ERRCODE='42501';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(819320123888::bigint);
  v_now := clock_timestamp();
  -- Reservations expire after six hours in migration 001; expired jobs must
  -- not be reclaimed and must release any remaining reservations.
  UPDATE affiliate_private.render_jobs j
    SET status='failed',error_code='expired',finished_at=v_now,
        lease_token=NULL,lease_expires_at=NULL
    WHERE j.status IN ('queued','running')
      AND (j.created_at <= v_now - INTERVAL '6 hours'
           OR (j.status='running' AND j.attempts >= 3
               AND j.lease_expires_at <= v_now));
  DELETE FROM affiliate_private.renders r USING affiliate_private.render_jobs j
    WHERE j.status='failed' AND j.error_code='expired'
      AND r.id = ANY(j.reservation_ids) AND r.status='reserved';
  SELECT * INTO v_job FROM affiliate_private.render_jobs j
    WHERE (j.status='queued'
           OR (j.status='running' AND j.lease_expires_at <= v_now))
      AND j.attempts < 3 AND j.created_at > v_now - INTERVAL '6 hours'
    ORDER BY j.created_at ASC
    LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN RETURN NULL; END IF;
  UPDATE affiliate_private.render_jobs j SET
    status='running',attempts=j.attempts+1,
    lease_token=gen_random_uuid(),
    lease_expires_at=LEAST(v_now+INTERVAL '20 minutes',
                           j.created_at+INTERVAL '6 hours')
    WHERE j.id=v_job.id RETURNING * INTO v_job;
  RETURN jsonb_build_object(
    'id',v_job.id,'owner_id',v_job.user_id,'kind',v_job.kind,
    'variant',v_job.variant,'plan',v_job.plan_at_enqueue,
    'input_key',v_job.input_key,'lease_token',v_job.lease_token,
    'lease_expires_at',v_job.lease_expires_at
  );
END
$$;

CREATE OR REPLACE FUNCTION public.affiliate_worker_heartbeat(
  p_job_id uuid,p_lease_token uuid
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_count integer;
BEGIN
  IF auth.role() IS DISTINCT FROM 'service_role' THEN
    RAISE EXCEPTION 'Worker autorizado obrigatorio' USING ERRCODE='42501';
  END IF;
  UPDATE affiliate_private.render_jobs j
    SET lease_expires_at=LEAST(
      clock_timestamp()+INTERVAL '20 minutes',j.created_at+INTERVAL '6 hours')
    WHERE j.id=p_job_id AND j.lease_token=p_lease_token
      AND j.status='running' AND j.lease_expires_at > clock_timestamp();
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count=1;
END
$$;

CREATE OR REPLACE FUNCTION public.affiliate_worker_finish(
  p_job_id uuid,p_lease_token uuid,p_sha256 text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_job affiliate_private.render_jobs%ROWTYPE;
  v_now timestamptz;
  v_count integer;
  v_key text;
BEGIN
  IF auth.role() IS DISTINCT FROM 'service_role' THEN
    RAISE EXCEPTION 'Worker autorizado obrigatorio' USING ERRCODE='42501';
  END IF;
  IF p_sha256 IS NULL OR p_sha256 !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'Hash de arquivo invalido' USING ERRCODE='22023';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(819320123888::bigint);
  v_now := clock_timestamp();
  SELECT * INTO v_job FROM affiliate_private.render_jobs j
    WHERE j.id=p_job_id AND j.status='running'
      AND j.lease_token=p_lease_token AND j.lease_expires_at > v_now
    FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Lease expirada ou invalida' USING ERRCODE='42501';
  END IF;
  UPDATE affiliate_private.renders r
    SET status='completed',completed_at=v_now
    WHERE r.id=ANY(v_job.reservation_ids) AND r.user_id=v_job.user_id
      AND r.status='reserved';
  GET DIAGNOSTICS v_count = ROW_COUNT;
  IF v_count <> cardinality(v_job.reservation_ids) THEN
    RAISE EXCEPTION 'Reserva inconsistente' USING ERRCODE='P0001';
  END IF;
  v_key := v_job.user_id::text || '/' || v_job.id::text ||
           CASE WHEN v_job.kind='campaign' THEN '/output.zip'
                ELSE '/output.mp4' END;
  UPDATE affiliate_private.render_jobs j SET
    status='completed',output_key=v_key,output_sha256=p_sha256,
    finished_at=v_now,lease_token=NULL,lease_expires_at=NULL
    WHERE j.id=v_job.id;
  RETURN v_key;
END
$$;

CREATE OR REPLACE FUNCTION public.affiliate_worker_fail(
  p_job_id uuid,p_lease_token uuid,p_error_code text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_job affiliate_private.render_jobs%ROWTYPE;
BEGIN
  IF auth.role() IS DISTINCT FROM 'service_role' THEN
    RAISE EXCEPTION 'Worker autorizado obrigatorio' USING ERRCODE='42501';
  END IF;
  IF p_error_code IS NULL OR p_error_code NOT IN (
    'invalid_input','render_failed','storage_failed','timeout','worker_failed'
  ) THEN
    RAISE EXCEPTION 'Codigo de erro invalido' USING ERRCODE='22023';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(819320123888::bigint);
  SELECT * INTO v_job FROM affiliate_private.render_jobs j
    WHERE j.id=p_job_id AND j.status='running'
      AND j.lease_token=p_lease_token AND j.lease_expires_at > clock_timestamp()
    FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  DELETE FROM affiliate_private.renders r
    WHERE r.id=ANY(v_job.reservation_ids) AND r.user_id=v_job.user_id
      AND r.status='reserved';
  UPDATE affiliate_private.render_jobs j SET
    status='failed',error_code=p_error_code,finished_at=clock_timestamp(),
    lease_token=NULL,lease_expires_at=NULL WHERE j.id=v_job.id;
  RETURN true;
END
$$;

-- Newly created SECURITY DEFINER RPCs would otherwise be executable by PUBLIC.
REVOKE ALL ON FUNCTION public.affiliate_enqueue_job(uuid,text,text) FROM PUBLIC,anon;
REVOKE ALL ON FUNCTION public.affiliate_job_status(uuid) FROM PUBLIC,anon;
REVOKE ALL ON FUNCTION public.affiliate_my_jobs(integer) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.affiliate_enqueue_job(uuid,text,text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.affiliate_job_status(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.affiliate_my_jobs(integer) TO authenticated;
REVOKE ALL ON FUNCTION public.affiliate_worker_claim() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.affiliate_worker_heartbeat(uuid,uuid) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.affiliate_worker_finish(uuid,uuid,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.affiliate_worker_fail(uuid,uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.affiliate_worker_claim() TO service_role;
GRANT EXECUTE ON FUNCTION public.affiliate_worker_heartbeat(uuid,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.affiliate_worker_finish(uuid,uuid,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.affiliate_worker_fail(uuid,uuid,text) TO service_role;
COMMIT;
