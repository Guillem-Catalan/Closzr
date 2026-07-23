/* ============================================================
   CLOSZR — Display layer

   Everything here reads from config.generated.json (generated
   from schema.py + org.py + config2.py by scripts/generate_ui_config.py).

   Change the 3-file architecture → run generator → UI updates.
   Nothing hardcoded here except pure UI concepts (icon names,
   BANT label translations, tab definitions).
   ============================================================ */

import CFG from "./config.generated.json";

// ---- Re-export config sections for convenience ----
export const CONFIG = CFG;

// ---- CRM ----
export const CRM_NAME: string = CFG.crm_name;
export const CRM_SHORT: string = CFG.crm_short;
export const CRM_ACCOUNT_ID: string = CFG.crm_account_id;
export const HUBSPOT_ACCOUNT_ID = CFG.hubspot_account_id;
export const CRM_FORECAST_CATEGORIES: string[] = CFG.crm_forecast_categories;

export function crmDealUrl(hsId: string): string {
  return `https://app.hubspot.com/contacts/${CRM_ACCOUNT_ID}/deal/${hsId}`;
}
export const hubspotDealUrl = crmDealUrl;

// ---- Organization ----
export const ORG_NAME: string = CFG.org_name;
export const ORG_DOMAINS: string[] = CFG.org_domains;

// ---- Teams ----
export const TEAMS = CFG.teams;
export const ACTIVE_TEAMS = CFG.active_teams;

export function getActiveTeamNames(): string[] {
  return CFG.active_teams;
}

export function getAllTeamNames(): string[] {
  return Object.keys(CFG.teams);
}

// ---- Owner names (email → display name) ----
export const OWNER_NAMES: Record<string, string> = CFG.owner_names;

export function ownerDisplayName(email: string): string {
  return OWNER_NAMES[email] || email.split("@")[0].split(".").map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

// ---- Known users for auto-signup ----
export const KNOWN_USERS: Record<string, { role: string; team: string }> = CFG.known_users;

// ---- Stages ----
export const STAGE_DISPLAY: Record<string, { short: string; abbr: string }> = CFG.stages.display;
export const STAGE_TONES: Record<string, string> = CFG.stages.tones;
export const MACRO_STAGE_MAP: Record<string, string> = CFG.stages.macro_stage_map;
export const STAGE_CATEGORIES = CFG.stages.categories;

export function shortStage(stage: string): string {
  const entry = STAGE_DISPLAY[stage];
  return entry ? entry.short : stage;
}

export function stageAbbr(stage: string): string {
  const entry = STAGE_DISPLAY[stage];
  return entry ? entry.abbr : stage.slice(0, 3).toUpperCase();
}

export function stageTone(stage: string): string {
  return STAGE_TONES[stage] || "ink";
}

// ---- Won / Lost display labels ----
export const WON_DISPLAY_LABEL: string = CFG.won_display_label;
export const LOST_DISPLAY_LABEL: string = CFG.lost_display_label;

// ---- Pipeline funnel ----
export const PIPELINE_FUNNEL = CFG.funnel;
export const PIPELINE_ASIDE = CFG.funnel_aside;

// ---- Stale thresholds ----
export const STALE_THRESHOLDS: Record<string, number> = CFG.stale_thresholds;
export const STALE_DEFAULT = CFG.stale_default;

// ---- Closed stages ----
export const CLOSED_WON_STAGES: string[] = CFG.stages.categories.won;
export const CLOSED_LOST_STAGES: string[] = CFG.stages.categories.lost;

// ---- Pipeline → valid open stages ----
export const PIPELINE_STAGES: Record<string, string[]> = CFG.pipeline_stages;

// ---- Team → pipeline mapping ----
export const TEAM_PIPELINES: Record<string, string[]> = CFG.team_pipelines;

// ---- DS team hierarchy (parent → children) ----
export const TEAM_HIERARCHY: Record<string, string[]> = CFG.team_hierarchy;

// ---- Per-pipeline stage roadmaps ----
export const STAGE_ROADMAPS: Record<string, Array<{ key: string; label: string }>> = CFG.stage_roadmaps;

// ---- Lost reasons ----
export const LOST_REASONS: string[] = CFG.lost_reasons;

// ---- Managers ----
export const MANAGERS: string[] = CFG.managers;

// ---- MEDDIC axes ----
export type MeddicAxis = { key: string; short: string; label: string };
export const MEDDIC_AXES: MeddicAxis[] = CFG.meddic_axes;
export const MEDDIC_KEYS = MEDDIC_AXES.map(a => a.key);
export const METHODOLOGY_NAME: string = CFG.methodology_name;

// ---- Short labels for won/lost categories ----
export const WON_LABEL: string = CFG.won_label;
export const LOST_LABEL: string = CFG.lost_label;

// ---- Default role for unknown users ----
export const DEFAULT_ROLE: string = CFG.default_role;

// ---- Role labels ----
export const ROLE_LABELS: Record<string, string> = CFG.role_labels;
export const ADMIN_ROLES = Object.keys(ROLE_LABELS);

// ---- Momentum / Confidence (pure UI display) ----
export const MOMENTUM_DISPLAY: Record<string, { icon: string; color: string }> = {
  accelerating: { icon: "▲", color: "var(--green)" },
  stable: { icon: "→", color: "var(--amber)" },
  decelerating: { icon: "▼", color: "var(--red)" },
};

export const CONFIDENCE_TONE: Record<string, string> = {
  high: "green", medium: "amber", low: "red",
};

// ---- Action type icons (pure UI) ----
export const ACTION_TYPE_ICON: Record<string, string> = {
  CALL: "phone", EMAIL: "mail", ROI: "calculator",
  SLIDES: "presentation", BATTLECARD: "shield",
  PREP: "sparkle", MEETING: "calendar",
};

// ---- Bucket display (pure UI) ----
export const BUCKET_STYLE: Record<string, { label: string; tone: string }> = {
  forecast: { label: "Forecast", tone: "green" },
  pushable: { label: "Pushable", tone: "amber" },
  next_month: { label: "Próx. mes", tone: "blue" },
  blocker: { label: "Blocker", tone: "red" },
  pipeline: { label: "Pipeline", tone: "ink" },
};

// ---- BANT display (pure UI translations) ----
export function bantTone(status: string | null): string {
  if (!status) return "ink";
  const s = status.toLowerCase();
  if (s === "confirmed") return "green";
  if (s.includes("partial")) return "amber";
  return "red";
}

export function bantLabel(status: string | null): string {
  if (!status) return "Sin datos";
  const map: Record<string, string> = {
    confirmed: "Confirmado", partially_confirmed: "Parcial",
    not_confirmed: "Sin confirmar", not_discussed: "Sin validar",
  };
  return map[status.toLowerCase()] || status;
}

// ---- Admin: scopes + tabs (pure UI) ----
export const ADMIN_SCOPES = [
  { value: "all", label: "Todo" },
  { value: "team", label: "Su equipo" },
  { value: "self", label: "Solo él/ella" },
  { value: "custom", label: "Custom" },
];
export const ALL_TABS = [
  { key: "general", label: "General" },
  { key: "todos", label: "Alerts" },
  { key: "deals", label: "Pipeline" },
  { key: "benchmark", label: "Benchmark" },
  { key: "performance", label: "Performance" },
  { key: "forecast", label: "Forecast" },
  { key: "oneone", label: "1:1" },
  { key: "team-analytics", label: "Analytics" },
  { key: "orgchart", label: "Orgchart" },
  { key: "uplift", label: "Uplift" },
  { key: "insights", label: "Insights" },
  { key: "partner-pipeline", label: "Pipeline" },
  { key: "partner-forecast", label: "Forecast" },
  { key: "partner-analytics", label: "Analytics" },
];
