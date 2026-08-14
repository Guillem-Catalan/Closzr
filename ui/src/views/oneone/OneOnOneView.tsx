import { useState, useEffect, useMemo, useCallback, Fragment } from "react";
import { Icon, TONE, Avatar, getInitials, fmtMRR } from "../components";
import { usePermissions } from "../../permissions";
import { hubspotDealUrl, CLOSED_LOST_STAGES, LOST_REASONS, CRM_FORECAST_CATEGORIES, stageAbbr } from "../../display";
import { WEEKS, getWeekType, getMonday, getMondayOfWeek, currentYearMonth, PROBLEM_LABELS, type Section, type CheckItem } from "./weeks";
import { useOneOnOne, type OODeal, type OOEntry, type OOSession } from "./useOneOnOne";

function fmtDate(d: string | null): string {
  if (!d) return "—";
  const [, m, day] = d.split("-");
  const months = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${parseInt(day)} ${months[parseInt(m)]}`;
}

function nowTime(): string {
  const n = new Date();
  return n.getHours().toString().padStart(2, "0") + ":" + n.getMinutes().toString().padStart(2, "0");
}

function momCls(m: string | null): string {
  return ({ accelerating: "mom-acc", stable: "mom-stab", stalling: "mom-stall", declining: "mom-dec" } as Record<string, string>)[m || ""] || "mom-stab";
}

function momLabel(m: string | null): string {
  return ({ accelerating: "↗ Acelerando", stable: "→ Estable", stalling: "↘ Frenando", declining: "↓ Cayendo" } as Record<string, string>)[m || ""] || m || "";
}

function probColor(p: number): string {
  return p >= 70 ? "var(--green-ink)" : p >= 40 ? "var(--amber-ink)" : "var(--red-ink)";
}
function probBg(p: number): string {
  return p >= 70 ? "var(--green-tint)" : p >= 40 ? "var(--amber-tint)" : "var(--red-tint)";
}

function stageCls(stage: string | null): string {
  const s = (stage || "").toLowerCase();
  if (s.includes("demo")) return "stage-demo";
  if (s.includes("eval")) return "stage-eval";
  if (s.includes("clos")) return "stage-closing";
  return "stage-demo";
}

type ActionMode = "keep" | "change" | "action" | "lost" | "push";
type ActionDef = { mode: ActionMode; label: string; cls: string };

function actionsFor(actType: string | undefined): ActionDef[] {
  switch (actType) {
    case "hygiene":
      return [
        { mode: "change", label: "Cambiar fecha", cls: "change" },
        { mode: "action", label: "Definir acción", cls: "flag" },
        { mode: "lost", label: "Mover a Lost", cls: "" },
      ];
    case "push":
      return [
        { mode: "push", label: "Adelantar a M+1", cls: "push" },
        { mode: "keep", label: "Mantener", cls: "keep" },
        { mode: "lost", label: "Mover a Lost", cls: "" },
      ];
    case "m0_close":
      return [
        { mode: "keep", label: "Confirmar cierre", cls: "keep" },
        { mode: "change", label: "Cambiar fecha", cls: "change" },
        { mode: "lost", label: "Mover a Lost", cls: "" },
      ];
    default:
      return [
        { mode: "keep", label: "Mantener fecha", cls: "keep" },
        { mode: "change", label: "Cambiar fecha", cls: "change" },
        { mode: "lost", label: "Mover a Lost", cls: "" },
      ];
  }
}

const MONTH_NAMES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

function monthOptions(): { value: string; label: string }[] {
  const opts: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const v = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    opts.push({ value: v, label: `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}` });
  }
  return opts;
}

function fmtYM(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return `${MONTH_NAMES[m - 1]} ${y}`;
}

const HsIcon = () => (
  <a className="hs-lnk" title="Abrir en HubSpot" onClick={e => e.stopPropagation()}>
    <svg width="14" height="14" viewBox="0 0 512 512" fill="currentColor">
      <path d="M391.8 197.4V133c17.2-8.3 29.1-25.8 29.1-46.1v-1.4c0-28.1-22.8-50.9-50.9-50.9h-1.4c-28.1 0-50.9 22.8-50.9 50.9v1.4c0 20.3 11.9 37.8 29.1 46.1v64.4c-25 5.1-47.9 16-67.2 31.6l-177.7-138.4c1.6-5.5 2.6-11.3 2.6-17.3C104.4 32.8 71.6 0 31.2 0S-42 32.8-42 73.2c0 40.4 32.8 73.2 73.2 73.2 6 0 11.8-1 17.3-2.6L225.8 282c-17.9 22-28.7 50-28.7 80.5 0 70.4 57.1 127.5 127.5 127.5S452 433 452 362.5 395 235 324.5 235c-.3 0-.5 0-.8 0l2.1-37.6zM324.5 427c-35.6 0-64.5-28.9-64.5-64.5s28.9-64.5 64.5-64.5 64.5 28.9 64.5 64.5-28.9 64.5-64.5 64.5z" transform="translate(42) scale(.88)"/>
    </svg>
  </a>
);

const SvgChev = ({ rot }: { rot: number }) => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    style={{ color: "var(--ink-4)", transform: `rotate(${rot}deg)`, transition: "transform .15s" }}>
    <path d="M6 9l6 6 6-6" />
  </svg>
);

/* =========================================================
   MAIN VIEW
   ========================================================= */
export default function OneOnOneView({ onOpen }: { onOpen: (row: any, tab?: string) => void }) {
  const { profile } = usePermissions();
  const tlEmail = profile?.email || "";

  const [month, setMonth] = useState(currentYearMonth);
  const [weekType, setWeekType] = useState(getWeekType);
  const [selectedRep, setSelectedRep] = useState("");
  const [tab, setTab] = useState<"session" | "hist">("session");

  const [openDeals, setOpenDeals] = useState<Record<string, boolean>>({});
  const [openChecks, setOpenChecks] = useState<Record<string, boolean>>({});
  const [collSec, setCollSec] = useState<Record<string, boolean>>({});
  const [collGuide, setCollGuide] = useState<Record<string, boolean>>({});
  const [actionMode, setActionMode] = useState<Record<string, ActionMode>>({});
  const [lostDeals, setLostDeals] = useState<Set<string>>(new Set());
  const [fcChanges, setFcChanges] = useState<Record<string, string>>({});
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [collSum, setCollSum] = useState(false);
  const [collSumSec, setCollSumSec] = useState<Record<string, boolean>>({});
  const [histOpen, setHistOpen] = useState<string | null>(null);
  const [noteInputs, setNoteInputs] = useState<Record<string, string>>({});
  const [flash, setFlash] = useState<string | null>(null);
  const [hsError, setHsError] = useState<string | null>(null);

  const week = WEEKS[weekType];
  const monday = getMondayOfWeek(month, weekType);
  const mOpts = useMemo(monthOptions, []);
  const isCurrent = month === currentYearMonth();
  const curWk = getWeekType();

  const { deals, reps, session, history, loading, getDealsFor, getCoverage, toggleCheck, addEntry, callDealUpdate } =
    useOneOnOne(selectedRep, weekType, tlEmail, monday, profile);

  const syncToHS = useCallback(async (action: string, params: Record<string, string>) => {
    const res = await callDealUpdate(action, params);
    if (!res.ok) {
      setHsError(res.error || "Error al sincronizar con HubSpot");
      setTimeout(() => setHsError(null), 5000);
    }
  }, [callDealUpdate]);

  useEffect(() => {
    if (!selectedRep && reps.length > 0) setSelectedRep(reps[0]);
  }, [reps, selectedRep]);

  useEffect(() => {
    if (isCurrent) setWeekType(getWeekType());
    else setWeekType(0);
  }, [month, isCurrent]);

  const resetOnRepChange = useCallback(() => {
    setOpenDeals({});
    setOpenChecks({});
    setActionMode({});
    setLostDeals(new Set());
    setFcChanges({});
    setHistOpen(null);
    setNoteInputs({});
  }, []);

  const activeDeals = useMemo(() => deals.filter(d => !lostDeals.has(d.deal_id)), [deals, lostDeals]);

  const getActiveDealsFor = useCallback((query: string): OODeal[] => {
    return getDealsFor(query).filter(d => !lostDeals.has(d.deal_id));
  }, [getDealsFor, lostDeals]);

  const entries = session?.entries || [];
  const checks = session?.checks || {};

  const itemDeals = useCallback((item: CheckItem): OODeal[] => {
    if (item.queries) {
      const seen = new Set<string>();
      const out: OODeal[] = [];
      for (const q of item.queries) {
        for (const d of getActiveDealsFor(q)) {
          if (!seen.has(d.deal_id)) { seen.add(d.deal_id); out.push(d); }
        }
      }
      return out;
    }
    if (item.query) return getActiveDealsFor(item.query);
    return [];
  }, [getActiveDealsFor]);

  const dealProblems = useCallback((item: CheckItem): Map<string, string[]> => {
    if (!item.queries) return new Map();
    const map = new Map<string, string[]>();
    for (const q of item.queries) {
      for (const d of getActiveDealsFor(q)) {
        const labels = map.get(d.deal_id) || [];
        const lbl = PROBLEM_LABELS[q];
        if (lbl && !labels.includes(lbl)) labels.push(lbl);
        map.set(d.deal_id, labels);
      }
    }
    return map;
  }, [getActiveDealsFor]);

  // KPI
  const kpi = useMemo(() => {
    const m0 = activeDeals.filter(d => getActiveDealsFor("m0").some(dd => dd.deal_id === d.deal_id));
    const m1 = activeDeals.filter(d => getActiveDealsFor("m1").some(dd => dd.deal_id === d.deal_id));
    const m0Soon = getActiveDealsFor("m0_closing_soon");
    const total = activeDeals.reduce((s, d) => s + (d.mrr || 0), 0);
    const m0Mrr = m0.reduce((s, d) => s + (d.mrr || 0), 0);
    const m1Mrr = m1.reduce((s, d) => s + (d.mrr || 0), 0);
    const cov = getCoverage();
    const covPct = cov.ratio > 0 ? Math.round(cov.ratio * 100) : 0;
    return { total, cnt: activeDeals.length, m0Mrr, m0Cnt: m0.length, m0Close: m0Soon.length, m1Mrr, m1Cnt: m1.length, covPct, target: cov.target };
  }, [activeDeals, getActiveDealsFor, getCoverage]);

  // Progress
  const totalChecks = week.sections.reduce((s, sec) => s + sec.items.length, 0);
  const doneChecks = week.sections.reduce((s, sec) => s + sec.items.filter(i => checks[i.id]).length, 0);
  const pct = totalChecks > 0 ? Math.round(doneChecks / totalChecks * 100) : 0;

  // autoCheck
  const autoCheck = useCallback((itemId: string) => {
    let item: CheckItem | null = null;
    week.sections.forEach(s => s.items.forEach(i => { if (i.id === itemId) item = i; }));
    if (!item) return;
    const ds = itemDeals(item);
    if (ds.length > 0) {
      const allReviewed = ds.every(d => entries.some(e => e.deal_id === d.deal_id));
      if (allReviewed && !checks[itemId]) toggleCheck(itemId);
    } else {
      const hasNote = entries.some(e => e.deal_id === `item:${itemId}`);
      if (hasNote && !checks[itemId]) toggleCheck(itemId);
    }
  }, [week, itemDeals, entries, checks, toggleCheck]);

  // Actions
  const doAction = useCallback((dk: string, deal: OODeal, mode: ActionMode, secNum: string) => {
    const rsEl = document.getElementById(`rs-${dk}`) as HTMLInputElement | null;
    const dtEl = document.getElementById(`dt-${dk}`) as HTMLInputElement | null;
    const lrEl = document.getElementById(`lr-${dk}`) as HTMLSelectElement | null;
    const reason = rsEl?.value.trim() || "";
    const newDate = dtEl?.value || "";
    const lostReason = lrEl?.value || "";
    if (!reason) return;
    if (mode === "change" && !newDate) return;
    const name = deal.company_name || deal.deal_name_full || "—";

    if (mode === "keep") {
      addEntry({ deal_id: deal.deal_id, deal_name: name, section: secNum, type: "note",
        note: `Fecha mantenida (${fmtDate(deal.close_date_hs)}): ${reason}` });
      if (deal.hs_deal_id) {
        syncToHS("add_note", { hs_deal_id: deal.hs_deal_id, note: `[1:1] Fecha mantenida: ${reason}` });
      }
    } else if (mode === "change") {
      addEntry({ deal_id: deal.deal_id, deal_name: name, section: secNum, type: "change",
        field: "close_date", old_val: fmtDate(deal.close_date_hs), new_val: fmtDate(newDate), note: reason });
      if (deal.hs_deal_id) {
        syncToHS("update_close_date", { hs_deal_id: deal.hs_deal_id, new_date: newDate });
        syncToHS("add_note", { hs_deal_id: deal.hs_deal_id, note: `[1:1] Fecha cambiada: ${reason}` });
      }
    } else if (mode === "action" || mode === "push") {
      addEntry({ deal_id: deal.deal_id, deal_name: name, section: secNum, type: "commitment", note: reason });
      if (deal.hs_deal_id) {
        syncToHS("add_note", { hs_deal_id: deal.hs_deal_id, note: `[1:1] ${mode === "push" ? "Adelantar" : "Acción"}: ${reason}` });
      }
    } else if (mode === "lost") {
      addEntry({ deal_id: deal.deal_id, deal_name: name, section: secNum, type: "change",
        field: "stage", old_val: deal.stage || "—", new_val: "Closed Lost", note: `${lostReason} — ${reason}` });
      setLostDeals(prev => new Set(prev).add(deal.deal_id));
      if (deal.hs_deal_id) {
        syncToHS("mark_lost", { hs_deal_id: deal.hs_deal_id, lost_reason: lostReason, detail: reason });
      }
    }

    setActionMode(prev => { const n = { ...prev }; delete n[dk]; return n; });
    setOpenDeals(prev => { const n = { ...prev }; delete n[dk]; return n; });
    setFlash(dk);
    setTimeout(() => setFlash(null), 800);

    const itmId = dk.replace(/-[^-]+$/, "");
    autoCheck(itmId);
  }, [addEntry, autoCheck]);

  const changeFc = useCallback((dealId: string, dealName: string, from: string, to: string) => {
    if (from === to) return;
    setFcChanges(prev => ({ ...prev, [dealId]: to }));
    addEntry({ deal_id: dealId, deal_name: dealName, section: "", type: "fcChange",
      field: "forecast_category", old_val: from, new_val: to });
    const deal = deals.find(d => d.deal_id === dealId);
    if (deal?.hs_deal_id) {
      syncToHS("update_forecast", { hs_deal_id: deal.hs_deal_id, category: to });
    }
    week.sections.forEach(s => s.items.forEach(i => {
      if (itemDeals(i).some(d => d.deal_id === dealId)) autoCheck(i.id);
    }));
  }, [addEntry, deals, syncToHS, week, itemDeals, autoCheck]);

  const addNote = useCallback((itemId: string) => {
    const val = noteInputs[itemId]?.trim();
    if (!val) return;
    addEntry({ deal_id: `item:${itemId}`, deal_name: "", section: "", type: "note", note: val });
    setNoteInputs(prev => ({ ...prev, [itemId]: "" }));
    autoCheck(itemId);
  }, [noteInputs, addEntry, autoCheck]);

  const validateCfm = useCallback((dk: string, mode: ActionMode): boolean => {
    const rs = document.getElementById(`rs-${dk}`) as HTMLInputElement | null;
    const dt = document.getElementById(`dt-${dk}`) as HTMLInputElement | null;
    const hasText = !!rs?.value.trim();
    if (mode === "change") return hasText && !!dt?.value;
    return hasText;
  }, []);

  /* ── render: deal card ── */
  const renderDealCard = (deal: OODeal, item: CheckItem, sec: Section) => {
    const dk = `${item.id}-${deal.deal_id}`;
    const op = !!openDeals[dk];
    const mode = actionMode[dk];
    const reviewed = entries.some(e => e.deal_id === deal.deal_id);
    const name = deal.company_name || deal.deal_name_full || "—";
    const prob = deal.close_probability || 0;
    const curFc = fcChanges[deal.deal_id] || "";
    const problems = dealProblems(item).get(deal.deal_id) || [];
    const hsUrl = deal.hs_deal_id ? hubspotDealUrl(deal.hs_deal_id) : null;

    const hsM = deal.close_date_hs?.slice(0, 7);
    const czM = deal.estimated_close_date?.slice(0, 7);
    const aligned = hsM && czM && hsM === czM;

    const dealEntries = entries.filter(e => e.deal_id === deal.deal_id);

    const fcCats = CRM_FORECAST_CATEGORIES.length > 0 ? CRM_FORECAST_CATEGORIES : ["Commit", "Upside", "Pipeline", "Omit"];

    const actType = (item as any).actType;
    const acts = actionsFor(actType);
    const mainActs = acts.filter(a => a.mode !== "lost");
    const lostAct = acts.find(a => a.mode === "lost");

    const cfmLabels: Record<string, string> = {
      keep: "Confirmar — mantener fecha", change: "Cambiar fecha de cierre",
      action: "Definir acción concreta", lost: "Mover a Closed Lost", push: "Adelantar a M+1",
    };
    const chipCls: Record<string, string> = { keep: "chip-g", change: "chip-a", action: "chip-a", lost: "chip-r", push: "chip-g" };
    const btnCls: Record<string, string> = { keep: "green", change: "blue", action: "blue", lost: "red", push: "green" };

    return (
      <div key={dk} className={`dcard${op ? " open" : ""}${flash === dk ? " flash" : ""}`}
        onClick={() => {
          setOpenDeals(prev => ({ ...prev, [dk]: !prev[dk] }));
          setActionMode(prev => { const n = { ...prev }; delete n[dk]; return n; });
        }}>
        <div className="dcard-top">
          <span className="dcard-name">
            {name}
            {hsUrl && <a className="hs-lnk" href={hsUrl} target="_blank" rel="noopener noreferrer"
              title="Abrir en HubSpot" onClick={e => e.stopPropagation()}>
              <svg width="14" height="14" viewBox="0 0 512 512" fill="currentColor">
                <path d="M391.8 197.4V133c17.2-8.3 29.1-25.8 29.1-46.1v-1.4c0-28.1-22.8-50.9-50.9-50.9h-1.4c-28.1 0-50.9 22.8-50.9 50.9v1.4c0 20.3 11.9 37.8 29.1 46.1v64.4c-25 5.1-47.9 16-67.2 31.6l-177.7-138.4c1.6-5.5 2.6-11.3 2.6-17.3C104.4 32.8 71.6 0 31.2 0S-42 32.8-42 73.2c0 40.4 32.8 73.2 73.2 73.2 6 0 11.8-1 17.3-2.6L225.8 282c-17.9 22-28.7 50-28.7 80.5 0 70.4 57.1 127.5 127.5 127.5S452 433 452 362.5 395 235 324.5 235c-.3 0-.5 0-.8 0l2.1-37.6zM324.5 427c-35.6 0-64.5-28.9-64.5-64.5s28.9-64.5 64.5-64.5 64.5 28.9 64.5 64.5-28.9 64.5-64.5 64.5z" transform="translate(42) scale(.88)"/>
              </svg>
            </a>}
          </span>
          <span className="dcard-mrr num">{fmtMRR(deal.mrr)}</span>
          <span className={`dcard-stage ${stageCls(deal.stage)}`}>{stageAbbr(deal.stage || "")}</span>
          {reviewed && <span className="dcard-reviewed">{"✓"} Revisado</span>}
        </div>
        <div className="dcard-meta">
          <span className="dcard-meta-item"><span className={`momentum ${momCls(deal.deal_momentum)}`}>{momLabel(deal.deal_momentum)}</span></span>
          <span className="dcard-meta-item"><span className="prob-badge num" style={{ background: probBg(prob), color: probColor(prob) }}>{prob}%</span></span>
          <span className="dcard-meta-item">Contacto: {deal.last_contact_label || "—"}</span>
          <span className="dcard-meta-item num">{fmtDate(deal.close_date_hs)}</span>
          {problems.map(l => <span key={l} className="ptag">{l}</span>)}
        </div>

        {op && (
          <div className="dcard-detail" onClick={e => e.stopPropagation()}>
            {deal.deal_summary && <div className="dcard-summary">{deal.deal_summary}</div>}
            {deal.action_headline && (
              <div className="dcard-action-rec">
                <span style={{ fontSize: 14, flex: "none" }}>{"💡"}</span>
                <span><b>Acción recomendada:</b> {deal.action_headline}</span>
              </div>
            )}
            <div className="dcard-dates">
              <span className="dp"><span className="dp-l">Account:</span><span className="dp-v num">{fmtDate(deal.close_date_hs)}</span></span>
              <span className="dp"><span className="dp-l">Closzr:</span><span className="dp-v num">{fmtDate(deal.estimated_close_date)}</span></span>
              {aligned
                ? <span className="chip chip-g">{"✓"} Alineados</span>
                : <span className="chip chip-a">{"⚠"} Fechas distintas</span>}
            </div>

            <div className="fc-sel">
              <label>Forecast:</label>
              {fcCats.map(c => (
                <button key={c} className={`fc-opt${curFc === c ? " on" : ""}`}
                  onClick={e => { e.stopPropagation(); changeFc(deal.deal_id, name, curFc || c, c); }}>
                  {c}
                </button>
              ))}
            </div>

            {!mode ? (
              <div className="abtns">
                {mainActs.map(a => (
                  <button key={a.mode} className={`btn-b ${a.cls}`}
                    onClick={e => { e.stopPropagation(); setActionMode(prev => ({ ...prev, [dk]: a.mode })); }}>
                    {a.label}
                  </button>
                ))}
                {lostAct && (
                  <button className="lost-lnk"
                    onClick={e => { e.stopPropagation(); setActionMode(prev => ({ ...prev, [dk]: "lost" })); }}>
                    {"✕"} {lostAct.label}
                  </button>
                )}
              </div>
            ) : (
              <ConfirmFlow dk={dk} deal={deal} mode={mode} secNum={sec.num}
                onCancel={() => setActionMode(prev => { const n = { ...prev }; delete n[dk]; return n; })}
                onConfirm={() => doAction(dk, deal, mode, sec.num)}
                cfmLabel={cfmLabels[mode]}
                chipCls={chipCls[mode]}
                btnCls={btnCls[mode]}
              />
            )}

            {dealEntries.length > 0 && (
              <div className="dlog">
                {dealEntries.map((e, i) => {
                  const ico = e.type === "note" ? "📝" : e.type === "change" ? "📅" : e.type === "fcChange" ? "📊" : "🚩";
                  const txt = e.type === "change" ? <><b>{e.field}:</b> {e.old_val} {"→"} {e.new_val}{e.note ? ` — ${e.note}` : ""}</>
                    : e.type === "commitment" ? <><b>Compromiso:</b> {e.note}</>
                    : e.type === "fcChange" ? <><b>Forecast:</b> {e.old_val} {"→"} {e.new_val}</>
                    : <>{e.note}</>;
                  return (
                    <div key={i} className="log-e">
                      <span className="ico">{ico}</span>
                      <span className="txt">{txt}</span>
                      <span className="time">{new Date(e.at).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  /* ── render: check item ── */
  const renderCheckItem = (item: CheckItem, sec: Section) => {
    const ck = !!checks[item.id];
    const op = !!openChecks[item.id];
    const ds = itemDeals(item);
    const hd = ds.length > 0;
    const hq = !!(item.query || item.queries);
    const iNotes = entries.filter(e => e.deal_id === `item:${item.id}`);
    const guideOpen = collGuide[item.id] === true;

    return (
      <div key={item.id} className="chk">
        <div className="chk-row" onClick={() => setOpenChecks(prev => ({ ...prev, [item.id]: !prev[item.id] }))}>
          <span className={`cb${ck ? " done" : ""}`}
            onClick={e => { e.stopPropagation(); toggleCheck(item.id); }}>
            {ck ? "✓" : ""}
          </span>
          <span className={`chk-txt${ck ? " done" : ""}`}>{item.text}</span>
          {hd && (
            <span className="chk-cnt"><span className="num">{ds.length}</span> deal{ds.length !== 1 ? "s" : ""}</span>
          )}
          {!hd && hq && <span className="chk-zero">0 deals</span>}
          <SvgChev rot={op ? 0 : -90} />
        </div>

        {op && (
          <>
            {item.guide && (
              <>
                <div className="guide-tog"
                  onClick={() => setCollGuide(prev => ({ ...prev, [item.id]: !prev[item.id] }))}>
                  <span style={{ display: "inline-block", transform: `rotate(${guideOpen ? 90 : 0}deg)`, transition: "transform .15s" }}>{"▸"}</span>
                  {" "}Guía ({item.guide.length})
                </div>
                {guideOpen && (
                  <div className="guide">
                    {item.guide.map((g, i) => (
                      <div key={i} className="guide-i"><span className="guide-b" /><span>{g}</span></div>
                    ))}
                  </div>
                )}
              </>
            )}
            {hd && <div className="deal-grid">{ds.map(d => renderDealCard(d, item, sec))}</div>}
            <div className="note-area">
              <div className="cfm-row">
                <input type="text" className="cfm-in"
                  placeholder="Nota sobre este punto..."
                  value={noteInputs[item.id] || ""}
                  onChange={e => setNoteInputs(prev => ({ ...prev, [item.id]: e.target.value }))}
                  onKeyDown={e => { if (e.key === "Enter") addNote(item.id); }}
                />
                <button className="cfm-btn" onClick={() => addNote(item.id)}>Guardar {"✓"}</button>
              </div>
              {iNotes.length > 0 && (
                <div className="dlog" style={{ marginTop: 8 }}>
                  {iNotes.map((e, i) => (
                    <div key={i} className="log-e">
                      <span className="ico">{"📝"}</span>
                      <span className="txt">{e.note}</span>
                      <span className="time">{new Date(e.at).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    );
  };

  /* ── render: session sections ── */
  const renderSession = () => (
    <div className="secs">
      {week.sections.map(sec => {
        const t = TONE[sec.tone] || TONE.blue;
        const sk = `${weekType}-${sec.num}`;
        const col = collSec[sk];
        let dn = 0;
        sec.items.forEach(i => { if (checks[i.id]) dn++; });
        const tot = sec.items.length;

        return (
          <div key={sec.num} className="sec">
            <div className="sec-h" onClick={() => setCollSec(prev => ({ ...prev, [sk]: !prev[sk] }))}>
              <span className="sec-num" style={{ background: t.bg, color: t.fg }}>{sec.num}</span>
              <span className="sec-title">{sec.title}</span>
              <span className="sec-time">{sec.time} min</span>
              <span className="sec-prog" style={{
                background: dn === tot && tot > 0 ? "var(--green-tint)" : t.bg,
                color: dn === tot && tot > 0 ? "var(--green-ink)" : t.fg,
              }}>{dn}/{tot}</span>
              <SvgChev rot={col ? -90 : 0} />
            </div>
            {!col && (
              <div className="sec-body">
                {sec.items.map(item => renderCheckItem(item, sec))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  /* ── render: live summary ── */
  const renderLiveSum = () => {
    const total = entries.length;

    return (
      <div className="sess-sum">
        <div className="sess-sum-h" onClick={() => setCollSum(!collSum)}>
          <span className="sec-num" style={{ background: "var(--indigo-tint)", color: "var(--indigo)" }}>{"📋"}</span>
          <span className="sess-sum-title">RESUMEN DE SESIÓN</span>
          <span className="sess-sum-badge" style={{
            background: total > 0 ? "var(--indigo-tint)" : "var(--paper-2)",
            color: total > 0 ? "var(--indigo)" : "var(--ink-4)",
          }}>{total} acción{total !== 1 ? "es" : ""}</span>
          <SvgChev rot={collSum ? -90 : 0} />
        </div>

        {!collSum && (
          <div className="sess-sum-body">
            {total === 0 ? (
              <div className="ss-empty">Aún no hay acciones registradas en esta sesión.</div>
            ) : (
              <>
                {week.sections.map(sec => {
                  const secEntries = entries.filter(e => e.section === sec.num);
                  if (!secEntries.length) return null;
                  const sk = `sum-${sec.num}`;
                  const isOpen = collSumSec[sk] !== false;
                  const t = TONE[sec.tone] || TONE.blue;

                  const dateChanges = secEntries.filter(e => e.type === "change" && e.field === "close_date");
                  const kept = secEntries.filter(e => e.type === "note" && e.deal_id && !e.deal_id.startsWith("item:") && (e.note || "").startsWith("Fecha mantenida"));
                  const lost = secEntries.filter(e => e.type === "change" && e.new_val === "Closed Lost");
                  const commits = secEntries.filter(e => e.type === "commitment");
                  const otherNotes = secEntries.filter(e => e.type === "note" && e.deal_id && !e.deal_id.startsWith("item:") && !(e.note || "").startsWith("Fecha mantenida"));

                  return (
                    <div key={sec.num} className="ss-sec">
                      <div className="ss-sec-h" onClick={() => setCollSumSec(prev => ({ ...prev, [sk]: prev[sk] === false }))}>
                        <span className="sec-num" style={{ background: t.bg, color: t.fg, width: 20, height: 20, fontSize: 9 }}>{sec.num}</span>
                        <span className="ss-sec-title">{sec.title}</span>
                        <span className="ss-sec-cnt">{secEntries.length}</span>
                        <SvgChev rot={isOpen ? 0 : -90} />
                      </div>
                      {isOpen && (
                        <div className="ss-sec-body">
                          {dateChanges.length > 0 && (
                            <div className="ss-sub">
                              <span className="ss-sub-title">{"📅"} Cambios de fecha ({dateChanges.length})</span>
                              {dateChanges.map((e, i) => (
                                <div key={i} className="ss-item"><span className="ico">{"📅"}</span><span><b>{e.deal_name}:</b> {e.old_val} {"→"} {e.new_val}{e.note ? ` — ${e.note}` : ""}</span></div>
                              ))}
                            </div>
                          )}
                          {kept.length > 0 && (
                            <div className="ss-sub">
                              <span className="ss-sub-title">{"✓"} Fechas mantenidas ({kept.length})</span>
                              {kept.map((e, i) => (
                                <div key={i} className="ss-item"><span className="ico">{"✓"}</span><span><b>{e.deal_name}:</b> {e.note}</span></div>
                              ))}
                            </div>
                          )}
                          {lost.length > 0 && (
                            <div className="ss-sub">
                              <span className="ss-sub-title">{"✕"} Moved to Lost ({lost.length})</span>
                              {lost.map((e, i) => (
                                <div key={i} className="ss-item"><span className="ico" style={{ color: "var(--red-ink)" }}>{"✕"}</span><span><b>{e.deal_name}:</b> {e.note}</span></div>
                              ))}
                            </div>
                          )}
                          {commits.length > 0 && (
                            <div className="ss-sub">
                              <span className="ss-sub-title">{"🚩"} Compromisos ({commits.length})</span>
                              {commits.map((e, i) => (
                                <div key={i} className="ss-item"><span className="ico">{"🚩"}</span><span><b>{e.deal_name}:</b> {e.note}</span></div>
                              ))}
                            </div>
                          )}
                          {otherNotes.length > 0 && (
                            <div className="ss-sub">
                              <span className="ss-sub-title">{"📝"} Notas ({otherNotes.length})</span>
                              {otherNotes.map((e, i) => (
                                <div key={i} className="ss-item"><span className="ico">{"📝"}</span><span><b>{e.deal_name}:</b> {e.note}</span></div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}

                {(() => {
                  const fcCh = entries.filter(e => e.type === "fcChange");
                  const itemNotes = entries.filter(e => e.type === "note" && e.deal_id?.startsWith("item:"));
                  if (!fcCh.length && !itemNotes.length) return null;
                  const gk = "sum-general";
                  const gOpen = collSumSec[gk] !== false;
                  return (
                    <div className="ss-sec">
                      <div className="ss-sec-h" onClick={() => setCollSumSec(prev => ({ ...prev, [gk]: prev[gk] === false }))}>
                        <span className="sec-num" style={{ background: "var(--indigo-tint)", color: "var(--indigo)", width: 20, height: 20, fontSize: 9 }}>G</span>
                        <span className="ss-sec-title">GENERAL</span>
                        <span className="ss-sec-cnt">{fcCh.length + itemNotes.length}</span>
                        <SvgChev rot={gOpen ? 0 : -90} />
                      </div>
                      {gOpen && (
                        <div className="ss-sec-body">
                          {fcCh.length > 0 && (
                            <div className="ss-sub">
                              <span className="ss-sub-title">{"📊"} Cambios de forecast ({fcCh.length})</span>
                              {fcCh.map((e, i) => (
                                <div key={i} className="ss-item"><span className="ico">{"📊"}</span><span><b>{e.deal_name}:</b> {e.old_val} {"→"} {e.new_val}</span></div>
                              ))}
                            </div>
                          )}
                          {itemNotes.length > 0 && (
                            <div className="ss-sub">
                              <span className="ss-sub-title">{"📝"} Notas generales ({itemNotes.length})</span>
                              {itemNotes.map((e, i) => (
                                <div key={i} className="ss-item"><span className="ico">{"📝"}</span><span>{e.note}</span></div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })()}
              </>
            )}
          </div>
        )}
      </div>
    );
  };

  /* ── render: close modal ── */
  const renderCloseModal = () => {
    const changes = entries.filter(e => e.type === "change");
    const commits = entries.filter(e => e.type === "commitment");
    const fcCh = entries.filter(e => e.type === "fcChange");
    const notes = entries.filter(e => e.type === "note" && e.deal_id && !e.deal_id.startsWith("item:"));
    const itemNotes = entries.filter(e => e.type === "note" && e.deal_id?.startsWith("item:"));
    const dealsReviewed = [...new Set(entries.filter(e => e.deal_id && !e.deal_id.startsWith("item:")).map(e => e.deal_name))];
    const lostCount = entries.filter(e => e.type === "change" && e.new_val === "Closed Lost").length;

    return (
      <div className="close-overlay" onClick={() => setShowCloseModal(false)}>
        <div className="close-modal" onClick={e => e.stopPropagation()}>
          <div className="close-modal-h">
            <h3>Resumen de sesión — {week.label} {week.subtitle}</h3>
            <button className="close-modal-x" onClick={() => setShowCloseModal(false)}>{"✕"}</button>
          </div>
          <div className="close-modal-body">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}>
              <div className="kpi"><span className="kpi-l">Progreso</span><span className="kpi-v num" style={{ color: pct === 100 ? "var(--green-ink)" : "var(--indigo)" }}>{pct}%</span><span className="kpi-s">{doneChecks}/{totalChecks} checks</span></div>
              <div className="kpi"><span className="kpi-l">Deals revisados</span><span className="kpi-v num">{dealsReviewed.length}</span></div>
              <div className="kpi"><span className="kpi-l">Acciones</span><span className="kpi-v num">{changes.length + commits.length}</span><span className="kpi-s">{changes.length} cambios {"·"} {commits.length} compromisos</span></div>
              <div className="kpi"><span className="kpi-l">Deals lost</span><span className="kpi-v num" style={{ color: lostCount > 0 ? "var(--red-ink)" : "var(--ink-3)" }}>{lostCount}</span><span className="kpi-s">{fcCh.length} forecast changes</span></div>
            </div>

            {changes.length > 0 && (
              <div className="ss-group"><div className="ss-group-title">{"📅"} Cambios ({changes.length})</div>
                {changes.map((e, i) => {
                  const isLost = e.new_val === "Closed Lost";
                  return <div key={i} className="ss-item"><span className="ico">{isLost ? "✕" : "📅"}</span><span><b>{e.deal_name}:</b> {e.old_val} {"→"} {e.new_val}{e.note ? ` — ${e.note}` : ""}</span></div>;
                })}
              </div>
            )}
            {commits.length > 0 && (
              <div className="ss-group"><div className="ss-group-title">{"🚩"} Compromisos ({commits.length})</div>
                {commits.map((e, i) => <div key={i} className="ss-item"><span className="ico">{"🚩"}</span><span><b>{e.deal_name}:</b> {e.note}</span></div>)}
              </div>
            )}
            {fcCh.length > 0 && (
              <div className="ss-group"><div className="ss-group-title">{"📊"} Forecast changes ({fcCh.length})</div>
                {fcCh.map((e, i) => <div key={i} className="ss-item"><span className="ico">{"📊"}</span><span><b>{e.deal_name}:</b> {e.old_val} {"→"} {e.new_val}</span></div>)}
              </div>
            )}
            {(notes.length > 0 || itemNotes.length > 0) && (
              <div className="ss-group"><div className="ss-group-title">{"📝"} Notas ({notes.length + itemNotes.length})</div>
                {notes.map((e, i) => <div key={i} className="ss-item"><span className="ico">{"📝"}</span><span><b>{e.deal_name}:</b> {e.note}</span></div>)}
                {itemNotes.map((e, i) => <div key={`in-${i}`} className="ss-item"><span className="ico">{"📝"}</span><span>{e.note}</span></div>)}
              </div>
            )}
          </div>
          <div className="close-modal-foot">
            <button className="cfm-cancel" onClick={() => setShowCloseModal(false)}>Volver a la sesión</button>
            <button className="cfm-go green" onClick={() => setShowCloseModal(false)}>Guardar sesión {"✓"}</button>
          </div>
        </div>
      </div>
    );
  };

  /* ── render: histórico ── */
  const renderHist = () => {
    const byMonth = new Map<string, OOSession[]>();
    for (const s of history) {
      const ym = s.session_date.slice(0, 7);
      if (!byMonth.has(ym)) byMonth.set(ym, []);
      byMonth.get(ym)!.push(s);
    }
    for (const sessions of byMonth.values()) sessions.sort((a, b) => a.week_type - b.week_type);

    if (history.length === 0) {
      return <div className="hist-wrap"><div className="ss-empty">No hay sesiones anteriores registradas para {selectedRep}.</div></div>;
    }

    return (
      <div className="hist-wrap">
        {[...byMonth.entries()].map(([ym, sessions]) => (
          <div key={ym} className="hist-month">
            <h4 className="hist-month-label">{fmtYM(ym)}</h4>
            <div className="hist-cards">
              {sessions.map(s => {
                const w = WEEKS[s.week_type];
                if (!w) return null;
                const tc = w.sections.reduce((a, sec) => a + sec.items.length, 0);
                const dc = w.sections.reduce((a, sec) => a + sec.items.filter(i => s.checks?.[i.id]).length, 0);
                const done = dc >= tc;
                const hkey = `${ym}-${s.week_type}`;
                const expanded = histOpen === hkey;
                const eCount = (s.entries || []).length;

                return (
                  <Fragment key={hkey}>
                    <div className={`hist-card ${done ? "done" : "partial"} ${expanded ? "open" : ""}`}
                      onClick={() => setHistOpen(histOpen === hkey ? null : hkey)}>
                      <div className="hist-card-h">
                        <span className="hist-card-w">{w.label}</span>
                        <span className={`hist-card-score ${done ? "done" : "partial"}`}>{dc}/{tc}</span>
                      </div>
                      <div className="hist-card-date">{s.session_date}</div>
                      <div className="hist-card-meta">{eCount} acción{eCount !== 1 ? "es" : ""}</div>
                    </div>

                    {expanded && (
                      <div className="hist-detail">
                        {w.sections.map(sec => {
                          const sdc = sec.items.filter(i => s.checks?.[i.id]).length;
                          return (
                            <div key={sec.num} className="hist-sec">
                              <div className="hist-sec-h">{sec.title} <span className="hist-sec-score">{sdc}/{sec.items.length}</span></div>
                              {sec.items.map(i => {
                                const ch = !!(s.checks?.[i.id]);
                                return <div key={i.id} className={`hist-check ${ch ? "done" : ""}`}><span>{ch ? "☑" : "☐"}</span> {i.text}</div>;
                              })}
                            </div>
                          );
                        })}
                        {s.entries && s.entries.length > 0 && (
                          <div className="hist-entries">
                            <div className="hist-entries-title">Acciones registradas</div>
                            {s.entries.map((e, i) => {
                              const ico = e.type === "change" ? (e.new_val === "Closed Lost" ? "✕" : "📅")
                                : e.type === "commitment" ? "🚩"
                                : e.type === "fcChange" ? "📊"
                                : "📝";
                              const txt = e.type === "change" ? <><b>{e.deal_name}:</b> {e.field}: {e.old_val} {"→"} {e.new_val}{e.note ? ` — ${e.note}` : ""}</>
                                : e.type === "commitment" ? <><b>{e.deal_name}:</b> {e.note}</>
                                : e.type === "fcChange" ? <><b>{e.deal_name}:</b> {e.old_val} {"→"} {e.new_val}</>
                                : <>{e.note}</>;
                              return (
                                <div key={i} className="hist-entry">
                                  <span className="ico">{ico}</span>
                                  <span>{txt}</span>
                                  <span className="time" style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-4)", flex: "none" }}>
                                    {new Date(e.at).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </Fragment>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    );
  };

  /* ── MAIN RENDER ── */
  return (
    <>
      {/* Toolbar */}
      <div className="tb">
        <h2>1:1 Review</h2>
        <span className="tb-sub">{"·"} Sesiones semanales</span>
        <div className="tb-r">
          {reps.length > 0 && (
            <label className="oo-sel">
              <span className="av">{getInitials(selectedRep)}</span>
              <select value={selectedRep} onChange={e => { setSelectedRep(e.target.value); resetOnRepChange(); }}>
                {reps.map(r => <option key={r}>{r}</option>)}
              </select>
              <SvgChev rot={0} />
            </label>
          )}
          <label className="oo-sel">
            <select value={month} onChange={e => setMonth(e.target.value)}>
              {mOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <SvgChev rot={0} />
          </label>
        </div>
      </div>

      {/* KPIs */}
      <div className="kpis">
        <div className="kpi"><span className="kpi-l">Pipeline</span><span className="kpi-v num">{fmtMRR(kpi.total)}</span><span className="kpi-s">{kpi.cnt} deals</span></div>
        <div className="kpi">
          <span className="kpi-l">M+0 {MONTH_NAMES[new Date().getMonth()]}</span>
          <span className="kpi-v num">{fmtMRR(kpi.m0Mrr)}</span>
          <span className="kpi-s">{kpi.m0Cnt} deals {"·"} {kpi.m0Close} esta semana</span>
        </div>
        <div className="kpi">
          <span className="kpi-l">M+1 {MONTH_NAMES[(new Date().getMonth() + 1) % 12]}</span>
          <span className="kpi-v num">{fmtMRR(kpi.m1Mrr)}</span>
          <span className="kpi-s">{kpi.m1Cnt} deals</span>
        </div>
        <div className="kpi">
          <span className="kpi-l">Coverage M+0</span>
          <span className="kpi-v num" style={{ color: kpi.covPct >= 80 ? "var(--green-ink)" : kpi.covPct >= 50 ? "var(--amber-ink)" : "var(--red-ink)" }}>{kpi.covPct}%</span>
          <span className="kpi-s">{fmtMRR(kpi.m0Mrr)} / {fmtMRR(kpi.target)}</span>
          <div className="kpi-bar">
            <div style={{ width: `${Math.min(100, kpi.covPct)}%`, background: kpi.covPct >= 80 ? "var(--green)" : kpi.covPct >= 50 ? "var(--amber)" : "var(--red)" }} />
          </div>
        </div>
      </div>

      {/* Week cards */}
      <div className="wks">
        {WEEKS.map((wk, i) => {
          const on = weekType === i;
          const locked = isCurrent && i !== curWk;
          let wt = 0, wd = 0;
          wk.sections.forEach(s => s.items.forEach(it => { wt++; if (on && checks[it.id]) wd++; }));

          return (
            <div key={i} className={`wc${on ? " on" : ""}${locked ? " locked" : ""}`}
              title={locked ? "Semana no activa" : undefined}
              onClick={() => { if (!locked) { setWeekType(i); setOpenDeals({}); setOpenChecks({}); setActionMode({}); } }}>
              <span className="wc-n">{wk.label} {i === curWk && isCurrent && <span className="badge wip">{"●"}</span>}</span>
              <span className="wc-t">{wk.subtitle}</span>
              <span className="wc-d">{wk.duration} min</span>
              {on && wt > 0 && <span className="wc-c num">{wd}/{wt}</span>}
            </div>
          );
        })}
        <div className="pbar">
          <div className="pbar-b"><div style={{ width: `${pct}%`, background: pct === 100 ? "var(--green)" : "var(--indigo)" }} /></div>
          <span className="pbar-t num">{pct}%</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab${tab === "session" ? " on" : ""}`} onClick={() => setTab("session")}>Sesión actual</button>
        <button className={`tab${tab === "hist" ? " on" : ""}`} onClick={() => setTab("hist")}>Histórico</button>
      </div>

      {/* Content */}
      {tab === "session" ? (
        loading ? (
          <p style={{ color: "var(--ink-3)", padding: 24 }}>Cargando deals...</p>
        ) : (
          <>
            {renderSession()}
            {renderLiveSum()}
            <button className="close-btn" onClick={() => setShowCloseModal(true)}>
              Cerrar sesión — ver resumen completo
            </button>
          </>
        )
      ) : (
        renderHist()
      )}

      {/* Close modal */}
      {showCloseModal && renderCloseModal()}

      {/* HubSpot error toast */}
      {hsError && (
        <div className="hs-toast" onClick={() => setHsError(null)}>
          {"⚠"} {hsError}
        </div>
      )}
    </>
  );
}

/* ── Confirm Flow Component ── */
function ConfirmFlow({ dk, deal, mode, secNum, onCancel, onConfirm, cfmLabel, chipCls, btnCls }: {
  dk: string; deal: OODeal; mode: ActionMode; secNum: string;
  onCancel: () => void; onConfirm: () => void;
  cfmLabel: string; chipCls: string; btnCls: string;
}) {
  const [valid, setValid] = useState(false);

  const validate = useCallback(() => {
    const rs = document.getElementById(`rs-${dk}`) as HTMLInputElement | null;
    const dt = document.getElementById(`dt-${dk}`) as HTMLInputElement | null;
    const hasText = !!rs?.value.trim();
    if (mode === "change") setValid(hasText && !!dt?.value);
    else setValid(hasText);
  }, [dk, mode]);

  return (
    <div className="cfm">
      <div className="cfm-title">
        <span className={`mode-chip ${chipCls}`} style={{ display: "inline-flex", padding: "2px 10px", borderRadius: "var(--r-pill)", fontSize: 11, fontWeight: 700 }}>
          {cfmLabel}
        </span>
      </div>

      {mode === "change" && (
        <div className="cfm-field">
          <label>Nueva fecha:</label>
          <input type="date" id={`dt-${dk}`} onChange={validate} onClick={e => e.stopPropagation()} />
        </div>
      )}

      {mode === "lost" && (
        <div className="cfm-field">
          <label>Motivo:</label>
          <select id={`lr-${dk}`} onClick={e => e.stopPropagation()} onChange={validate}>
            {LOST_REASONS.map(r => <option key={r}>{r}</option>)}
          </select>
        </div>
      )}

      <div className="cfm-field">
        <label>{mode === "lost" ? "Detalle:" : mode === "keep" ? "Comentario:" : mode === "action" ? "Acción:" : mode === "push" ? "Plan:" : "Motivo:"}</label>
        <input type="text" id={`rs-${dk}`}
          placeholder={mode === "change" ? "¿Por qué se cambia la fecha? (obligatorio)"
            : mode === "lost" ? "Contexto adicional (obligatorio)"
            : mode === "keep" ? "¿Por qué se mantiene? (obligatorio)"
            : mode === "action" ? "¿Qué acción concreta? ¿Para cuándo? (obligatorio)"
            : "¿Qué hace falta para cerrar antes? (obligatorio)"}
          onInput={validate}
          onClick={e => e.stopPropagation()}
        />
      </div>

      <div className="cfm-foot">
        <button className="cfm-cancel" onClick={e => { e.stopPropagation(); onCancel(); }}>Cancelar</button>
        <button className={`cfm-go ${btnCls}`} disabled={!valid} onClick={e => { e.stopPropagation(); onConfirm(); }}>Confirmar</button>
      </div>
    </div>
  );
}
