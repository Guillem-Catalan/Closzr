-- 015: Restrict orgchart writes to admin users only.
-- The previous policy (authenticated_write) allowed ANY authenticated user
-- to INSERT/UPDATE/DELETE orgchart rows — a privilege escalation risk.
-- Now only users whose email has access_level='admin' in orgchart can write.
-- Edge functions (service_role) are unaffected.

DROP POLICY IF EXISTS authenticated_write ON orgchart;

CREATE POLICY admin_write ON orgchart
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM orgchart
      WHERE email = (SELECT email FROM auth.users WHERE id = auth.uid())
        AND access_level = 'admin'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM orgchart
      WHERE email = (SELECT email FROM auth.users WHERE id = auth.uid())
        AND access_level = 'admin'
    )
  );
