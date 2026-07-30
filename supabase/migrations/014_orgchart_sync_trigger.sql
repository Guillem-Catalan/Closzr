-- Automatic sync: any change to orgchart → triggers GitHub Action
-- that runs sync_orgchart.py → regenerates org_people.py → auto-commit
--
-- Requires:
--   1. pg_net extension (enabled by default in Supabase)
--   2. A GitHub Personal Access Token stored in vault:
--      INSERT INTO vault.secrets (name, secret)
--      VALUES ('github_pat', 'ghp_xxxxxxxxxxxx');

CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

CREATE OR REPLACE FUNCTION notify_orgchart_sync() RETURNS trigger AS $$
DECLARE
  github_token TEXT;
BEGIN
  SELECT decrypted_secret INTO github_token
    FROM vault.decrypted_secrets
    WHERE name = 'github_pat'
    LIMIT 1;

  IF github_token IS NULL THEN
    RAISE WARNING 'github_pat not found in vault — skipping orgchart sync trigger';
    RETURN NULL;
  END IF;

  PERFORM net.http_post(
    url := 'https://api.github.com/repos/Guillem-Catalan/Closzr/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || github_token,
      'Accept', 'application/vnd.github.v3+json',
      'Content-Type', 'application/json',
      'User-Agent', 'supabase-orgchart-trigger'
    ),
    body := jsonb_build_object(
      'event_type', 'orgchart_sync'
    )
  );

  RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER orgchart_sync_trigger
  AFTER INSERT OR UPDATE OR DELETE ON orgchart
  FOR EACH STATEMENT
  EXECUTE FUNCTION notify_orgchart_sync();
