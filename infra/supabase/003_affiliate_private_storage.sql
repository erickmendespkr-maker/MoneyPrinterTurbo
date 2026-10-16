-- Private object bucket for Afiliados Creator inputs and completed media.
-- Run after 001 and 002, in the Supabase SQL Editor. Not applied automatically.
-- Do NOT create public policies for this bucket: the verified backend and
-- worker use the service_role credential kept in server-side secrets only.
BEGIN;
INSERT INTO storage.buckets (
  id, name, public, file_size_limit, allowed_mime_types
) VALUES (
  'afiliados-private', 'afiliados-private', false,
  367001600, ARRAY['application/zip', 'video/mp4']::text[]
)
ON CONFLICT (id) DO UPDATE SET
  public = false,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;
-- Storage ownership is checked on every signed download by the server's
-- authenticated affiliate_job_status RPC, not by a user-provided file path.
-- No SELECT/INSERT/UPDATE/DELETE policy is granted to anon/authenticated here.
-- Audit existing broad storage policies before creating this bucket on a
-- project shared with other applications.
COMMIT;
