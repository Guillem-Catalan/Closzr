/* ============================================================
   CLOSZR — TO-DOs: daily action list for reps
   4 sections: Meetings · Actions today · Overdue · Done
   ============================================================ */
import { useState, useMemo } from "react";
import { Icon, Chip, StageChip, fmtMRR } from "../components";
import { useData } from "../../data/store";
import type { ActionItem, DealRow } from "../../data/store";
import { supabase } from "../../data/supabase";
import { hubspotDealUrl, BUCKET_STYLE, ACTION_TYPE_ICON } from "../../display";
import { distinctTeams, distinctOwnersFromActions, normalize, repNameToEmail } from "../../data/filters";

type TimeFilter = "hoy" | "semana" | "next_week" | "mes";

const TYPE_ICON = ACTION_TYPE_ICON;

function getSpainToday(): string {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Madrid" });
}

const DAY_NAMES = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
// smartWhenLabel removed — we now use smartDateLabel(f.due) directly

function smartDateLabel(dueDate: string | null): string {
  if (!dueDate) return "pendiente";
  const today = getSpainToday();
  const due = dueDate.slice(0, 10);
  const diffMs = new Date(due).getTime() - new Date(today).getTime();
  const diffDays = Math.round(diffMs / 86_400_000);

  if (diffDays === 0) return "hoy";
  if (diffDays === 1) return "mañana";
  if (diffDays === -1) return "ayer";
  if (diffDays < -1) {
    const dd = due.slice(8, 10);
    const mm = due.slice(5, 7);
    return `${dd}/${mm} (hace ${Math.abs(diffDays)}d)`;
  }
  if (diffDays <= 6) {
    const d = new Date(due);
    return DAY_NAMES[d.getDay()] + " " + due.slice(8, 10) + "/" + due.slice(5, 7);
  }
  if (diffDays <= 13) {
    const d = new Date(due);
    return "próx. " + DAY_NAMES[d.getDay()] + " " + due.slice(8, 10) + "/" + due.slice(5, 7);
  }
  return due.slice(8, 10) + "/" + due.slice(5, 7);
}

function getEndOfWeek(today: string): string {
  const d = new Date(today);
  const dow = d.getDay();
  d.setDate(d.getDate() + (7 - dow));
  return d.toISOString().slice(0, 10);
}

function getNextWeekEnd(today: string): string {
  const d = new Date(getEndOfWeek(today));
  d.setDate(d.getDate() + 7);
  return d.toISOString().slice(0, 10);
}

function getEndOfMonth(today: string): string {
  const d = new Date(today);
  return new Date(d.getFullYear(), d.getMonth() + 1, 0).toISOString().slice(0, 10);
}

/* ---- Action row (reused for actions + overdue) ---- */
function ActionRow({ a, onOpen, onToggle, isDone, today }: {
  a: ActionItem; onOpen: () => void; onToggle: () => void; isDone: boolean; today: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const bs = BUCKET_STYLE[a.bucket] || BUCKET_STYLE.pipeline;
  const isOverdue = !isDone && a.actionDueDate && a.actionDueDate < today;

  return (
    <>
      <div style={{
        display: "grid", gridTemplateColumns: "32px 1fr 80px 70px 24px",
        gap: 12, padding: "10px 18px", alignItems: "center", cursor: "pointer",
        borderBottom: "1px solid var(--line-2)", transition: "background .12s",
        background: isDone ? "var(--card-2)" : isOverdue ? "rgba(216,68,47,.03)" : "transparent",
        opacity: isDone ? 0.55 : 1,
      }} onClick={() => setExpanded(!expanded)}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <button onClick={e => { e.stopPropagation(); onToggle(); }} style={{
            width: 22, height: 22, borderRadius: 99,
            border: isDone ? "none" : "2px solid var(--line-ink)",
            background: isDone ? "var(--green)" : "none",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer", transition: "all .15s", color: isDone ? "#fff" : "var(--ink-4)",
          }} title={isDone ? "Desmarcar" : "Marcar como hecho"}>
            <Icon name="check" size={12} stroke={2.5} />
          </button>
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <Chip tone={bs.tone} style={{ fontSize: 10, padding: "1px 6px" }}>
              <Icon name={TYPE_ICON[a.actionType] || "sparkle"} size={9} stroke={2} /> {a.actionType}
            </Chip>
            <Chip tone={bs.tone} style={{ fontSize: 10, padding: "1px 6px" }}>{bs.label}</Chip>
            {isOverdue && <Chip tone="red" style={{ fontSize: 10, padding: "1px 6px" }}>atrasado</Chip>}
            <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{smartDateLabel(a.actionDueDate)}</span>
          </div>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--ink)", lineHeight: 1.4, textDecoration: isDone ? "line-through" : "none" }}>
            {a.actionWho && a.actionWho !== "—" && <span style={{ color: "var(--indigo)", fontWeight: 700 }}>{a.actionWho} → </span>}
            {a.actionHeadline}
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 1, display: "flex", alignItems: "center", gap: 4 }}>
            {a.dealName} · {fmtMRR(a.dealMrr)} · {a.dealStage}
            {a.hsId && (
              <a href={hubspotDealUrl(a.hsId!)}
                target="_blank" rel="noopener noreferrer" title="Abrir en HubSpot"
                onClick={e => e.stopPropagation()}
                style={{ display: "inline-flex", color: "var(--ink-4)", flex: "none" }}>
                <svg width={12} height={12} viewBox="0 0 24 24" fill="currentColor"><path d="M17.63 13.31a3.3 3.3 0 01-1.63.43 3.37 3.37 0 01-3.37-3.37c0-.6.16-1.17.44-1.66l-2.3-2.3a.99.99 0 01-.15-.17 2.48 2.48 0 01-1.52.53V9.3a1.35 1.35 0 110-2.7V4.06A2.06 2.06 0 007.04 2a2.06 2.06 0 00-2.06 2.06v2.53a2.73 2.73 0 00.88 5.31h.05a2.7 2.7 0 001.79-.68l2.38 2.38a3.34 3.34 0 00-.46 1.69A3.37 3.37 0 0013 18.66a3.3 3.3 0 001.86-.57l2.74 2.74a1.1 1.1 0 001.56-1.56zM13 16.92a1.63 1.63 0 110-3.25 1.63 1.63 0 010 3.25z"/></svg>
              </a>
            )}
          </div>
        </div>
        <div>
          <button className="cz-btn-soft" style={{ fontSize: 10, padding: "3px 8px" }} onClick={e => { e.stopPropagation(); onOpen(); }}>
            Deal <Icon name="arrowRight" size={10} stroke={2} />
          </button>
        </div>
        <div className="num" style={{ fontWeight: 700, fontSize: 13 }}>{fmtMRR(a.dealMrr)}</div>
        <div><Icon name="chevDown" size={13} style={{ color: "var(--ink-3)", transform: expanded ? "none" : "rotate(-90deg)", transition: "transform .18s" }} /></div>
      </div>
      {expanded && !isDone && (
        <div style={{ padding: "12px 18px 14px 62px", background: "var(--card-2)", borderBottom: "1px solid var(--line-2)", display: "flex", flexDirection: "column", gap: 8 }}>
          {a.actionDetail && <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: "var(--ink-2)" }}>{a.actionDetail}</p>}
          {a.followUps.length > 0 && (
            <div>
              <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Siguientes pasos</span>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 4 }}>
                {a.followUps.map((f, i) => (
                  <li key={i} style={{ display: "flex", gap: 6, fontSize: 12.5, lineHeight: 1.5, color: "var(--ink-2)" }}>
                    <Chip tone="ink" style={{ fontSize: 9, padding: "0px 4px", flex: "none", marginTop: 2 }}>{f.type}</Chip>
                    <span>{f.who && <b>{f.who} → </b>}{f.text}{f.due ? <span style={{ color: "var(--ink-3)" }}> — {smartDateLabel(f.due)}</span> : f.when !== "pendiente" && <span style={{ color: "var(--ink-3)" }}> — {f.when}</span>}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </>
  );
}

/* ---- Meeting row ---- */
function MeetingRow({ d, onOpen }: { d: DealRow; onOpen: () => void }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "32px 1fr 80px 70px 24px",
      gap: 12, padding: "10px 18px", alignItems: "center",
      borderBottom: "1px solid var(--line-2)", cursor: "pointer",
    }} onClick={onOpen}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ width: 22, height: 22, borderRadius: 99, background: "var(--indigo-tint)", color: "var(--indigo)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon name="calendar" size={12} stroke={2} />
        </span>
      </div>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <Chip tone="indigo" style={{ fontSize: 10, padding: "1px 6px" }}>MEETING</Chip>
        </div>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--ink)", lineHeight: 1.4 }}>{d.deal}</div>
        <div style={{ fontSize: 12, color: "var(--ink-3)" }}>{d.owner} · {fmtMRR(d.mrr)} · {d.stage}</div>
      </div>
      <div><StageChip stage={d.stage} /></div>
      <div className="num" style={{ fontWeight: 700, fontSize: 13 }}>{fmtMRR(d.mrr)}</div>
      <div><Icon name="arrowRight" size={13} style={{ color: "var(--ink-4)" }} /></div>
    </div>
  );
}

/* ---- Section header ---- */
function SectionHeader({ title, count, tone, collapsed, onToggle }: {
  title: string; count: number; tone: string; collapsed?: boolean; onToggle?: () => void;
}) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "12px 18px",
      background: `var(--${tone}-tint)`, borderBottom: "1px solid var(--line)",
      cursor: onToggle ? "pointer" : "default",
    }} onClick={onToggle}>
      <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 14, color: `var(--${tone}-ink)` }}>{title}</span>
      <Chip tone={tone} style={{ fontSize: 11 }}>{count}</Chip>
      {onToggle && <Icon name="chevDown" size={14} style={{ marginLeft: "auto", color: `var(--${tone}-ink)`, transform: collapsed ? "rotate(-90deg)" : "none", transition: "transform .18s" }} />}
    </div>
  );
}

/* ============================================================ */
export default function TodoView({ onOpen }: { onOpen: (row: any, tab: string) => void }) {
  const D = useData();
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("hoy");
  const [teamFilter, setTeamFilter] = useState("");
  const [repFilter, setRepFilter] = useState("");
  const [search, setSearch] = useState("");
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());
  const [showOverdue, setShowOverdue] = useState(true);
  const [showDone, setShowDone] = useState(false);
  const TODO_PAGE = 30;
  const [actionsVisible, setActionsVisible] = useState(TODO_PAGE);
  const [overdueVisible, setOverdueVisible] = useState(TODO_PAGE);

  const today = getSpainToday();
  const repNorm = repFilter ? normalize(repFilter) : "";
  const repEmail = repFilter ? repNameToEmail(repFilter) : "";

  const allMeetingRows = useMemo(() => D.groups.flatMap(g => g.rows), [D.groups]);
  const teams = useMemo(() => {
    const fromDeals = distinctTeams(allMeetingRows);
    const fromActions = D.todos.map(a => a.team).filter(Boolean);
    return [...new Set([...fromDeals, ...fromActions])].sort();
  }, [allMeetingRows, D.todos]);
  const reps = useMemo(() => distinctOwnersFromActions(D.todos, teamFilter || undefined), [D.todos, teamFilter]);

  // Filter helper for rep matching
  const matchesRep = (owner: string, who?: string) => {
    if (!repFilter) return true;
    const on = normalize(owner || "");
    if (on === repNorm || on.startsWith(repNorm + " ")) return true;
    if (who) { const wn = normalize(who); if (wn === repNorm || wn.startsWith(repNorm + " ")) return true; }
    return false;
  };

  const matchesFilters = (a: { dealName?: string; deal?: string; dealOwner?: string; owner?: string; actionHeadline?: string; team?: string; actionWho?: string }) => {
    if (teamFilter && a.team !== teamFilter) return false;
    if (repFilter && !matchesRep(a.dealOwner || a.owner || "", a.actionWho)) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      const name = (a.dealName || a.deal || "").toLowerCase();
      const headline = (a.actionHeadline || "").toLowerCase();
      const owner = (a.dealOwner || a.owner || "").toLowerCase();
      if (!name.includes(q) && !headline.includes(q) && !owner.includes(q)) return false;
    }
    return true;
  };

  // 1. Meetings today (from same sources as Deals > Hoy)
  const meetings = useMemo(() => {
    if (timeFilter !== "hoy") return [];
    const allMeetingRows = D.groups.flatMap(g => g.rows);
    return allMeetingRows.filter(r => {
      if (!matchesFilters({ deal: r.deal, owner: r.owner, team: r.team })) return false;
      if (repFilter && r.meetingPaes && !r.meetingPaes.includes(repEmail)) {
        const on = normalize(r.owner || "");
        if (on !== repNorm && !on.startsWith(repNorm + " ")) return false;
      }
      return true;
    }).sort((a, b) => (a.hora || "zz").localeCompare(b.hora || "zz"));
  }, [D.groups, timeFilter, teamFilter, repFilter, search]);

  // Time range for current filter
  const getMaxDate = () => {
    if (timeFilter === "hoy") return today;
    if (timeFilter === "semana") return getEndOfWeek(today);
    if (timeFilter === "next_week") return getNextWeekEnd(today);
    return getEndOfMonth(today);
  };
  const getMinDate = () => {
    if (timeFilter === "next_week") return getEndOfWeek(today);
    return "2000-01-01";
  };

  // 2. Actions for the period (due_date = today or within range, NOT overdue)
  const todayActions = useMemo(() => {
    setActionsVisible(TODO_PAGE);
    const max = getMaxDate();
    const min = getMinDate();
    return D.todos
      .filter(a => !doneIds.has(a.id) && a.status === "pending")
      .filter(a => a.actionDueDate && a.actionDueDate >= today && a.actionDueDate <= max && a.actionDueDate > min)
      .filter(a => matchesFilters(a))
      .sort((a, b) => a.actionPriority - b.actionPriority || (b.dealMrr || 0) - (a.dealMrr || 0));
  }, [D.todos, doneIds, timeFilter, teamFilter, repFilter, search, today]);

  // 3. Overdue (due_date < today, still pending)
  const overdue = useMemo(() => {
    setOverdueVisible(TODO_PAGE);
    return D.todos
      .filter(a => !doneIds.has(a.id) && a.status === "pending")
      .filter(a => a.actionDueDate && a.actionDueDate < today)
      .filter(a => matchesFilters(a))
      .sort((a, b) => (b.actionDueDate || "").localeCompare(a.actionDueDate || "") || (b.dealMrr || 0) - (a.dealMrr || 0));
  }, [D.todos, doneIds, teamFilter, repFilter, search, today]);

  // 4. Done (marked in this session)
  const doneActions = useMemo(() => {
    return D.todos.filter(a => doneIds.has(a.id));
  }, [D.todos, doneIds]);

  // KPIs
  const meetingCount = meetings.length;
  const actionCount = todayActions.length;
  const overdueCount = overdue.length;
  const doneCount = doneIds.size;

  const handleToggleDone = async (id: string) => {
    if (doneIds.has(id)) {
      // Unmark
      setDoneIds(prev => { const next = new Set(prev); next.delete(id); return next; });
      try { await supabase.from("deal_actions").update({ status: "pending", completed_at: null }).eq("id", id); } catch {}
    } else {
      // Mark done
      setDoneIds(prev => new Set(prev).add(id));
      try { await supabase.from("deal_actions").update({ status: "done", completed_at: new Date().toISOString() }).eq("id", id); } catch {}
    }
  };

  const handleOpenDeal = (row: any) => {
    onOpen({ id: row.dealId || row.id, deal: row.dealName || row.deal, stage: row.dealStage || row.stage, mrr: row.dealMrr || row.mrr, owner: row.dealOwner || row.owner }, "hist");
  };

  return (
    <div className="cz-fc">
      {/* Toolbar */}
      <div className="cz-toolbar" style={{ marginBottom: 4 }}>
        <div className="cz-tb-title"><h2 className="display">TO-DOs</h2></div>
        <div className="cz-seg">
          {([["hoy", "Hoy"], ["semana", "Semana"], ["next_week", "Next week"], ["mes", "Mes"]] as const).map(([k, l]) => (
            <button key={k} className={timeFilter === k ? "on" : ""} onClick={() => setTimeFilter(k)}>{l}</button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <select className="cz-native-select" value={teamFilter} onChange={e => { setTeamFilter(e.target.value); setRepFilter(""); }}>
          <option value="">All Teams</option>
          {teams.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className="cz-native-select" value={repFilter} onChange={e => setRepFilter(e.target.value)}>
          <option value="">All PAEs</option>
          {reps.map((r: string) => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="cz-search">
          <Icon name="search" size={16} style={{ color: "var(--ink-3)" }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar…" />
        </label>
      </div>

      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
        <div className="cz-fc-kpi" style={{ padding: "14px 16px" }}>
          <span className="eyebrow" style={{ color: "var(--indigo)" }}>Meetings</span>
          <div className="cz-fc-kpi-v display" style={{ fontSize: 26, color: "var(--indigo)" }}>{meetingCount}</div>
        </div>
        <div className="cz-fc-kpi" style={{ padding: "14px 16px" }}>
          <span className="eyebrow">Acciones</span>
          <div className="cz-fc-kpi-v display" style={{ fontSize: 26 }}>{actionCount}</div>
        </div>
        <div className="cz-fc-kpi" style={{ padding: "14px 16px" }}>
          <span className="eyebrow" style={{ color: "var(--red-ink)" }}>Atrasadas</span>
          <div className="cz-fc-kpi-v display" style={{ fontSize: 26, color: "var(--red)" }}>{overdueCount}</div>
        </div>
        <div className="cz-fc-kpi" style={{ padding: "14px 16px" }}>
          <span className="eyebrow" style={{ color: "var(--green-ink)" }}>Hechas</span>
          <div className="cz-fc-kpi-v display" style={{ fontSize: 26, color: "var(--green)" }}>{doneCount}</div>
        </div>
      </div>

      {/* Sections */}
      <div className="cz-card" style={{ padding: 0, overflow: "hidden" }}>

        {/* 1. Meetings */}
        {timeFilter === "hoy" && meetings.length > 0 && (
          <>
            <SectionHeader title="Meetings hoy" count={meetings.length} tone="indigo" />
            {meetings.map((d, i) => (
              <MeetingRow key={d.id || i} d={d} onOpen={() => handleOpenDeal(d)} />
            ))}
          </>
        )}

        {/* 2. Actions for period */}
        {todayActions.length > 0 && (
          <>
            <SectionHeader title={timeFilter === "hoy" ? "Acciones de hoy" : timeFilter === "semana" ? "Acciones esta semana" : timeFilter === "next_week" ? "Acciones próxima semana" : "Acciones del mes"} count={todayActions.length} tone="ink" />
            {todayActions.slice(0, actionsVisible).map(a => (
              <ActionRow key={a.id} a={a} onOpen={() => handleOpenDeal(a)} onToggle={() => handleToggleDone(a.id)} isDone={false} today={today} />
            ))}
            {actionsVisible < todayActions.length && (
              <button onClick={() => setActionsVisible(c => c + TODO_PAGE)} style={{
                width: "100%", padding: "10px", border: "none", background: "var(--card-2)",
                cursor: "pointer", fontSize: 12, fontWeight: 600, color: "var(--indigo)",
                borderBottom: "1px solid var(--line-2)",
              }}>
                Mostrar más ({todayActions.length - actionsVisible} restantes)
              </button>
            )}
          </>
        )}

        {/* 3. Overdue */}
        {overdue.length > 0 && (
          <>
            <SectionHeader title="Atrasadas" count={overdue.length} tone="red" collapsed={!showOverdue} onToggle={() => setShowOverdue(!showOverdue)} />
            {showOverdue && overdue.slice(0, overdueVisible).map(a => (
              <ActionRow key={a.id} a={a} onOpen={() => handleOpenDeal(a)} onToggle={() => handleToggleDone(a.id)} isDone={false} today={today} />
            ))}
            {showOverdue && overdueVisible < overdue.length && (
              <button onClick={() => setOverdueVisible(c => c + TODO_PAGE)} style={{
                width: "100%", padding: "10px", border: "none", background: "var(--card-2)",
                cursor: "pointer", fontSize: 12, fontWeight: 600, color: "var(--indigo)",
                borderBottom: "1px solid var(--line-2)",
              }}>
                Mostrar más ({overdue.length - overdueVisible} restantes)
              </button>
            )}
          </>
        )}

        {/* 4. Done */}
        {doneActions.length > 0 && (
          <>
            <SectionHeader title="Hechas" count={doneActions.length} tone="green" collapsed={!showDone} onToggle={() => setShowDone(!showDone)} />
            {showDone && doneActions.map(a => (
              <ActionRow key={a.id} a={a} onOpen={() => handleOpenDeal(a)} onToggle={() => handleToggleDone(a.id)} isDone={true} today={today} />
            ))}
          </>
        )}

        {/* Empty state */}
        {meetings.length === 0 && todayActions.length === 0 && overdue.length === 0 && doneActions.length === 0 && (
          <div className="cz-empty">Sin acciones pendientes para estos filtros.</div>
        )}
      </div>
    </div>
  );
}
