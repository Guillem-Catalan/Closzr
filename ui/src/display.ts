/* ============================================================
   CLOSZR — Display layer

   Everything here reads from config.generated.json (generated
   from config.py by scripts/generate_ui_config.py).

   Change config.py → run generator → UI updates.
   Nothing hardcoded here except pure UI concepts (icon names,
   BANT label translations, tab definitions).
   ============================================================ */

import CFG from "./config.generated.json";

// ---- Re-export config sections for convenience ----
export const CONFIG = CFG;

// ---- HubSpot ----
export const HUBSPOT_ACCOUNT_ID = CFG.hubspot_account_id;

export function hubspotDealUrl(hsId: string): string {
  return `https://app.hubspot.com/contacts/${HUBSPOT_ACCOUNT_ID}/deal/${hsId}`;
}

// ---- Teams (from config.py) ----
export const TEAMS = CFG.teams;
export const ACTIVE_TEAMS = CFG.active_teams;

export function getActiveTeamNames(): string[] {
  return CFG.active_teams;
}

export function getAllTeamNames(): string[] {
  return Object.keys(CFG.teams);
}

// ---- Owner names (email → display name, from config.py HUBSPOT_OWNER_IDS) ----
export const OWNER_NAMES: Record<string, string> = CFG.owner_names;

export function ownerDisplayName(email: string): string {
  return OWNER_NAMES[email] || email.split("@")[0].split(".").map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

// ---- Known users for auto-signup (from config.py orgchart) ----
export const KNOWN_USERS: Record<string, { role: string; team: string }> = CFG.known_users;

// ---- Stages (from config.py STAGE_DISPLAY + PARSER_CONFIG) ----
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

// ---- Pipeline funnel (from config.py stage categories) ----
export const PIPELINE_FUNNEL = CFG.funnel;
export const PIPELINE_ASIDE = CFG.funnel_aside;

// ---- Stale thresholds (from config.py PARSER_CONFIG) ----
export const STALE_THRESHOLDS: Record<string, number> = CFG.stale_thresholds;
export const STALE_DEFAULT = CFG.stale_default;

// ---- Closed stages (from config.py STAGE_WON + STAGE_LOST) ----
export const CLOSED_WON_STAGES: string[] = CFG.stages.categories.won;
export const CLOSED_LOST_STAGES: string[] = CFG.stages.categories.lost;

// ---- Pipeline → valid open stages (from config.py PIPELINE_STAGES) ----
export const PIPELINE_STAGES: Record<string, string[]> = CFG.pipeline_stages;

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

// ---- Admin: roles + scopes + tabs (pure UI) ----
export const ADMIN_ROLES = ["Admin", "Manager", "Director", "TL", "PAE", "PBD", "AE", "SDR"];
export const ADMIN_SCOPES = [
  { value: "all", label: "Todo" },
  { value: "team", label: "Su equipo" },
  { value: "self", label: "Solo él/ella" },
  { value: "custom", label: "Custom" },
];
export const ALL_TABS = [
  { key: "general", label: "General" },
  { key: "todos", label: "To Do's" },
  { key: "deals", label: "Pipeline" },
  { key: "benchmark", label: "Benchmark" },
  { key: "alerts", label: "Alerts" },
  { key: "forecast", label: "Forecast" },
  { key: "oneone", label: "1:1" },
  { key: "uplift", label: "Uplift" },
];
