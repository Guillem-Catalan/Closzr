/* ============================================================
   CLOSZR — Filter logic

   Derives team/rep options from DATA, not from config.
   Views call these functions to get dropdown options and
   to match rows against active filters.
   ============================================================ */

import type { DealRow, ActionItem } from "./store";
import { TEAM_HIERARCHY, ORG_DOMAINS } from "../display";

export function expandTeam(team: string): Set<string> {
  const result = new Set<string>();
  const walk = (t: string) => {
    result.add(t);
    for (const child of (TEAM_HIERARCHY[t] || [])) walk(child);
  };
  walk(team);
  return result;
}

export function expandTeams(teams: Set<string>): Set<string> | null {
  if (teams.size === 0) return null;
  const result = new Set<string>();
  for (const t of teams) for (const child of expandTeam(t)) result.add(child);
  return result;
}

// ---- Normalize for accent-insensitive comparison ----
export function normalize(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export function repNameToEmail(name: string): string {
  return normalize(name).replace(/ /g, ".") + "@" + ORG_DOMAINS[0];
}

// ---- Derive options from data ----

export function distinctTeams(rows: DealRow[]): string[] {
  const set = new Set<string>();
  for (const r of rows) if (r.team) set.add(r.team);
  for (const [parent, children] of Object.entries(TEAM_HIERARCHY)) {
    if (children.some(c => set.has(c))) set.add(parent);
  }
  return [...set].sort();
}

export function distinctPipelines(rows: { pipeline?: string }[]): string[] {
  const set = new Set<string>();
  for (const r of rows) if (r.pipeline) set.add(r.pipeline);
  return [...set].sort();
}

export function distinctOwners(rows: DealRow[], team?: string): string[] {
  const teamSet = team ? expandTeam(team) : null;
  const set = new Set<string>();
  for (const r of rows) {
    if (teamSet && !teamSet.has(r.team || "")) continue;
    if (r.owner && r.owner !== "—") set.add(r.owner);
  }
  return [...set].sort();
}

export function distinctTeamsFromActions(actions: ActionItem[]): string[] {
  const set = new Set<string>();
  for (const a of actions) if (a.team) set.add(a.team);
  return [...set].sort();
}

export function distinctOwnersFromActions(actions: ActionItem[], team?: string): string[] {
  const set = new Set<string>();
  for (const a of actions) {
    if (team && a.team !== team) continue;
    if (a.dealOwner && a.dealOwner !== "—") set.add(a.dealOwner);
  }
  return [...set].sort();
}

// ---- Match functions ----

export function matchesTeam(row: { team?: string }, team: string): boolean {
  if (!team) return true;
  return expandTeam(team).has(row.team || "");
}

export function matchesRep(owner: string, repFilter: string, meetingPaes?: string[]): boolean {
  if (!repFilter) return true;
  const repNorm = normalize(repFilter);
  const ownerNorm = normalize(owner || "");
  if (ownerNorm === repNorm || ownerNorm.startsWith(repNorm + " ")) return true;
  if (meetingPaes) {
    const email = repNameToEmail(repFilter);
    if (meetingPaes.includes(email)) return true;
  }
  return false;
}

export function matchesSearch(q: string, ...fields: (string | null | undefined)[]): boolean {
  if (!q.trim()) return true;
  const lower = q.toLowerCase();
  return fields.some(f => f && f.toLowerCase().includes(lower));
}

export type FilterState = {
  team: string;
  rep: string;
  search: string;
};

export function filterRow(row: DealRow, f: FilterState): boolean {
  if (!matchesTeam(row, f.team)) return false;
  if (!matchesRep(row.owner, f.rep, row.meetingPaes)) return false;
  if (!matchesSearch(f.search, row.deal, row.owner, row.signal)) return false;
  return true;
}

export function filterAction(action: ActionItem, f: FilterState): boolean {
  if (!matchesTeam(action, f.team)) return false;
  if (f.rep) {
    const repNorm = normalize(f.rep);
    const ownerNorm = normalize(action.dealOwner || "");
    const whoNorm = normalize(action.actionWho || "");
    if (ownerNorm !== repNorm && !ownerNorm.startsWith(repNorm + " ")
      && whoNorm !== repNorm && !whoNorm.startsWith(repNorm + " ")) return false;
  }
  if (!matchesSearch(f.search, action.dealName, action.actionHeadline, action.dealOwner)) return false;
  return true;
}
