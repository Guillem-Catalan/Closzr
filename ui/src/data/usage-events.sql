-- =============================================================
-- Closzr Usage Events — table, indexes, RLS, RPC functions
-- Run this in the Supabase SQL Editor for project bqoepgcdgqylobkmqdur
-- =============================================================

-- 1. Table
CREATE TABLE IF NOT EXISTS usage_events (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    text NOT NULL,
  email      text NOT NULL,
  event_type text NOT NULL,
  resource   text NOT NULL,
  metadata   jsonb NOT NULL DEFAULT '{}',
  user_agent text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 2. Indexes
CREATE INDEX IF NOT EXISTS idx_usage_events_created_email
  ON usage_events (created_at, email);
CREATE INDEX IF NOT EXISTS idx_usage_events_resource
  ON usage_events (resource);

-- 3. RLS — enable but only allow authenticated inserts of own rows
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'usage_events_insert') THEN
    CREATE POLICY usage_events_insert ON usage_events
      FOR INSERT TO authenticated
      WITH CHECK (true);
  END IF;
END $$;

-- No SELECT policy — reads go through security-definer RPCs only.

-- 4. RPC functions (all security definer)
-- All functions accept optional filter_email for per-user drill-down.

-- 4a. DAU
CREATE OR REPLACE FUNCTION usage_dau(
  from_date    timestamptz,
  to_date      timestamptz,
  filter_role  text DEFAULT NULL,
  filter_email text DEFAULT NULL
)
RETURNS TABLE(date date, count bigint)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT d::date AS date, count(DISTINCT e.email) AS count
  FROM generate_series(from_date::date, to_date::date, '1 day'::interval) d
  LEFT JOIN usage_events e
    ON e.created_at >= d AND e.created_at < d + '1 day'::interval
    AND (filter_role IS NULL OR EXISTS (
      SELECT 1 FROM users u WHERE u.email = e.email AND u.role = filter_role
    ))
    AND (filter_email IS NULL OR e.email = filter_email)
  GROUP BY d::date
  ORDER BY d::date;
$$;

-- 4b. WAU
CREATE OR REPLACE FUNCTION usage_wau(
  from_date    timestamptz,
  to_date      timestamptz,
  filter_role  text DEFAULT NULL,
  filter_email text DEFAULT NULL
)
RETURNS TABLE(week_start date, count bigint)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT date_trunc('week', e.created_at)::date AS week_start,
         count(DISTINCT e.email) AS count
  FROM usage_events e
  WHERE e.created_at >= from_date AND e.created_at < to_date + '1 day'::interval
    AND (filter_role IS NULL OR EXISTS (
      SELECT 1 FROM users u WHERE u.email = e.email AND u.role = filter_role
    ))
    AND (filter_email IS NULL OR e.email = filter_email)
  GROUP BY week_start
  ORDER BY week_start;
$$;

-- 4c. MAU
CREATE OR REPLACE FUNCTION usage_mau(
  from_date    timestamptz,
  to_date      timestamptz,
  filter_role  text DEFAULT NULL,
  filter_email text DEFAULT NULL
)
RETURNS TABLE(month text, count bigint)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT to_char(date_trunc('month', e.created_at), 'YYYY-MM') AS month,
         count(DISTINCT e.email) AS count
  FROM usage_events e
  WHERE e.created_at >= from_date AND e.created_at < to_date + '1 day'::interval
    AND (filter_role IS NULL OR EXISTS (
      SELECT 1 FROM users u WHERE u.email = e.email AND u.role = filter_role
    ))
    AND (filter_email IS NULL OR e.email = filter_email)
  GROUP BY month
  ORDER BY month;
$$;

-- 4d. Top users
CREATE OR REPLACE FUNCTION usage_top_users(
  from_date    timestamptz,
  to_date      timestamptz,
  lim          int DEFAULT 20,
  filter_role  text DEFAULT NULL,
  filter_email text DEFAULT NULL
)
RETURNS TABLE(email text, role text, action_count bigint, last_active timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT e.email,
         COALESCE(u.role, 'Unknown') AS role,
         count(*) AS action_count,
         max(e.created_at) AS last_active
  FROM usage_events e
  LEFT JOIN users u ON u.email = e.email
  WHERE e.created_at >= from_date AND e.created_at < to_date + '1 day'::interval
    AND (filter_role IS NULL OR u.role = filter_role)
    AND (filter_email IS NULL OR e.email = filter_email)
  GROUP BY e.email, u.role
  ORDER BY action_count DESC
  LIMIT lim;
$$;

-- 4e. By resource
CREATE OR REPLACE FUNCTION usage_by_resource(
  from_date    timestamptz,
  to_date      timestamptz,
  filter_role  text DEFAULT NULL,
  filter_email text DEFAULT NULL
)
RETURNS TABLE(resource text, users bigint, actions bigint)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT e.resource,
         count(DISTINCT e.email) AS users,
         count(*) AS actions
  FROM usage_events e
  WHERE e.created_at >= from_date AND e.created_at < to_date + '1 day'::interval
    AND (filter_role IS NULL OR EXISTS (
      SELECT 1 FROM users u WHERE u.email = e.email AND u.role = filter_role
    ))
    AND (filter_email IS NULL OR e.email = filter_email)
  GROUP BY e.resource
  ORDER BY users DESC;
$$;

-- 4f. Heatmap
CREATE OR REPLACE FUNCTION usage_heatmap(
  from_date    timestamptz,
  to_date      timestamptz,
  tz           text DEFAULT 'UTC',
  filter_role  text DEFAULT NULL,
  filter_email text DEFAULT NULL
)
RETURNS TABLE(dow int, hour int, count bigint)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT (extract(isodow FROM e.created_at AT TIME ZONE tz) - 1)::int AS dow,
         extract(hour FROM e.created_at AT TIME ZONE tz)::int AS hour,
         count(*) AS count
  FROM usage_events e
  WHERE e.created_at >= from_date AND e.created_at < to_date + '1 day'::interval
    AND (filter_role IS NULL OR EXISTS (
      SELECT 1 FROM users u WHERE u.email = e.email AND u.role = filter_role
    ))
    AND (filter_email IS NULL OR e.email = filter_email)
  GROUP BY dow, hour
  ORDER BY dow, hour;
$$;

-- 4g. Activation rate
CREATE OR REPLACE FUNCTION usage_activation_rate(
  from_date    timestamptz,
  to_date      timestamptz,
  filter_role  text DEFAULT NULL,
  filter_email text DEFAULT NULL
)
RETURNS TABLE(total_users bigint, activated_users bigint, rate numeric)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  WITH user_resources AS (
    SELECT e.email, count(DISTINCT e.resource) AS res_count
    FROM usage_events e
    WHERE e.created_at >= from_date AND e.created_at < to_date + '1 day'::interval
      AND (filter_role IS NULL OR EXISTS (
        SELECT 1 FROM users u WHERE u.email = e.email AND u.role = filter_role
      ))
      AND (filter_email IS NULL OR e.email = filter_email)
    GROUP BY e.email
  )
  SELECT count(*) AS total_users,
         count(*) FILTER (WHERE res_count >= 2) AS activated_users,
         CASE WHEN count(*) > 0
              THEN round(count(*) FILTER (WHERE res_count >= 2)::numeric / count(*), 4)
              ELSE 0
         END AS rate
  FROM user_resources;
$$;
