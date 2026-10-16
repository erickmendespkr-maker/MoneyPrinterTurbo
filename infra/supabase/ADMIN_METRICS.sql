-- Afiliados Creator: read-only operational queries (not applied automatically).
-- Run as an authorized database administrator in Supabase SQL Editor.
-- Never expose this file or its query results in a public dashboard.

-- Last 30 days: completed jobs, chargeable videos, average processing
-- duration, and total output storage by plan. These are RESOURCE metrics,
-- not actual charges. Server idle time, third-party AI usage and fees
-- must be incorporated separately.
SELECT
  j.plan_at_enqueue AS plan,
  COUNT(*) AS completed_jobs,
  SUM(cardinality(j.reservation_ids)) AS chargeable_videos,
  ROUND(AVG(j.worker_wall_ms)::numeric / 1000, 2) AS mean_worker_seconds_per_job,
  ROUND(SUM(j.worker_wall_ms)::numeric / 3600000, 2) AS worker_hours_total,
  ROUND(SUM(j.output_bytes)::numeric / 1073741824, 3) AS output_gib_total,
  ROUND(AVG(j.output_bytes)::numeric / 1048576, 2) AS mean_output_mib
FROM affiliate_private.render_jobs j
WHERE j.status = 'completed'
  AND j.finished_at >= clock_timestamp() - INTERVAL '30 days'
GROUP BY j.plan_at_enqueue
ORDER BY j.plan_at_enqueue;

-- Day-by-day: failures, successful jobs, and queued/running backlog.
SELECT
  (j.created_at AT TIME ZONE 'America/Sao_Paulo')::date AS created_date_brasilia,
  COUNT(*) FILTER (WHERE j.status = 'completed') AS completed,
  COUNT(*) FILTER (WHERE j.status = 'failed') AS failed,
  COUNT(*) FILTER (WHERE j.status = 'queued') AS queued,
  COUNT(*) FILTER (WHERE j.status = 'running') AS running
FROM affiliate_private.render_jobs j
WHERE j.created_at >= clock_timestamp() - INTERVAL '14 days'
GROUP BY 1 ORDER BY 1 DESC;

-- Use an explicit service budget rather than inventing a "per-second API"
-- price. For example, if a dedicated server costs R$ X/month and processes
-- N completed videos in that month, allocated server cost per completed
-- video is approximately X/N BRL. Add AI, storage, taxes and payment fees.
-- Wall-time is not equal to billed vCPU time or total server expense.
