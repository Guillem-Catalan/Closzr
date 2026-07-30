-- 015_orgchart_rls_admin_only.sql
-- Replace the open authenticated_write policy with admin-only write policies.
-- Uses separate INSERT/UPDATE/DELETE policies (not FOR ALL) to avoid
-- polluting SELECT with the USING clause.
-- Uses auth.jwt() ->> 'email' instead of querying auth.users to avoid
-- permission issues with the auth schema.

BEGIN;

-- Remove the old open-write policy (anyone authenticated could write)
DROP POLICY IF EXISTS authenticated_write ON orgchart;

-- Admin-only write: separate policies per operation
CREATE POLICY admin_insert ON orgchart FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM orgchart
      WHERE email = (auth.jwt() ->> 'email')
        AND access_level = 'admin'
    )
  );

CREATE POLICY admin_update ON orgchart FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM orgchart
      WHERE email = (auth.jwt() ->> 'email')
        AND access_level = 'admin'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM orgchart
      WHERE email = (auth.jwt() ->> 'email')
        AND access_level = 'admin'
    )
  );

CREATE POLICY admin_delete ON orgchart FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM orgchart
      WHERE email = (auth.jwt() ->> 'email')
        AND access_level = 'admin'
    )
  );

COMMIT;
