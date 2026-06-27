/* ============================================================
   CLOSZR — Data provider

   Reads from deal_ui (single table, all fields pre-computed).
   No joins, no stage mappings, no team hacks.
   Teams/reps derived from the data.
   Structure (funnel, stage tones) from config.generated.json.
   ============================================================ */
import { useState, useEffect, type ReactNode } from "react";
import { DataContext, type CZData, type DealRow, type FunnelStage, type ForecastDeal, type ForecastData, type ClosedDeal, type ActionItem } from "./store";
import { supabase } from "./supabase";
import { usePermissions, type UserProfile } from "../permissions";
import { PIPELINE_FUNNEL, PIPELINE_ASIDE, stageAbbr, shortStage, CLOSED_LOST_STAGES, STAGE_TONES } from "../display";

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
  outcome: string | null;
  employees: string | null;
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
    owner: d.pae || d.pbd || "—",
    team: d.team || "",
    stale: d.is_stale || false,
    signal: d.action_signal || d.action_headline_short || "",
    score: d.score ?? undefined,
    _macro: d.macro_stage || "other",
    _amount: d.mrr || 0,
    _closeDate: d.close_date || d.close_date_hs || null,
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
    closesThisMonth: d.closes_this_month || false,
    closesNextMonth: (d.closes_next_month || false) && !(d.closes_this_month || false),
    pushable: d.bucket === "pushable",
    pushAction: d.push_action || null,
    momentum: d.deal_momentum || null,
    confidence: d.forecast_confidence || null,
    claudioCloseDate: d.estimated_close_date || null,
    forecastReasoning: d.forecast_reasoning || null,
    forecastRisks: joinTexts(d.forecast_risks),
    forecastAccelerators: joinTexts(d.forecast_accelerators),
    hsCategory: "",
    closeDate: d.close_date || d.close_date_hs || null,
  };
}

async function loadData(): Promise<CZData> {
  const [allDeals, targets] = await Promise.all([
    fetchPaged<RawDealUI>("deal_ui", "*", q => q.not("macro_stage", "is", null)),
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
  const targetTotal = targets.filter(t => t.month === cm).reduce((s, t) => s + (t.monthly_target || 0), 0);
  const allFcDeals: ForecastDeal[] = allRows.map(r => toForecastDeal(r._raw, r));

  const closzrDeals = allFcDeals.filter(d => d.closesThisMonth);
  const nextMonthDeals = allFcDeals.filter(d => d.closesNextMonth && !d.closesThisMonth);
  const pushableDeals = allFcDeals.filter(d => d.pushable && !d.closesThisMonth && !d.closesNextMonth);

  const closedDeals: ClosedDeal[] = allDeals
    .filter(d => d.outcome === "won" && d.close_date && d.close_date.startsWith(cm))
    .map(d => ({ id: d.deal_id, deal: d.company_name || "—", stage: "Won", mrr: d.mrr, prob: 100, last: d.close_date || "—", trend: null, owner: d.pae || d.pbd || "—", team: d.team || "", dealAge: null, strengths: null, lessons: [], interactions: null }));

  const nextMonthStr = cm.slice(0, 5) + String(Number(cm.slice(5)) + 1).padStart(2, "0");
  const { data: lostRaw } = await supabase.from("deals")
    .select("id,deal_id,deal_name,deal_stage,amount,pae,pbd,close_date,closed_lost_reason,deal_age_days")
    .in("deal_stage", CLOSED_LOST_STAGES).gte("close_date", cm + "-01").lt("close_date", nextMonthStr + "-01");

  const lostDeals: import("./store").LostDeal[] = (lostRaw || []).map((d: any) => ({
    id: d.id, hsId: d.deal_id || undefined, deal: d.deal_name || "—", stage: "Lost", mrr: d.amount, prob: 0,
    last: d.close_date || "—", trend: null, owner: d.pae || d.pbd || "—", team: "",
    closeDate: d.close_date || null, lostReason: d.closed_lost_reason || null, dealAge: d.deal_age_days || null,
  }));

  const forecast: ForecastData = {
    target: targetTotal,
    hsTotal: Math.round(closzrDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    closzrTotal: Math.round(closzrDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    nextMonthTotal: Math.round(nextMonthDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    pushableCount: pushableDeals.length,
    closedTotal: Math.round(closedDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    lostTotal: Math.round(lostDeals.reduce((s, d) => s + (d.mrr || 0), 0)),
    hsDeals: allFcDeals.filter(d => d.closesThisMonth || d.pushable),
    closzrDeals, nextMonthDeals, pushableDeals, closedDeals, lostDeals,
    allDeals: allFcDeals, targets,
  };

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
      return { id: d.deal_id, dealId: d.deal_id, hsId: d.hs_deal_id || undefined, dealName: d.company_name || d.deal_name_full || "—", dealOwner: d.pae || d.pbd || "—", dealMrr: d.mrr, dealStage: shortStage(d.stage || ""), bucket: d.bucket || "pipeline", claudioCloseDate: d.estimated_close_date || null, actionHeadline: d.action_headline || "", actionDetail: d.howto_body || null, actionType: d.action_type || "PREP", actionWho: d.action_who || "—", actionWhen: d.action_due_label || "pendiente", actionPriority: d.action_priority || 5, actionDueDate: d.action_due_date || null, followUps, status: "pending", team: d.team || "" };
    });

  return { STAGE, groups: [], nakiva: null, yukAtlas: null, pipeline, pipelineAside, forecast, oneOnOne, todos, loading: false };
}

// ---- Permission-based filtering ----
function applyPermissions(data: CZData, profile: UserProfile | null): CZData {
  if (!profile) return data;
  const teams = profile.visibleTeams || [];
  if (!teams.length && profile.role !== "Admin") return data;
  const scope = profile.tabPermissions?.deals?.scope || "all";
  if (scope === "all" && profile.role === "Admin") return data;

  const teamSet = new Set(teams);
  const ownerEmail = profile.email.toLowerCase();
  const filterRow = (r: DealRow): boolean => {
    if (scope === "self") return (r.owner || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ /g, ".") + "@factorial.co" === ownerEmail;
    if (teamSet.size === 0) return true;
    return teamSet.has(r.team || "");
  };
  const filterFc = (d: ForecastDeal): boolean => filterRow(d as any);

  return {
    ...data,
    groups: data.groups.map(g => ({ ...g, rows: g.rows.filter(filterRow) })).filter(g => g.rows.length > 0),
    pipeline: data.pipeline.map(s => { const rows = s.rows.filter(filterRow); return { ...s, rows, count: rows.length, value: rows.reduce((a, r) => a + (r.mrr || 0), 0), stale: rows.filter(r => r.stale).length }; }),
    pipelineAside: data.pipelineAside.map(s => { const rows = s.rows.filter(filterRow); return { ...s, rows, count: rows.length, value: rows.reduce((a, r) => a + (r.mrr || 0), 0), stale: rows.filter(r => r.stale).length }; }),
    todos: data.todos.filter(a => { if (scope === "self") return (a.dealOwner || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ /g, ".") + "@factorial.co" === ownerEmail; return teamSet.size === 0 || teamSet.has(a.team); }),
    forecast: {
      ...data.forecast,
      hsTotal: data.forecast.hsDeals.filter(filterFc).reduce((s, d) => s + (d.mrr || 0), 0),
      closzrTotal: data.forecast.closzrDeals.filter(filterFc).reduce((s, d) => s + (d.mrr || 0), 0),
      nextMonthTotal: data.forecast.nextMonthDeals.filter(filterFc).reduce((s, d) => s + (d.mrr || 0), 0),
      pushableCount: data.forecast.pushableDeals.filter(filterFc).length,
      closedTotal: data.forecast.closedDeals.filter(d => teamSet.size === 0 || teamSet.has(d.team || "")).reduce((s, d) => s + (d.mrr || 0), 0),
      lostTotal: data.forecast.lostDeals.filter(d => teamSet.size === 0 || teamSet.has(d.team || "")).reduce((s, d) => s + (d.mrr || 0), 0),
      hsDeals: data.forecast.hsDeals.filter(filterFc),
      closzrDeals: data.forecast.closzrDeals.filter(filterFc),
      nextMonthDeals: data.forecast.nextMonthDeals.filter(filterFc),
      pushableDeals: data.forecast.pushableDeals.filter(filterFc),
      closedDeals: data.forecast.closedDeals.filter(d => teamSet.size === 0 || teamSet.has(d.team || "")),
      lostDeals: data.forecast.lostDeals.filter(d => teamSet.size === 0 || teamSet.has(d.team || "")),
      allDeals: data.forecast.allDeals.filter(filterFc),
    },
  };
}

// ---- Provider ----
export function DataProvider({ children }: { children: ReactNode }) {
  const { profile } = usePermissions();
  const [raw, setRaw] = useState<CZData | null>(null);
  const emptyData: CZData = { STAGE, groups: [], nakiva: null, yukAtlas: null, pipeline: [], pipelineAside: [], forecast: { target: 0, hsTotal: 0, closzrTotal: 0, nextMonthTotal: 0, pushableCount: 0, closedTotal: 0, lostTotal: 0, hsDeals: [], closzrDeals: [], nextMonthDeals: [], pushableDeals: [], closedDeals: [], lostDeals: [], allDeals: [], targets: [] }, oneOnOne: { reps: [], rep: "", activeDeals: 0, pipeline: 0, top10: [], meddicBase: 0, meddic: [], meddicNote: "", weakness: [], tlActions: [], methodologyOpen: 0, methodology: [] }, todos: [], loading: true };

  useEffect(() => {
    loadData().then(setRaw).catch(err => { console.error("Failed to load:", err); setRaw(prev => prev ? { ...prev, loading: false } : { ...emptyData, loading: false }); });
    let t: ReturnType<typeof setTimeout>;
    const reload = () => { clearTimeout(t); t = setTimeout(() => { loadData().then(setRaw); }, 5000); };
    const ch = supabase.channel("rt-deal-ui").on("postgres_changes", { event: "*", schema: "public", table: "deal_ui" }, reload).subscribe();
    return () => { clearTimeout(t); supabase.removeChannel(ch); };
  }, []);

  return <DataContext.Provider value={raw ? applyPermissions(raw, profile) : emptyData}>{children}</DataContext.Provider>;
}
