/* ============================================================
   CLOSZR — Data provider

   Reads from deal_ui (single table, all fields pre-computed).
   No joins, no stage mappings, no team hacks.
   Teams/reps derived from the data.
   Structure (funnel, stage tones) from config.generated.json.
   ============================================================ */
import { useState, useEffect, type ReactNode } from "react";
import { DataContext, type CZData, type DealRow, type FunnelStage, type ForecastDeal, type ForecastData, type ClosedDeal, type ActionItem, type BenchmarkDeal } from "./store";
import { supabase } from "./supabase";
import { usePermissions, type UserProfile } from "../permissions";
import { PIPELINE_FUNNEL, PIPELINE_ASIDE, stageAbbr, shortStage, CLOSED_WON_STAGES, CLOSED_LOST_STAGES, STAGE_TONES } from "../display";
import { repNameToEmail, expandTeam } from "./filters";

// ---- Paginated fetch ----
async function fetchPaged<T>(table: string, cols: string, filter?: (q: any) => any): Promise<T[]> {
  const all: T[] = [];
  let offset = 0;
  const PAGE = 1000;
  while (true) {
    let q: any = supabase.from(table).select(cols);
    if (filter) q = filter(q);
    q = q.range(offset, offset + PAGE - 1);
    const { data, error } = await q;
    if (error) { console.warn(`[fetchPaged] ${table}: ${error.message}`); return all; }
    const rows = (data ?? []) as T[];
    all.push(...rows);
    if (rows.length < PAGE) break;
    offset += PAGE;
  }
  return all;
}

// ---- Stage palette for components.tsx StageChip ----
const STAGE: Record<string, { tone: string }> = {};
for (const [stage, tone] of Object.entries(STAGE_TONES)) {
  STAGE[stage] = { tone };
  const short = shortStage(stage);
  if (short !== stage && !STAGE[short]) STAGE[short] = { tone };
  const abbr = stageAbbr(stage);
  if (abbr !== stage && !STAGE[abbr]) STAGE[abbr] = { tone };
}

// ---- Raw deal_ui row ----
type RawDealUI = {
  deal_id: string;
  hs_deal_id: string | null;
  company_name: string | null;
  deal_name_full: string | null;
  stage: string | null;
  macro_stage: string | null;
  pae: string | null;
  pbd: string | null;
  team: string | null;
  mrr: number | null;
  close_probability: number | null;
  close_date: string | null;
  close_date_hs: string | null;
  last_contact_label: string | null;
  trend: number | null;
  is_stale: boolean | null;
  stale_days: number | null;
  score: number | null;
  bucket: string | null;
  action_priority: number | null;
  action_headline: string | null;
  action_headline_short: string | null;
  action_signal: string | null;
  action_type: string | null;
  action_who: string | null;
  action_due_date: string | null;
  action_due_label: string | null;
  howto_body: string | null;
  deal_summary: string | null;
  deal_assessment: string | null;
  m_score: number | null;
  e_score: number | null;
  dc_score: number | null;
  dp_score: number | null;
  i_score: number | null;
  c_score: number | null;
  m_text: string | null;
  e_text: string | null;
  dc_text: string | null;
  dp_text: string | null;
  i_text: string | null;
  c_text: string | null;
  blockers_count: number | null;
  signals_count: number | null;
  next_steps: any[] | null;
  closes_this_month: boolean | null;
  closes_next_month: boolean | null;
  forecast_confidence: string | null;
  deal_momentum: string | null;
  estimated_close_date: string | null;
  forecast_reasoning: string | null;
  push_action: string | null;
  forecast_risks: any[] | null;
  forecast_accelerators: any[] | null;
  pipeline_name: string | null;
  outcome: string | null;
  outcome_summary: string | null;
  employees: string | null;
  forecast_category: string | null;
  deal_age_days: number | null;
  closed_lost_reason: string | null;
  has_meeting_today: boolean | null;
  full_narrative: string | null;
  analysis_timeline: any;
  analysis_what_worked: any;
  analysis_what_failed: any;
  analysis_could_have_changed: string | null;
  analysis_rep_assessment: string | null;
  analysis_key_people: any;
  analysis_products_pitched: any;
  analysis_products_missed: any;
  analysis_product_assessment: string | null;
  trajectory: any;
  interactions: any;
  lessons: any;
  key_turning_point: string | null;
};

type RawTarget = { team: string; month: string; monthly_target: number };

function toDealRow(d: RawDealUI): DealRow & { _macro: string; _amount: number; _closeDate: string | null; _raw: RawDealUI } {
  return {
    id: d.deal_id,
    hsId: d.hs_deal_id || undefined,
    deal: d.company_name || d.deal_name_full || "—",
    stage: stageAbbr(d.stage || ""),
    mrr: d.mrr,
    prob: d.close_probability,
    last: d.last_contact_label || "—",
    trend: d.trend,
    closeDateHs: d.close_date_hs || null,
    closeDateClaudio: d.estimated_close_date || null,
    owner: d.pae || d.pbd || "—",
    team: d.team || "",
    pipeline: d.pipeline_name || "",
    stale: d.is_stale || false,
    signal: d.action_signal || d.action_headline_short || "",
    score: d.score ?? undefined,
    _macro: d.macro_stage || "other",
    _amount: d.mrr || 0,
    _closeDate: d.close_date_hs || null,
    _raw: d,
  };
}

function toForecastDeal(d: RawDealUI, row: DealRow): ForecastDeal {
  const joinTexts = (raw: any) => {
    if (!raw) return null;
    let arr = raw;
    if (typeof arr === "string") { try { arr = JSON.parse(arr); } catch { return raw; } }
    if (!Array.isArray(arr)) return String(raw);
    return arr.map((x: any) => typeof x === "string" ? x : x?.text || "").filter(Boolean).join("\n") || null;
  };
  return {
    ...row,
    closesThisMonth: (() => {
      if (!d.estimated_close_date) return false;
      const cm = new Date().toISOString().slice(0, 7);
      return d.estimated_close_date.startsWith(cm);
    })(),
    closesNextMonth: (() => {
      if (!d.estimated_close_date) return false;
      const now = new Date();
      const nm = new Date(now.getFullYear(), now.getMonth() + 1, 1);
      const nmKey = nm.toISOString().slice(0, 7);
      return d.estimated_close_date.startsWith(nmKey);
    })(),
    pushable: d.bucket === "pushable",
    pushAction: d.push_action || null,
    momentum: d.deal_momentum || null,
    confidence: d.forecast_confidence || null,
    claudioCloseDate: d.estimated_close_date || null,
    forecastReasoning: d.forecast_reasoning || null,
    forecastRisks: joinTexts(d.forecast_risks),
    forecastAccelerators: joinTexts(d.forecast_accelerators),
    hsCategory: d.forecast_category || "",
    closeDate: d.close_date_hs || null,
  };
}

const DEAL_UI_COLS = "deal_id,hs_deal_id,company_name,deal_name_full,stage,macro_stage,pae,pbd,team,mrr,close_probability,close_date,close_date_hs,last_contact_label,trend,is_stale,stale_days,score,bucket,action_priority,action_headline,action_headline_short,action_signal,action_type,action_who,action_due_date,action_due_label,howto_body,deal_summary,deal_assessment,m_score,e_score,dc_score,dp_score,i_score,c_score,m_text,e_text,dc_text,dp_text,i_text,c_text,blockers_count,signals_count,next_steps,forecast_confidence,deal_momentum,estimated_close_date,forecast_reasoning,push_action,forecast_risks,forecast_accelerators,outcome,outcome_summary,employees,forecast_category,deal_age_days,closed_lost_reason,has_meeting_today,full_narrative,analysis_timeline,analysis_what_worked,analysis_what_failed,analysis_could_have_changed,analysis_rep_assessment,analysis_key_people,analysis_products_pitched,analysis_products_missed,analysis_product_assessment,trajectory,interactions,lessons,key_turning_point,pipeline_name";

async function loadData(): Promise<CZData> {
  const [allDeals, targets] = await Promise.all([
    fetchPaged<RawDealUI>("deal_ui", DEAL_UI_COLS, q => q.not("macro_stage", "is", null)),
    fetchPaged<RawTarget>("forecast_targets", "team,month,monthly_target"),
  ]);

  console.log(`[loadData] ${allDeals.length} deals from deal_ui`);

  const allRows = allDeals.map(toDealRow);

  // ---- Pipeline ----
  const macroGroups: Record<string, typeof allRows> = {};
  for (const r of allRows) (macroGroups[r._macro] ??= []).push(r);

  const pipeline: FunnelStage[] = PIPELINE_FUNNEL.map(def => {
    const rows = macroGroups[def.key] || [];
    return { ...def, count: rows.length, value: rows.reduce((s, r) => s + r._amount, 0), stale: rows.filter(r => r.stale).length, rows: rows as DealRow[] };
  });
  const pipelineAside: FunnelStage[] = PIPELINE_ASIDE.map(def => {
    const rows = macroGroups[def.key] || [];
    return { ...def, count: rows.length, value: rows.reduce((s, r) => s + r._amount, 0), stale: rows.filter(r => r.stale).length, rows: rows as DealRow[] };
  });

  // ---- Forecast ----
  const cm = new Date().toISOString().slice(0, 7);
  const nmDate = new Date();
  nmDate.setMonth(nmDate.getMonth() + 1);
  const nmKey = nmDate.toISOString().slice(0, 7);
  const targetTotal = targets.filter(t => t.month === cm).reduce((s, t) => s + (t.monthly_target || 0), 0);

  const wonSet = new Set(CLOSED_WON_STAGES.map(s => s.toLowerCase()));
  const lostSet = new Set(CLOSED_LOST_STAGES.map(s => s.toLowerCase()));
  const stageLower = (d: RawDealUI) => (d.stage || "").toLowerCase();
  const rawById = new Map(allDeals.map(d => [d.deal_id, d]));

  // Active deals = not won, not lost
  const activeFcDeals: ForecastDeal[] = allRows
    .filter(r => !wonSet.has(stageLower(r._raw)) && !lostSet.has(stageLower(r._raw)) && r._raw.outcome !== "won" && r._raw.outcome !== "lost")
    .map(r => toForecastDeal(r._raw, r));

  // All forecast deals (for filters/teams — active + won, no lost)
  const allFcDeals: ForecastDeal[] = allRows
    .filter(r => !lostSet.has(stageLower(r._raw)))
    .map(r => toForecastDeal(r._raw, r));

  // Caja 6 — Cerrado: stage in CLOSED_WON_STAGES AND close_date_hs this month
  const closedDeals: ClosedDeal[] = allDeals
    .filter(d => wonSet.has(stageLower(d)) && (d.close_date_hs || "").startsWith(cm))
    .map(d => ({ id: d.deal_id, hsId: d.hs_deal_id || undefined, deal: d.company_name || d.deal_name_full || "—", stage: "Won", mrr: d.mrr, prob: 100, last: d.close_date_hs || "—", trend: null, closeDateHs: d.close_date_hs || null, closeDateClaudio: d.estimated_close_date || null, owner: d.pae || d.pbd || "—", team: d.team || "", dealAge: d.deal_age_days || null, strengths: d.outcome_summary || null, lessons: [], interactions: null }));
  const closedIds = new Set(closedDeals.map(d => d.id));

  // Caja 7 — Perdidos: stage in CLOSED_LOST_STAGES AND close_date_hs this month
  const lostDeals: import("./store").LostDeal[] = allDeals
    .filter(d => lostSet.has(stageLower(d)) && (d.close_date_hs || "").startsWith(cm))
    .map(d => ({ id: d.deal_id, hsId: d.hs_deal_id || undefined, deal: d.company_name || d.deal_name_full || "—", stage: "Lost", mrr: d.mrr, prob: 0, last: d.close_date_hs || "—", trend: null, closeDateHs: d.close_date_hs || null, closeDateClaudio: d.estimated_close_date || null, owner: d.pae || d.pbd || "—", team: d.team || "", closeDate: d.close_date_hs || null, lostReason: d.closed_lost_reason || null, dealAge: d.deal_age_days || null }));

  // Caja 2 — HS Forecast: close_date_hs this month, exclude won/lost
  const hsDeals = activeFcDeals.filter(d =>
    (d.closeDate && d.closeDate.startsWith(cm))
  );

  // Caja 3 — Closzr Forecast: closes_this_month OR estimated_close_date this month + won deals
  const closzrActive = activeFcDeals
    .filter(d => d.closesThisMonth || (d.claudioCloseDate && d.claudioCloseDate.startsWith(cm)));

  const closzrActiveIds = new Set(closzrActive.map(d => d.id));
  const closzrFromWon: ForecastDeal[] = closedDeals
    .filter(d => !closzrActiveIds.has(d.id))
    .map(d => {
      const raw = rawById.get(d.id!);
      return { ...d, closesThisMonth: true, closesNextMonth: false, pushable: false, pushAction: null, momentum: null, confidence: null, claudioCloseDate: null, forecastReasoning: raw?.deal_assessment || null, forecastRisks: null, forecastAccelerators: null, hsCategory: "Won", closeDate: d.last } as ForecastDeal;
    });
  const closzrWonActive = closzrActive.map(d => {
    if (closedIds.has(d.id!)) {
      const raw = rawById.get(d.id!);
      return { ...d, prob: 100, hsCategory: "Won", forecastReasoning: raw?.deal_assessment || d.forecastReasoning };
    }
    return d;
  });
  const closzrDeals = [...closzrWonActive, ...closzrFromWon];

  // Caja 4 — Next month: closes_next_month OR estimated_close_date next month, exclude closzr this month
  const closzrThisIds = new Set(closzrDeals.map(d => d.id));
  const nextMonthDeals = activeFcDeals.filter(d => {
    if (closzrThisIds.has(d.id)) return false;
    return d.closesNextMonth || (d.claudioCloseDate && d.claudioCloseDate.startsWith(nmKey));
  });

  // Caja 5 — Pushable: bucket=pushable, exclude closzr + nextMonth
  const nextMonthIds = new Set(nextMonthDeals.map(d => d.id));
  const pushableDeals = activeFcDeals.filter(d =>
    d.pushable && !closzrThisIds.has(d.id) && !nextMonthIds.has(d.id)
  );

  // M0/M1/M2 — deals assigned by either close date (can appear in multiple)
  const m2Date = new Date(nmDate.getFullYear(), nmDate.getMonth() + 1, 1);
  const m2Key = m2Date.toISOString().slice(0, 7);
  const hasMonth = (d: ForecastDeal, mk: string) =>
    (d.closeDate && d.closeDate.startsWith(mk)) || (d.claudioCloseDate && d.claudioCloseDate.startsWith(mk));
  const m0Deals = activeFcDeals.filter(d => hasMonth(d, cm));
  const m1Deals = activeFcDeals.filter(d => hasMonth(d, nmKey));
  const m0m1Ids = new Set([...m0Deals, ...m1Deals].map(d => d.id));
  const m2Deals = activeFcDeals.filter(d => hasMonth(d, m2Key) || (d.pushable && !m0m1Ids.has(d.id)));

  const forecast: ForecastData = {
    target: targetTotal,
    hsTotal: Math.round(hsDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    closzrTotal: Math.round(closzrDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    nextMonthTotal: Math.round(nextMonthDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    pushableCount: pushableDeals.length,
    closedTotal: Math.round(closedDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    lostTotal: Math.round(lostDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    hsDeals, closzrDeals, nextMonthDeals, pushableDeals, closedDeals, lostDeals,
    allDeals: allFcDeals, targets,
    m0Deals, m1Deals, m2Deals,
  };

  // ---- Benchmark (all-time won/lost) ----
  const parseJsonArr = (v: any): any[] => {
    if (!v) return [];
    if (Array.isArray(v)) return v;
    if (typeof v === "string") { try { const p = JSON.parse(v); return Array.isArray(p) ? p : []; } catch { return []; } }
    return [];
  };
  const parseJsonObj = (v: any): any | null => {
    if (!v) return null;
    if (typeof v === "object" && !Array.isArray(v)) return v;
    if (typeof v === "string") { try { return JSON.parse(v); } catch { return null; } }
    return null;
  };
  const toBenchmark = (d: RawDealUI, outcome: "won" | "lost"): BenchmarkDeal => ({
    id: d.deal_id, hsId: d.hs_deal_id || undefined,
    deal: d.company_name || d.deal_name_full || "—",
    mrr: d.mrr, owner: d.pae || d.pbd || "—", team: d.team || "", pipeline: d.pipeline_name || "",
    closeDate: d.close_date_hs || null, dealAge: d.deal_age_days || null, outcome,
    meddic: { m: d.m_score || 0, e: d.e_score || 0, dc: d.dc_score || 0, dp: d.dp_score || 0, i: d.i_score || 0, c: d.c_score || 0 },
    meddicText: { m: d.m_text || null, e: d.e_text || null, dc: d.dc_text || null, dp: d.dp_text || null, i: d.i_text || null, c: d.c_text || null },
    outcomeSummary: d.outcome_summary || null, dealAssessment: d.deal_assessment || null,
    lostReason: d.closed_lost_reason || null, employees: d.employees || null,
    fullNarrative: d.full_narrative || null,
    timeline: parseJsonArr(d.analysis_timeline),
    whatWorked: parseJsonArr(d.analysis_what_worked).map((x: any) => typeof x === "string" ? x : x?.text || x?.point || ""),
    whatFailed: parseJsonArr(d.analysis_what_failed).map((x: any) => typeof x === "string" ? x : x?.text || x?.point || ""),
    couldHaveChanged: d.analysis_could_have_changed || null,
    repAssessment: d.analysis_rep_assessment || null,
    keyPeople: parseJsonArr(d.analysis_key_people),
    productsPitched: parseJsonArr(d.analysis_products_pitched),
    productsMissed: parseJsonArr(d.analysis_products_missed),
    productAssessment: d.analysis_product_assessment || null,
    trajectory: parseJsonArr(d.trajectory),
    interactions: parseJsonObj(d.interactions),
    lessons: parseJsonArr(d.lessons).map((x: any) => typeof x === "string" ? x : x?.text || x?.lesson || ""),
    keyTurningPoint: d.key_turning_point || null,
  });
  const benchWon = allDeals.filter(d => wonSet.has(stageLower(d))).map(d => toBenchmark(d, "won"));
  const benchLost = allDeals.filter(d => lostSet.has(stageLower(d))).map(d => toBenchmark(d, "lost"));
  const benchmark = { won: benchWon, lost: benchLost };

  // ---- 1:1 ----
  const reps = [...new Set(allRows.map(r => r.owner).filter(o => o !== "—"))].sort();
  const rep = reps[0] || "—";
  const repDeals = allRows.filter(r => r.owner === rep);
  const repSnaps = repDeals.map(r => r._raw);
  const avg = (f: keyof RawDealUI) => { const v = repSnaps.map(s => s[f] as number | null).filter(x => x != null) as number[]; return v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length * 10) / 10 : 0; };
  const meddicScores = [{ key: "Metrics", score: avg("m_score") }, { key: "Economic Buyer", score: avg("e_score") }, { key: "Decision Criteria", score: avg("dc_score") }, { key: "Decision Process", score: avg("dp_score") }, { key: "Identify Pain", score: avg("i_score") }, { key: "Champion", score: avg("c_score") }];
  const weakest = [...meddicScores].sort((a, b) => a.score - b.score);

  const todayStr = new Date().toISOString().slice(0, 10);
  const oneOnOne = {
    reps, rep, activeDeals: repDeals.length,
    pipeline: repDeals.reduce((s, r) => s + r._amount, 0),
    top10: [...repDeals].sort((a, b) => b._amount - a._amount).slice(0, 10).map(r => ({ id: r.id, deal: r.deal, stage: r.stage, mrr: r.mrr, prob: r.prob })),
    meddicBase: repSnaps.length, meddic: meddicScores,
    meddicNote: weakest[0] && weakest[1] ? `${weakest[0].key} (${weakest[0].score}) y ${weakest[1].key} (${weakest[1].score}) son las áreas más débiles.` : "",
    weakness: [{ label: "Metrics", count: repSnaps.filter(s => (s.m_score || 0) < 4).length }, { label: "Economic Buyer", count: repSnaps.filter(s => (s.e_score || 0) < 4).length }, { label: "Decision Process", count: repSnaps.filter(s => (s.dp_score || 0) < 4).length }, { label: "Champion", count: repSnaps.filter(s => (s.c_score || 0) < 4).length }, { label: "Decision Criteria", count: repSnaps.filter(s => (s.dc_score || 0) < 4).length }, { label: "Identify Pain", count: repSnaps.filter(s => (s.i_score || 0) < 4).length }].sort((a, b) => b.count - a.count),
    tlActions: repDeals.filter(r => (r._raw.blockers_count || 0) > 0 || r.stale).sort((a, b) => b._amount - a._amount).slice(0, 10).map(r => ({ id: r.id, deal: r.deal, stage: r.stage, mrr: r.mrr, prob: r.prob, flag: r.stale ? `Sin contacto ${r._raw.stale_days || "?"}d` : "Blocker activo", sev: r.stale && (r._raw.stale_days || 0) > 30 || (r._raw.blockers_count || 0) > 0 ? "alto" : "medio", text: r.signal || "Requiere revisión." })),
    methodologyOpen: repDeals.length,
    methodology: [
      { n: repDeals.filter(r => r.stale).length, label: "Deals parados", tone: "amber", key: "stale", deals: repDeals.filter(r => r.stale) as DealRow[] },
      { n: repDeals.filter(r => r._closeDate && r._closeDate < todayStr).length, label: "Fecha de cierre pasada", tone: "red", key: "past_close", deals: repDeals.filter(r => r._closeDate && r._closeDate < todayStr) as DealRow[] },
    ].filter(m => m.n > 0),
  };

  // ---- TO-DOs ----
  const todos: ActionItem[] = allDeals
    .filter(d => d.action_headline && d.action_priority != null)
    .sort((a, b) => (a.action_priority || 5) - (b.action_priority || 5))
    .map(d => {
      let followUps: ActionItem["followUps"] = [];
      if (d.next_steps && Array.isArray(d.next_steps)) followUps = d.next_steps.slice(1).map((s: any, i: number) => ({ order: i + 2, type: s.type || "PREP", who: s.who || "—", text: s.text || "", when: s.when || "pendiente", due: s.due || undefined }));
      return { id: d.deal_id, dealId: d.deal_id, hsId: d.hs_deal_id || undefined, dealName: d.company_name || d.deal_name_full || "—", dealOwner: d.pae || d.pbd || "—", dealMrr: d.mrr, dealStage: shortStage(d.stage || ""), bucket: d.bucket || "pipeline", claudioCloseDate: d.estimated_close_date || null, actionHeadline: d.action_headline || "", actionDetail: d.howto_body || null, actionType: d.action_type || "PREP", actionWho: d.action_who || "—", actionWhen: d.action_due_label || "pendiente", actionPriority: d.action_priority || 5, actionDueDate: d.action_due_date || null, followUps, status: "pending", team: d.team || "", pipeline: d.pipeline_name || "" };
    });

  // ---- Meetings today ----
  const meetingRows: DealRow[] = allRows
    .filter(r => r._raw.has_meeting_today)
    .map(r => r as DealRow);
  const groups = meetingRows.length > 0
    ? [{ id: "meetings-today", title: "Meetings hoy", meta: `${meetingRows.length} deals`, tint: "indigo", rows: meetingRows }]
    : [];

  return { STAGE, groups, nakiva: null, yukAtlas: null, pipeline, pipelineAside, forecast, benchmark, oneOnOne, todos, loading: false };
}

// ---- Permission-based filtering ----
function applyPermissions(data: CZData, profile: UserProfile | null): CZData {
  if (!profile) return data;
  const teams = profile.visibleTeams || [];
  if (!teams.length && profile.role !== "Admin") return data;
  const scope = profile.tabPermissions?.deals?.scope || "all";
  if (scope === "all" && profile.role === "Admin") return data;

  const teamSet = new Set<string>();
  for (const t of teams) for (const et of expandTeam(t)) teamSet.add(et);
  const ownerEmail = profile.email.toLowerCase();
  const matchesSelf = (name: string) => repNameToEmail(name) === ownerEmail;
  const filterRow = (r: DealRow): boolean => {
    if (scope === "self") return matchesSelf(r.owner || "");
    if (teamSet.size === 0) return true;
    return teamSet.has(r.team || "");
  };
  const filterFc = (d: ForecastDeal): boolean => filterRow(d as any);
  const filterByTeam = (d: { team?: string }) => teamSet.size === 0 || teamSet.has(d.team || "");

  return {
    ...data,
    groups: data.groups.map(g => ({ ...g, rows: g.rows.filter(filterRow) })).filter(g => g.rows.length > 0),
    pipeline: data.pipeline.map(s => { const rows = s.rows.filter(filterRow); return { ...s, rows, count: rows.length, value: rows.reduce((a, r) => a + (r.mrr || 0), 0), stale: rows.filter(r => r.stale).length }; }),
    pipelineAside: data.pipelineAside.map(s => { const rows = s.rows.filter(filterRow); return { ...s, rows, count: rows.length, value: rows.reduce((a, r) => a + (r.mrr || 0), 0), stale: rows.filter(r => r.stale).length }; }),
    todos: data.todos.filter(a => { if (scope === "self") return matchesSelf(a.dealOwner || ""); return filterByTeam(a); }),
    benchmark: { won: data.benchmark.won.filter(filterByTeam), lost: data.benchmark.lost.filter(filterByTeam) },
    forecast: {
      ...data.forecast,
      hsTotal: Math.round(data.forecast.hsDeals.filter(filterFc).reduce((s, d) => s + (d.mrr || 0), 0)),
      closzrTotal: Math.round(data.forecast.closzrDeals.filter(filterFc).reduce((s, d) => s + (d.mrr || 0), 0)),
      nextMonthTotal: Math.round(data.forecast.nextMonthDeals.filter(filterFc).reduce((s, d) => s + (d.mrr || 0), 0)),
      pushableCount: data.forecast.pushableDeals.filter(filterFc).length,
      closedTotal: Math.round(data.forecast.closedDeals.filter(filterByTeam).reduce((s, d) => s + (d.mrr || 0), 0)),
      lostTotal: Math.round(data.forecast.lostDeals.filter(filterByTeam).reduce((s, d) => s + (d.mrr || 0), 0)),
      hsDeals: data.forecast.hsDeals.filter(filterFc),
      closzrDeals: data.forecast.closzrDeals.filter(filterFc),
      nextMonthDeals: data.forecast.nextMonthDeals.filter(filterFc),
      pushableDeals: data.forecast.pushableDeals.filter(filterFc),
      closedDeals: data.forecast.closedDeals.filter(filterByTeam),
      lostDeals: data.forecast.lostDeals.filter(filterByTeam),
      allDeals: data.forecast.allDeals.filter(filterFc),
      m0Deals: data.forecast.m0Deals.filter(filterFc),
      m1Deals: data.forecast.m1Deals.filter(filterFc),
      m2Deals: data.forecast.m2Deals.filter(filterFc),
    },
  };
}

const EMPTY_DATA: CZData = { STAGE, groups: [], nakiva: null, yukAtlas: null, pipeline: [], pipelineAside: [], forecast: { target: 0, hsTotal: 0, closzrTotal: 0, nextMonthTotal: 0, pushableCount: 0, closedTotal: 0, lostTotal: 0, hsDeals: [], closzrDeals: [], nextMonthDeals: [], pushableDeals: [], closedDeals: [], lostDeals: [], allDeals: [], targets: [], m0Deals: [], m1Deals: [], m2Deals: [] }, benchmark: { won: [], lost: [] }, oneOnOne: { reps: [], rep: "", activeDeals: 0, pipeline: 0, top10: [], meddicBase: 0, meddic: [], meddicNote: "", weakness: [], tlActions: [], methodologyOpen: 0, methodology: [] }, todos: [], loading: true };

// ---- Provider ----
export function DataProvider({ children }: { children: ReactNode }) {
  const { profile } = usePermissions();
  const [raw, setRaw] = useState<CZData | null>(null);

  useEffect(() => {
    loadData().then(setRaw).catch(err => { console.error("Failed to load:", err); setRaw(prev => prev ? { ...prev, loading: false } : { ...EMPTY_DATA, loading: false }); });
    let t: ReturnType<typeof setTimeout>;
    const reload = () => { clearTimeout(t); t = setTimeout(() => { loadData().then(setRaw); }, 5000); };
    const ch = supabase.channel("rt-deal-ui").on("postgres_changes", { event: "*", schema: "public", table: "deal_ui" }, reload).subscribe();
    return () => { clearTimeout(t); supabase.removeChannel(ch); };
  }, []);

  return <DataContext.Provider value={raw ? applyPermissions(raw, profile) : EMPTY_DATA}>{children}</DataContext.Provider>;
}
