-- Afiliados Creator — READ-ONLY Supabase deployment preflight.
-- Run on an explicitly selected DEVELOPMENT project, NEVER assume any
-- connected Supabase project belongs to Afiliados Creator.
-- No tables or schema are changed by these queries.

-- 1. Which migrations, if any, were already applied?
SELECT
  to_regclass('affiliate_private.subscriptions') IS NOT NULL
    AS quotas_table_exists,
  to_regclass('affiliate_private.render_jobs') IS NOT NULL
    AS worker_jobs_table_exists,
  to_regclass('affiliate_private.free_attempts') IS NOT NULL
    AS free_attempt_budget_exists;

-- 2. The private schema must not be usable by public-facing roles.
SELECT
  rolname AS role_name,
  has_schema_privilege(rolname, 'affiliate_private', 'USAGE')
    AS has_private_schema_usage
FROM pg_roles
WHERE rolname IN ('anon', 'authenticated', 'service_role')
  AND to_regnamespace('affiliate_private') IS NOT NULL
ORDER BY rolname;

-- 3. No public-facing role may directly complete a video reservation.
-- NULL signatures indicate that migration 001/002 was not applied yet.
SELECT
  function_name,
  to_regprocedure(function_name) IS NOT NULL AS exists_now,
  CASE WHEN to_regprocedure(function_name) IS NULL THEN NULL
       ELSE has_function_privilege('authenticated', to_regprocedure(function_name), 'EXECUTE')
  END AS authenticated_can_execute,
  CASE WHEN to_regprocedure(function_name) IS NULL THEN NULL
       ELSE has_function_privilege('anon', to_regprocedure(function_name), 'EXECUTE')
  END AS anon_can_execute
FROM (VALUES
  ('public.affiliate_reserve_videos(integer)'),
  ('public.affiliate_complete_videos(uuid[])'),
  ('public.affiliate_release_videos(uuid[])'),
  ('public.affiliate_enqueue_job(uuid,text,text)'),
  ('public.affiliate_job_status(uuid)'),
  ('public.affiliate_my_jobs(integer)'),
  ('public.affiliate_worker_claim()'),
  ('public.affiliate_worker_heartbeat(uuid,uuid)'),
  ('public.affiliate_worker_finish(uuid,uuid,text,bigint,bigint)'),
  ('public.affiliate_worker_fail(uuid,uuid,text)')
) AS f(function_name);

-- 4. Inspect the bucket only if Storage exists; do not change policies.
SELECT name, public, file_size_limit
FROM storage.buckets
WHERE id='afiliados-private';

-- 5. Current active work and completion timing.
-- Run this final query ONLY after migration 002 was applied, because
-- the render_jobs relation does not exist on an empty project.
-- SELECT status,count(*) AS jobs,
--        round(avg(worker_wall_ms)::numeric/1000,2) AS avg_seconds
-- FROM affiliate_private.render_jobs GROUP BY status ORDER BY status;

-- Expected result after planned migrations:
--   quota/jobs/attempts table: true
--   anon/authenticated private schema usage: false
--   authenticated may execute enqueue_job, job_status, my_jobs.
--   anon/authenticated must NEVER execute worker RPCs or raw reserve,
--     complete or release RPCs.
--   bucket public: false.
