-- 017_orgchart_visitor_self_insert.sql
-- Allow authenticated users to insert THEMSELVES as visitor when they
-- don't exist in orgchart yet. Prevents ensureInOrgchart() from being
-- silently blocked by admin-only RLS (migration 015).

BEGIN;

CREATE POLICY visitor_self_insert ON orgchart FOR INSERT TO authenticated
  WITH CHECK (
    email = lower(auth.jwt() ->> 'email')
    AND access_level = 'visitor'
    AND scope_admin = 'none'
    AND NOT EXISTS (SELECT 1 FROM orgchart WHERE email = lower(auth.jwt() ->> 'email'))
  );

COMMIT;
