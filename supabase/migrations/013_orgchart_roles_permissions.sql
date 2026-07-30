-- 013_orgchart_roles_permissions.sql
-- Unify roles, access levels, and per-view scopes in the orgchart table.
-- This makes orgchart the single source of truth for people, roles, and permissions.

BEGIN;

-- ══════════════════════════════════════════════════════════════════════════════
-- 1. NEW COLUMNS
-- ══════════════════════════════════════════════════════════════════════════════

-- Access level (determines global permission tier)
ALTER TABLE orgchart ADD COLUMN access_level TEXT NOT NULL DEFAULT 'tree';

-- Per-view scopes: none = hidden, self = own data, team = subtree, all = everything
-- General
ALTER TABLE orgchart ADD COLUMN scope_general        TEXT NOT NULL DEFAULT 'all';
-- Execution
ALTER TABLE orgchart ADD COLUMN scope_alerts          TEXT NOT NULL DEFAULT 'self';
ALTER TABLE orgchart ADD COLUMN scope_pipeline        TEXT NOT NULL DEFAULT 'self';
ALTER TABLE orgchart ADD COLUMN scope_benchmark       TEXT NOT NULL DEFAULT 'self';
ALTER TABLE orgchart ADD COLUMN scope_performance     TEXT NOT NULL DEFAULT 'self';
-- Team
ALTER TABLE orgchart ADD COLUMN scope_forecast        TEXT NOT NULL DEFAULT 'team';
ALTER TABLE orgchart ADD COLUMN scope_one_one         TEXT NOT NULL DEFAULT 'self';
ALTER TABLE orgchart ADD COLUMN scope_team_analytics  TEXT NOT NULL DEFAULT 'team';
ALTER TABLE orgchart ADD COLUMN scope_orgchart        TEXT NOT NULL DEFAULT 'all';
-- Product
ALTER TABLE orgchart ADD COLUMN scope_uplift          TEXT NOT NULL DEFAULT 'self';
ALTER TABLE orgchart ADD COLUMN scope_insights        TEXT NOT NULL DEFAULT 'self';
-- Admin
ALTER TABLE orgchart ADD COLUMN scope_admin           TEXT NOT NULL DEFAULT 'none';
-- Partners (shared across partner_pipeline, partner_forecast, partner_analytics)
ALTER TABLE orgchart ADD COLUMN visible_partners      TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE orgchart ADD COLUMN scope_partners        TEXT NOT NULL DEFAULT 'all';

-- ══════════════════════════════════════════════════════════════════════════════
-- 2. NORMALIZE ROLES TO LOWERCASE (before adding CHECK constraint)
-- ══════════════════════════════════════════════════════════════════════════════

-- All AE
UPDATE orgchart SET role = 'ae' WHERE role = 'AE';
-- All PAE
UPDATE orgchart SET role = 'pae' WHERE role = 'PAE';
-- All PBD
UPDATE orgchart SET role = 'pbd' WHERE role = 'PBD';
-- All SDR
UPDATE orgchart SET role = 'sdr' WHERE role = 'SDR';
-- All PDM
UPDATE orgchart SET role = 'pdm' WHERE role = 'PDM';
-- Directors
UPDATE orgchart SET role = 'director' WHERE role = 'Director';
-- Head
UPDATE orgchart SET role = 'head' WHERE role = 'Head';
-- Country Manager
UPDATE orgchart SET role = 'country_manager' WHERE role = 'Country_Manager';
-- Generic Manager label
UPDATE orgchart SET role = 'manager' WHERE role = 'Manager';

-- Split partner TLs into pae_tl / pbd_tl (4 people)
UPDATE orgchart SET role = 'pae_tl' WHERE email = 'nunzio.fumo@factorial.co';
UPDATE orgchart SET role = 'pae_tl' WHERE email = 'gabriel.lichtenstein@factorial.co';
UPDATE orgchart SET role = 'pbd_tl' WHERE email = 'giacomo.torresi@factorial.co';
UPDATE orgchart SET role = 'pbd_tl' WHERE email = 'fiona.durr@factorial.co';

-- Remaining TLs (direct sales, Mexico) → lowercase
UPDATE orgchart SET role = 'tl' WHERE role = 'TL';

-- ══════════════════════════════════════════════════════════════════════════════
-- 3. CHECK CONSTRAINTS (after data is normalized)
-- ══════════════════════════════════════════════════════════════════════════════

ALTER TABLE orgchart ADD CONSTRAINT chk_access_level
  CHECK (access_level IN ('admin', 'manager', 'visitor', 'tree'));

ALTER TABLE orgchart ADD CONSTRAINT chk_role
  CHECK (role IN (
    'ae', 'pae', 'pbd', 'sdr', 'pdm', 'pre_sales',
    'tl', 'pae_tl', 'pbd_tl',
    'director', 'head', 'country_manager', 'c_level',
    'manager'
  ));

ALTER TABLE orgchart ADD CONSTRAINT chk_scope_general       CHECK (scope_general       IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_alerts        CHECK (scope_alerts        IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_pipeline      CHECK (scope_pipeline      IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_benchmark     CHECK (scope_benchmark     IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_performance   CHECK (scope_performance   IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_forecast      CHECK (scope_forecast      IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_one_one       CHECK (scope_one_one       IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_team_analytics CHECK (scope_team_analytics IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_orgchart      CHECK (scope_orgchart      IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_uplift        CHECK (scope_uplift        IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_insights      CHECK (scope_insights      IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_admin         CHECK (scope_admin         IN ('none','self','team','all'));
ALTER TABLE orgchart ADD CONSTRAINT chk_scope_partners      CHECK (scope_partners      IN ('none','self','team','all'));

-- ══════════════════════════════════════════════════════════════════════════════
-- 4. ACCESS LEVELS
-- ══════════════════════════════════════════════════════════════════════════════

-- Admins (3)
UPDATE orgchart SET access_level = 'admin', scope_admin = 'all'
  WHERE email IN (
    'guillem.catalan@factorial.co',
    'albert.fernandez@factorial.co',
    'marc.macia@factorial.co'
  );

-- Managers (5) — see everything, read-only, not in tree
UPDATE orgchart SET access_level = 'manager'
  WHERE email IN (
    'alex.martinez@factorial.co',
    'domenica.galarza@factorial.co',
    'lucas.siroo@factorial.co',
    'oriol.delmoral@factorial.co',
    'pau.cruz@factorial.co'
  );

-- Everyone else stays 'tree' (the default)

-- ══════════════════════════════════════════════════════════════════════════════
-- 5. DELETE samuel.fernandez
-- ══════════════════════════════════════════════════════════════════════════════

DELETE FROM orgchart WHERE email = 'samuel.fernandez@factorial.co';

COMMIT;
