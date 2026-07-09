import { useState, useEffect, useMemo, Fragment } from "react";
import { Icon, Chip, StageChip, Avatar, getInitials, fmtMRR, TONE } from "../components";
import { usePermissions } from "../../permissions";
import { stageAbbr } from "../../display";
import { WEEKS, getWeekType, getMondayOfWeek, currentYearMonth, PROBLEM_LABELS, type Section, type CheckItem } from "./weeks";
import { useOneOnOne, type OODeal, type OOEntry, type OOSession } from "./useOneOnOne";

function fmtDate(d: string | null): string {
  if (!d) return "—";
  const [, m, day] = d.split("-");
  const months = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${parseInt(day)} ${months[parseInt(m)]}`;
}

function fmtDateFull(d: string | null): string {
  if (!d) return "Sin fecha";
  const [y, m, day] = d.split("-");
  const months = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
  return `${parseInt(day)} ${months[parseInt(m)]} ${y}`;
}

function fmtMonthLabel(d: string | null): string {
  if (!d) return "—";
  const m = parseInt(d.split("-")[1]);
  const months = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  return months[m] || "—";
}

function daysOverdue(d: string | null): number | null {
  if (!d) return null;
  const diff = Math.floor((Date.now() - new Date(d).getTime()) / 86400000);
  return diff > 0 ? diff : null;
}

function dateAlign(repDate: string | null, claudioDate: string | null): { status: "aligned" | "rep_only" | "claudio_only" | "mismatch"; label: string } {
  const repM = repDate?.slice(0, 7);
  const clM = claudioDate?.slice(0, 7);
  if (!repM && !clM) return { status: "aligned", label: "Sin fechas" };
  if (repM && clM && repM === clM) return { status: "aligned", label: "✓ Alineados" };
  if (repM && !clM) return { status: "rep_only", label: "Solo Rep" };
  if (!repM && clM) return { status: "claudio_only", label: "Solo Closzr" };
  return { status: "mismatch", label: `⚠ Rep ${fmtMonthLabel(repDate)} vs Closzr ${fmtMonthLabel(claudioDate)}` };
}

type ActionMode = "keep" | "change" | "action" | "lost" | "push";
type ActionDef = { mode: ActionMode; label: string; icon: string; tone: string };

function actionsFor(query: string | undefined): ActionDef[] {
  switch (query) {
    case "past_close":
      return [
        { mode: "change", label: "Cambiar fecha", icon: "calendar", tone: "change" },
        { mode: "lost", label: "Mover a Lost", icon: "x", tone: "lost" },
      ];
    case "same_stage_30d":
    case "stale_7d":
    case "m0_at_risk":
      return [
        { mode: "action", label: "Definir acción", icon: "flag", tone: "keep" },
        { mode: "lost", label: "Mover a Lost", icon: "x", tone: "lost" },
      ];
    case "demo_6w":
      return [
        { mode: "action", label: "Acelerar o limpiar", icon: "flag", tone: "keep" },
        { mode: "lost", label: "Mover a Lost", icon: "x", tone: "lost" },
      ];
    case "past_close_or_stale":
      return [
        { mode: "change", label: "Cambiar fecha", icon: "calendar", tone: "change" },
        { mode: "action", label: "Definir acción", icon: "flag", tone: "keep" },
        { mode: "lost", label: "Mover a Lost", icon: "x", tone: "lost" },
      ];
    case "m1_m2_pusheable":
      return [
        { mode: "push", label: "Adelantar a M+1", icon: "check", tone: "keep" },
        { mode: "keep", label: "Mantener fecha", icon: "check", tone: "keep" },
      ];
    case "m0_closing_soon":
      return [
        { mode: "keep", label: "Confirmar cierre", icon: "check", tone: "keep" },
        { mode: "change", label: "Cambiar fecha", icon: "calendar", tone: "change" },
        { mode: "lost", label: "Mover a Lost", icon: "x", tone: "lost" },
      ];
    default:
      return [
        { mode: "keep", label: "Mantener fecha", icon: "check", tone: "keep" },
        { mode: "change", label: "Cambiar fecha", icon: "calendar", tone: "change" },
        { mode: "lost", label: "Mover a Lost", icon: "x", tone: "lost" },
      ];
  }
}

function contextTag(query: string | undefined, deal: OODeal): { text: string; warn: boolean } | null {
  switch (query) {
    case "past_close": {
      const over = daysOverdue(deal.close_date_hs);
      return over ? { text: `⚠ ${over} días de retraso`, warn: true } : null;
    }
    case "same_stage_30d":
      return { text: `⏱ ${deal.stale_days ?? "—"} días en ${deal.stage || "—"}`, warn: (deal.stale_days || 0) >= 30 };
    case "stale_7d":
      return { text: `⏱ ${deal.stale_days ?? "—"} días sin actividad`, warn: (deal.stale_days || 0) >= 7 };
    case "demo_6w":
      return { text: `⏱ ${deal.deal_age_days ?? "—"} días desde demo`, warn: (deal.deal_age_days || 0) > 42 };
    case "past_close_or_stale": {
      const over = daysOverdue(deal.close_date_hs);
      if (over) return { text: `⚠ ${over} días de retraso`, warn: true };
      if ((deal.stale_days || 0) >= 7) return { text: `⏱ ${deal.stale_days} días sin actividad`, warn: true };
      return null;
    }
    case "m0_at_risk":
      return { text: `⏱ ${deal.stale_days ?? "—"} días sin actividad`, warn: true };
    case "m0_closing_soon": {
      const left = deal.close_date_hs ? Math.max(0, Math.floor((new Date(deal.close_date_hs).getTime() - Date.now()) / 86400000)) : null;
      return left != null ? { text: `⏱ ${left} días para cierre`, warn: left <= 3 } : null;
    }
    case "m1_m2_pusheable":
      return deal.deal_momentum ? { text: `↗ ${deal.deal_momentum}${deal.close_probability != null ? ` · ${deal.close_probability}%` : ""}`, warn: false } : null;
    default:
      return null;
  }
}

function confirmPlaceholder(mode: ActionMode): string {
  switch (mode) {
    case "keep": return "¿Por qué se mantiene esta fecha?";
    case "change": return "¿Por qué se cambia la fecha?";
    case "action": return "¿Qué acción concreta se hará y para cuándo?";
    case "lost": return "¿Por qué se cierra este deal?";
    case "push": return "¿Qué haría falta para cerrar un mes antes?";
  }
}

/* ── Action Panel (expanded below a table row) ── */
function DealActionPanel({ deal, section, session, onEntry, query }: {
  deal: OODeal; section: string;
  session: { checks: Record<string, boolean>; entries: OOEntry[] } | null;
  onEntry: (e: Omit<OOEntry, "at">) => void;
  query?: string;
}) {
  const [mode, setMode] = useState<ActionMode | null>(null);
  const [reason, setReason] = useState("");
  const [newDate, setNewDate] = useState("");
  const entries = (session?.entries || []).filter(e => e.deal_id === deal.deal_id && e.section === section);
  const name = deal.company_name || deal.deal_name_full || "—";
  const summary = deal.deal_summary || deal.deal_assessment || null;
  const actions = actionsFor(query);
  const tag = contextTag(query, deal);

  const confirmAction = () => {
    if (!reason.trim()) return;
    if (mode === "keep") {
      onEntry({ deal_id: deal.deal_id, deal_name: name, section, type: "note",
        note: `Fecha mantenida (${fmtDateFull(deal.close_date_hs)}): ${reason.trim()}` });
    } else if (mode === "change" && newDate) {
      onEntry({ deal_id: deal.deal_id, deal_name: name, section, type: "change",
        field: "close_date", old_val: fmtDateFull(deal.close_date_hs), new_val: fmtDateFull(newDate),
        note: reason.trim() });
    } else if (mode === "action" || mode === "push") {
      onEntry({ deal_id: deal.deal_id, deal_name: name, section, type: "commitment",
        note: reason.trim() });
    } else if (mode === "lost") {
      onEntry({ deal_id: deal.deal_id, deal_name: name, section, type: "change",
        field: "stage", old_val: deal.stage || "—", new_val: "Closed Lost",
        note: reason.trim() });
    }
    setMode(null);
    setReason("");
    setNewDate("");
  };

  const resetMode = () => { setMode(null); setReason(""); setNewDate(""); };

  const align = dateAlign(deal.close_date_hs, deal.estimated_close_date);
  const mainActions = actions.filter(a => a.mode !== "lost");
  const lostAction = actions.find(a => a.mode === "lost");

  return (
    <div className="cz-oo-action" onClick={e => e.stopPropagation()}>
      {/* Summary — always */}
      {summary && <p className="cz-oo-action-summary">{summary}</p>}

      {/* Dates line + alignment chip + context tag */}
      <div className="cz-oo-dates-line">
        <span className="cz-oo-dates-pair">
          <span className="cz-oo-dates-label">Account:</span>
          <span className="cz-oo-dates-val num">{fmtDate(deal.close_date_hs)}</span>
        </span>
        <span className="cz-oo-dates-pair">
          <span className="cz-oo-dates-label">Closzr:</span>
          <span className="cz-oo-dates-val num">{fmtDate(deal.estimated_close_date)}</span>
        </span>
        <Chip tone={align.status === "aligned" ? "green" : align.status === "mismatch" ? "red" : "amber"} style={{ fontSize: 11 }}>
          {align.label}
        </Chip>
        {tag && (
          <span className={"cz-oo-ctx-tag" + (tag.warn ? " warn" : "")}>{tag.text}</span>
        )}
      </div>

      {/* Actions — big buttons + Lost as link */}
      {!mode && (
        <div className="cz-oo-action-buttons">
          {mainActions.map(a => (
            <button key={a.mode} className={`cz-oo-btn-big ${a.tone}`} onClick={() => setMode(a.mode)}>
              <Icon name={a.icon} size={15} />{a.label}
            </button>
          ))}
          {lostAction && (
            <button className="cz-oo-lost-link" onClick={() => setMode("lost")}>
              <Icon name="x" size={13} />Mover a Lost
            </button>
          )}
        </div>
      )}

      {/* Confirm flow — horizontal textarea + button */}
      {mode && (
        <div className={"cz-oo-confirm-flow" + (mode === "lost" ? " lost" : "")}>
          <div className="cz-oo-confirm-header">
            <span>{actions.find(a => a.mode === mode)?.label} — <b>{name}</b></span>
            <button className="cz-oo-confirm-cancel" onClick={resetMode}><Icon name="x" size={14} /></button>
          </div>
          {mode === "change" && (
            <div className="cz-oo-date-pick">
              <label className="cz-oo-date-pick-label">Nueva fecha</label>
              <input type="date" className="cz-oo-date-pick-input" value={newDate} onChange={e => setNewDate(e.target.value)} />
            </div>
          )}
          <div className="cz-oo-confirm-inline">
            <input
              type="text"
              className="cz-oo-confirm-input"
              placeholder={confirmPlaceholder(mode)}
              value={reason} onChange={e => setReason(e.target.value)}
              onKeyDown={e => e.key === "Enter" && confirmAction()}
              autoFocus
            />
            <button
              className={"cz-oo-confirm-btn" + (mode === "lost" ? " lost" : "")}
              disabled={!reason.trim() || (mode === "change" && !newDate)}
              onClick={confirmAction}
            >
              Confirmar<Icon name="check" size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Entry log */}
      {entries.length > 0 && (
        <div className="cz-oo-deal-log">
          {entries.map((e, i) => (
            <div key={i} className="cz-oo-log-entry">
              <Icon name={e.type === "note" ? "note" : e.type === "change" ? "calendar" : "flag"} size={12} />
              <span className="cz-oo-log-text">
                {e.type === "change" && <><b>{e.field}</b>: {e.old_val} → {e.new_val}{e.note ? ` — ${e.note}` : ""}</>}
                {e.type === "note" && e.note}
                {e.type === "commitment" && <><b>Compromiso:</b> {e.note}</>}
              </span>
              <span className="cz-oo-log-time num">{new Date(e.at).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Deal Data Table ── */
function DealTable({ deals, section, session, onEntry, onOpen, query, dealProblems }: {
  deals: OODeal[]; section: string;
  session: { checks: Record<string, boolean>; entries: OOEntry[] } | null;
  onEntry: (e: Omit<OOEntry, "at">) => void;
  onOpen: (row: any) => void;
  query?: string;
  dealProblems?: Map<string, { queries: string[]; labels: string[] }>;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const showProblems = dealProblems && dealProblems.size > 0;

  return (
    <div className="cz-oo-tw">
      <table className="cz-oo-t">
        <thead>
          <tr>
            <th>Deal</th>
            {showProblems && <th>Problema</th>}
            <th className="cz-oo-th-r">MRR</th>
            <th className="cz-oo-th-r">Stage</th>
            <th className="cz-oo-th-r">Último contacto</th>
            <th className="cz-oo-th-r">Cierre Account</th>
            <th className="cz-oo-th-r">Cierre Closzr</th>
            <th style={{ width: 1 }}></th>
          </tr>
        </thead>
        <tbody>
          {deals.map(deal => {
            const expanded = expandedId === deal.deal_id;
            const name = deal.company_name || deal.deal_name_full || "—";
            return (
              <Fragment key={deal.deal_id}>
                <tr
                  className={expanded ? "on" : ""}
                  onClick={() => setExpandedId(expanded ? null : deal.deal_id)}
                >
                  <td className="cz-oo-td-co">{name}</td>
                  {showProblems && (
                    <td>
                      <div className="cz-oo-problem-tags">
                        {(dealProblems.get(deal.deal_id)?.labels || []).map(l => (
                          <span key={l} className="cz-oo-problem-tag">{l}</span>
                        ))}
                      </div>
                    </td>
                  )}
                  <td className="num cz-oo-td-r" style={{ fontWeight: 700 }}>{fmtMRR(deal.mrr)}</td>
                  <td className="cz-oo-td-r"><StageChip stage={stageAbbr(deal.stage || "")} /></td>
                  <td className="cz-oo-td-r cz-oo-td-lc">{deal.last_contact_label || "—"}</td>
                  <td className="num cz-oo-td-r">{fmtDate(deal.close_date_hs)}</td>
                  <td className="num cz-oo-td-r">{fmtDate(deal.estimated_close_date)}</td>
                  <td className="cz-oo-td-r">
                    <button
                      className="cz-oo-ver"
                      onClick={e => { e.stopPropagation(); onOpen({ id: deal.deal_id }); }}
                    >
                      Ver deal<Icon name="external" size={12} />
                    </button>
                  </td>
                </tr>
                {expanded && (
                  <tr className="cz-oo-xrow">
                    <td colSpan={showProblems ? 8 : 7}>
                      <DealActionPanel deal={deal} section={section} session={session} onEntry={onEntry} query={query} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── Check Item ── */
function CheckItemRow({ item, section, checked, getDealsFor, session, onToggle, onEntry, onOpen }: {
  item: CheckItem; section: string; checked: boolean;
  getDealsFor: (q: string) => OODeal[];
  session: { checks: Record<string, boolean>; entries: OOEntry[] } | null;
  onToggle: () => void;
  onEntry: (e: Omit<OOEntry, "at">) => void;
  onOpen: (row: any) => void;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");

  const { deals, dealProblems } = useMemo(() => {
    if (item.queries) {
      const seen = new Set<string>();
      const merged: OODeal[] = [];
      const problems = new Map<string, { queries: string[]; labels: string[] }>();
      for (const q of item.queries) {
        for (const d of getDealsFor(q)) {
          if (!seen.has(d.deal_id)) {
            seen.add(d.deal_id);
            merged.push(d);
          }
          const entry = problems.get(d.deal_id) || { queries: [], labels: [] };
          if (!entry.queries.includes(q)) {
            entry.queries.push(q);
            const lbl = PROBLEM_LABELS[q];
            if (lbl) entry.labels.push(lbl);
          }
          problems.set(d.deal_id, entry);
        }
      }
      return { deals: merged, dealProblems: problems };
    }
    if (item.query) return { deals: getDealsFor(item.query), dealProblems: undefined };
    return { deals: [] as OODeal[], dealProblems: undefined };
  }, [item.query, item.queries, getDealsFor]);

  const hasDeals = deals.length > 0;
  const itemNotes = (session?.entries || []).filter(e => e.deal_id === `item:${item.id}` && e.section === section);

  const addNote = () => {
    if (!note.trim()) return;
    onEntry({ deal_id: `item:${item.id}`, deal_name: item.text, section, type: "note", note: note.trim() });
    setNote("");
  };

  return (
    <div className="cz-oo-check">
      <div className={"cz-oo-check-row clickable"} onClick={() => setOpen(p => !p)}>
        <button className={"cz-oo-checkbox" + (checked ? " done" : "")} onClick={e => { e.stopPropagation(); onToggle(); }}>
          {checked && <Icon name="check" size={10} stroke={3} />}
        </button>
        <span className={"cz-oo-check-text" + (checked ? " done" : "")}>{item.text}</span>
        {hasDeals && (
          <span className="cz-oo-check-count">
            <span className="num">{deals.length}</span>
            <span>deal{deals.length !== 1 ? "s" : ""}</span>
          </span>
        )}
        {(item.query || item.queries) && deals.length === 0 && (
          <Chip tone="green" style={{ fontSize: 10, marginLeft: "auto" }}>0 deals</Chip>
        )}
        {itemNotes.length > 0 && !hasDeals && !item.query && !item.queries && (
          <span className="cz-oo-check-count">
            <span className="num">{itemNotes.length}</span>
            <span>nota{itemNotes.length !== 1 ? "s" : ""}</span>
          </span>
        )}
        <Icon name="chevDown" size={12} style={{ color: "var(--ink-4)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .15s", marginLeft: hasDeals || ((item.query || item.queries) && deals.length === 0) || (itemNotes.length > 0 && !hasDeals && !item.query && !item.queries) ? 0 : "auto" }} />
      </div>
      {open && (
        <div className="cz-oo-deals-panel">
          {item.guide && (
            <div className="cz-oo-guide">
              {item.guide.map((g, i) => (
                <div key={i} className="cz-oo-guide-item">
                  <span className="cz-oo-guide-bullet" />
                  <span>{g}</span>
                </div>
              ))}
            </div>
          )}
          {hasDeals && (
            <DealTable deals={deals} section={section} session={session} onEntry={onEntry} onOpen={onOpen} query={item.query} dealProblems={dealProblems} />
          )}
          <div className="cz-oo-item-note">
            <div className="cz-oo-confirm-inline">
              <input
                type="text"
                className="cz-oo-confirm-input"
                placeholder="Añadir nota sobre este punto..."
                value={note} onChange={e => setNote(e.target.value)}
                onKeyDown={e => e.key === "Enter" && addNote()}
              />
              <button className="cz-oo-confirm-btn" disabled={!note.trim()} onClick={addNote}>
                Guardar<Icon name="check" size={14} />
              </button>
            </div>
            {itemNotes.length > 0 && (
              <div className="cz-oo-deal-log">
                {itemNotes.map((e, i) => (
                  <div key={i} className="cz-oo-log-entry">
                    <Icon name="note" size={12} />
                    <span className="cz-oo-log-text">{e.note}</span>
                    <span className="cz-oo-log-time num">{new Date(e.at).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Section ── */
function SectionBlock({ section, session, getDealsFor, onToggle, onEntry, onOpen }: {
  section: Section;
  session: { checks: Record<string, boolean>; entries: OOEntry[] } | null;
  getDealsFor: (q: string) => OODeal[];
  onToggle: (id: string) => void;
  onEntry: (e: Omit<OOEntry, "at">) => void;
  onOpen: (row: any) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const checks = session?.checks || {};
  const done = section.items.filter(i => checks[i.id]).length;
  const total = section.items.length;
  const t = TONE[section.tone] || TONE.ink;

  return (
    <div className="cz-oo-section">
      <button className="cz-oo-section-header" onClick={() => setCollapsed(p => !p)}>
        <span className="cz-oo-section-num" style={{ background: t.bg, color: t.fg }}>{section.num}</span>
        <span className="cz-oo-section-title">{section.title}</span>
        <span className="cz-oo-section-time">{section.time} min</span>
        <span className="cz-oo-section-progress" style={{
          background: done === total && total > 0 ? "var(--green-tint)" : t.bg,
          color: done === total && total > 0 ? "var(--green-ink)" : t.fg,
        }}>
          {done}/{total}
        </span>
        <Icon name="chevDown" size={15} style={{ color: "var(--ink-4)", transform: collapsed ? "rotate(-90deg)" : "none", transition: "transform .15s" }} />
      </button>
      {!collapsed && (
        <div className="cz-oo-section-body">
          {section.items.map(item => (
            <CheckItemRow
              key={item.id} item={item} section={section.num}
              checked={!!checks[item.id]}
              getDealsFor={getDealsFor}
              session={session}
              onToggle={() => onToggle(item.id)}
              onEntry={onEntry} onOpen={onOpen}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Month helpers ── */
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

/* ── Histórico Panel ── */
function HistoricoPanel({ history, repName }: { history: OOSession[]; repName: string }) {
  const byMonth = useMemo(() => {
    const map = new Map<string, OOSession[]>();
    for (const s of history) {
      const ym = s.session_date.slice(0, 7);
      if (!map.has(ym)) map.set(ym, []);
      map.get(ym)!.push(s);
    }
    for (const sessions of map.values()) sessions.sort((a, b) => a.week_type - b.week_type);
    return map;
  }, [history]);

  if (history.length === 0) {
    return (
      <div className="cz-oo-hist">
        <p style={{ color: "var(--ink-3)", fontSize: 13, padding: "20px 0" }}>No hay sesiones registradas para {repName}.</p>
      </div>
    );
  }

  return (
    <div className="cz-oo-hist">
      {[...byMonth.entries()].map(([ym, sessions]) => (
        <div key={ym} className="cz-oo-hist-month">
          <span className="cz-oo-hist-label">{fmtYM(ym)}</span>
          <div className="cz-oo-hist-weeks">
            {sessions.map(s => {
              const w = WEEKS[s.week_type];
              const total = w ? w.sections.reduce((a, sec) => a + sec.items.length, 0) : 0;
              const done = w ? w.sections.reduce((a, sec) => a + sec.items.filter(i => s.checks[i.id]).length, 0) : 0;
              const nEntries = (s.entries || []).length;
              return (
                <div key={s.id || s.week_type} className="cz-oo-hist-card">
                  <span className="cz-oo-hist-wk">W{s.week_type}</span>
                  <span className="cz-oo-hist-wt">{w?.subtitle || "—"}</span>
                  <span className="cz-oo-hist-stat num">{done}/{total}</span>
                  {nEntries > 0 && <span className="cz-oo-hist-entries">{nEntries} nota{nEntries !== 1 ? "s" : ""}</span>}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Main View ── */
export default function OneOnOneView({ onOpen }: { onOpen: (row: any, tab?: string) => void }) {
  const { profile } = usePermissions();
  const tlEmail = profile?.email || "";
  const [month, setMonth] = useState(currentYearMonth);
  const [weekType, setWeekType] = useState(getWeekType);
  const [selectedRep, setSelectedRep] = useState("");
  const [showHist, setShowHist] = useState(false);
  const week = WEEKS[weekType];
  const monday = getMondayOfWeek(month, weekType);
  const mOpts = useMemo(monthOptions, []);
  const isCurrent = month === currentYearMonth();

  const { reps, session, history, loading, getDealsFor, toggleCheck, addEntry } = useOneOnOne(selectedRep, weekType, tlEmail, monday);

  useEffect(() => {
    if (!selectedRep && reps.length > 0) setSelectedRep(reps[0]);
  }, [reps, selectedRep]);

  useEffect(() => {
    if (isCurrent) setWeekType(getWeekType());
    else setWeekType(0);
  }, [month, isCurrent]);

  const totalChecks = week.sections.reduce((s, sec) => s + sec.items.length, 0);
  const doneChecks = week.sections.reduce((s, sec) => s + sec.items.filter(i => session?.checks[i.id]).length, 0);
  const pct = totalChecks > 0 ? Math.round(doneChecks / totalChecks * 100) : 0;

  return (
    <div className="cz-oo">
      {/* Header */}
      <div className="cz-oo-head">
        <div className="cz-oo-head-top">
          <div>
            <h2>1:1 Review</h2>
            <p className="cz-oo-head-sub">Guía paso a paso para tus sesiones semanales</p>
          </div>
          <button className={"cz-oo-hist-btn" + (showHist ? " on" : "")} onClick={() => setShowHist(p => !p)}>
            <Icon name="book" size={15} />Histórico
          </button>
        </div>

        <div className="cz-oo-controls">
          {reps.length > 0 && (
            <label className="cz-oo-sel">
              <Avatar initials={getInitials(selectedRep)} size={24} name={selectedRep} />
              <select value={selectedRep} onChange={e => setSelectedRep(e.target.value)}>
                {reps.map(r => <option key={r}>{r}</option>)}
              </select>
              <Icon name="chevDown" size={14} style={{ color: "var(--ink-4)" }} />
            </label>
          )}
          <label className="cz-oo-sel">
            <Icon name="calendar" size={15} style={{ color: "var(--ink-3)" }} />
            <select value={month} onChange={e => setMonth(e.target.value)}>
              {mOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <Icon name="chevDown" size={14} style={{ color: "var(--ink-4)" }} />
          </label>
        </div>
      </div>

      {/* Week cards */}
      <div className="cz-oo-weeks">
        {WEEKS.map(w => {
          const wTotal = w.sections.reduce((s, sec) => s + sec.items.length, 0);
          const wDone = weekType === w.type ? doneChecks : 0;
          return (
            <button
              key={w.type}
              className={"cz-oo-wcard" + (weekType === w.type ? " on" : "") + (wTotal === 0 ? " soon" : "")}
              onClick={() => wTotal > 0 && setWeekType(w.type)}
            >
              <span className="cz-oo-wcard-num">W{w.type}</span>
              <span className="cz-oo-wcard-title">{w.subtitle}</span>
              <span className="cz-oo-wcard-dur">{w.duration} min</span>
              {weekType === w.type && wTotal > 0 && (
                <span className="cz-oo-wcard-count num">{wDone}/{wTotal}</span>
              )}
            </button>
          );
        })}
        {totalChecks > 0 && (
          <div className="cz-oo-progress-inline">
            <div className="cz-oo-progress-bar">
              <div style={{ width: pct + "%", background: pct === 100 ? "var(--green)" : "var(--indigo)" }} />
            </div>
            <span className="cz-oo-progress-text num">{pct}%</span>
          </div>
        )}
      </div>

      {/* Histórico */}
      {showHist && <HistoricoPanel history={history} repName={selectedRep} />}

      {/* Sections */}
      {!showHist && (
        loading ? (
          <p style={{ color: "var(--ink-3)", padding: 24 }}>Cargando deals...</p>
        ) : (
          <div className="cz-oo-sections">
            {week.sections.map(sec => (
              <SectionBlock
                key={sec.num} section={sec} session={session}
                getDealsFor={getDealsFor}
                onToggle={toggleCheck} onEntry={addEntry}
                onOpen={(row) => onOpen(row, "hist")}
              />
            ))}
          </div>
        )
      )}
    </div>
  );
}
