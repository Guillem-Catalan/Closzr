import { useState, useEffect } from "react";
import { Icon, Chip, StageChip, ProbBadge, Avatar, getInitials, fmtMRR, TONE } from "../components";
import { usePermissions } from "../../permissions";
import { stageAbbr } from "../../display";
import { WEEKS, getWeekType, type Section, type CheckItem } from "./weeks";
import { useOneOnOne, type OODeal, type OOEntry } from "./useOneOnOne";

function fmtDate(d: string | null): string {
  if (!d) return "—";
  const [, m, day] = d.split("-");
  const months = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${parseInt(day)} ${months[parseInt(m)]}`;
}

function fmtMonthLabel(d: string | null): string {
  if (!d) return "—";
  const m = parseInt(d.split("-")[1]);
  const months = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  return months[m] || "—";
}

function dateAlign(repDate: string | null, claudioDate: string | null): "aligned" | "rep_only" | "claudio_only" | "mismatch" {
  const repM = repDate?.slice(0, 7);
  const clM = claudioDate?.slice(0, 7);
  if (!repM && !clM) return "aligned";
  if (repM && clM && repM === clM) return "aligned";
  if (repM && !clM) return "rep_only";
  if (!repM && clM) return "claudio_only";
  return "mismatch";
}

/* ── Deal Card ── */
function DealCard({ deal, section, session, onEntry, onOpen }: {
  deal: OODeal; section: string;
  session: { checks: Record<string, boolean>; entries: OOEntry[] } | null;
  onEntry: (e: Omit<OOEntry, "at">) => void;
  onOpen: (row: any) => void;
}) {
  const [note, setNote] = useState("");
  const align = dateAlign(deal.close_date_hs, deal.estimated_close_date);
  const entries = (session?.entries || []).filter(e => e.deal_id === deal.deal_id && e.section === section);
  const name = deal.company_name || deal.deal_name_full || "—";

  const saveNote = () => {
    if (!note.trim()) return;
    onEntry({ deal_id: deal.deal_id, deal_name: name, section, type: "note", note: note.trim() });
    setNote("");
  };

  return (
    <div className="cz-oo-deal">
      <div className="cz-oo-deal-header">
        <button className="cz-oo-deal-name" onClick={() => onOpen({ id: deal.deal_id })}>
          {name}
        </button>
        <span className="cz-oo-deal-mrr num">{fmtMRR(deal.mrr)}</span>
        <StageChip stage={stageAbbr(deal.stage || "")} />
        {deal.close_probability != null && <ProbBadge value={deal.close_probability} />}
      </div>

      <div className="cz-oo-deal-dates">
        <span className="cz-oo-date-label">Rep:</span>
        <span className="cz-oo-date-val num">{fmtDate(deal.close_date_hs)}</span>
        <span className="cz-oo-date-label">Claudio:</span>
        <span className="cz-oo-date-val num">{fmtDate(deal.estimated_close_date)}</span>
        {align === "aligned" && <Chip tone="green" style={{ fontSize: 10 }}>✓ Alineados</Chip>}
        {align === "mismatch" && (
          <Chip tone="red" style={{ fontSize: 10 }}>
            ⚠ Rep {fmtMonthLabel(deal.close_date_hs)} vs Claudio {fmtMonthLabel(deal.estimated_close_date)}
          </Chip>
        )}
        {align === "rep_only" && <Chip tone="amber" style={{ fontSize: 10 }}>Solo Rep</Chip>}
        {align === "claudio_only" && <Chip tone="amber" style={{ fontSize: 10 }}>Solo Claudio</Chip>}
      </div>

      {deal.deal_assessment && (
        <p className="cz-oo-deal-assess">{deal.deal_assessment}</p>
      )}

      <div className="cz-oo-note-input">
        <input
          type="text" placeholder="Añadir nota sobre este deal..."
          value={note} onChange={e => setNote(e.target.value)}
          onKeyDown={e => e.key === "Enter" && saveNote()}
        />
        {note.trim() && (
          <button className="cz-oo-note-save" onClick={saveNote}>
            <Icon name="check" size={14} />
          </button>
        )}
      </div>

      {entries.length > 0 && (
        <div className="cz-oo-deal-log">
          {entries.map((e, i) => (
            <div key={i} className="cz-oo-log-entry">
              <Icon name={e.type === "note" ? "note" : e.type === "change" ? "calendar" : "flag"} size={13} />
              <span className="cz-oo-log-text">
                {e.type === "change" && <><b>{e.field}</b>: {e.old_val} → {e.new_val}</>}
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

/* ── Check Item ── */
function CheckItemRow({ item, section, checked, deals, session, onToggle, onEntry, onOpen }: {
  item: CheckItem; section: string; checked: boolean;
  deals: OODeal[];
  session: { checks: Record<string, boolean>; entries: OOEntry[] } | null;
  onToggle: () => void;
  onEntry: (e: Omit<OOEntry, "at">) => void;
  onOpen: (row: any) => void;
}) {
  const [open, setOpen] = useState(true);
  const hasDeals = deals.length > 0;

  return (
    <div className="cz-oo-check">
      <div className="cz-oo-check-row">
        <button className={"cz-oo-checkbox" + (checked ? " done" : "")} onClick={onToggle}>
          {checked && <Icon name="check" size={12} stroke={2.5} />}
        </button>
        <span className={"cz-oo-check-text" + (checked ? " done" : "")}>{item.text}</span>
        {hasDeals && (
          <button className="cz-oo-check-count" onClick={() => setOpen(p => !p)}>
            <span className="num">{deals.length} deal{deals.length !== 1 ? "s" : ""}</span>
            <Icon name="chevDown" size={13} style={{ transform: open ? "none" : "rotate(-90deg)", transition: "transform .15s" }} />
          </button>
        )}
        {item.query && deals.length === 0 && (
          <Chip tone="green" style={{ fontSize: 10, marginLeft: "auto" }}>0 deals ✓</Chip>
        )}
      </div>
      {hasDeals && open && (
        <div className="cz-oo-deals-panel">
          {deals.map(d => (
            <DealCard key={d.deal_id} deal={d} section={section} session={session} onEntry={onEntry} onOpen={onOpen} />
          ))}
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
              deals={item.query ? getDealsFor(item.query) : []}
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

/* ── Main View ── */
export default function OneOnOneView({ onOpen }: { onOpen: (row: any, tab?: string) => void }) {
  const { profile } = usePermissions();
  const tlEmail = profile?.email || "";
  const [weekType, setWeekType] = useState(getWeekType);
  const [selectedRep, setSelectedRep] = useState("");
  const week = WEEKS[weekType];

  const { reps, session, loading, getDealsFor, toggleCheck, addEntry } = useOneOnOne(selectedRep, weekType, tlEmail);

  // Auto-select first rep
  useEffect(() => {
    if (!selectedRep && reps.length > 0) setSelectedRep(reps[0]);
  }, [reps, selectedRep]);

  const totalChecks = week.sections.reduce((s, sec) => s + sec.items.length, 0);
  const doneChecks = week.sections.reduce((s, sec) => s + sec.items.filter(i => session?.checks[i.id]).length, 0);
  const pct = totalChecks > 0 ? Math.round(doneChecks / totalChecks * 100) : 0;

  return (
    <div className="cz-oo">
      {/* Toolbar */}
      <div className="cz-toolbar">
        <div className="cz-tb-title">
          <h2 className="display">1:1 Review</h2>
        </div>
        {reps.length > 0 && (
          <label className="cz-rep-select">
            <Avatar initials={getInitials(selectedRep)} size={26} name={selectedRep} />
            <select value={selectedRep} onChange={e => setSelectedRep(e.target.value)}>
              {reps.map(r => <option key={r}>{r}</option>)}
            </select>
            <Icon name="chevDown" size={15} style={{ color: "var(--ink-3)" }} />
          </label>
        )}
        {totalChecks > 0 && (
          <span className="cz-tb-meta num">{doneChecks}/{totalChecks} completados</span>
        )}
      </div>

      {/* Week tabs */}
      <div className="cz-oo-weeks">
        {WEEKS.map(w => (
          <button
            key={w.type}
            className={"cz-oo-week-tab" + (weekType === w.type ? " active" : "") + (w.sections.length === 0 ? " soon" : "")}
            onClick={() => w.sections.length > 0 && setWeekType(w.type)}
          >
            <span className="cz-oo-week-label">{w.label}</span>
            <span className="cz-oo-week-sub">{w.subtitle}</span>
          </button>
        ))}
      </div>

      {/* Progress bar */}
      {totalChecks > 0 && (
        <div className="cz-oo-progress">
          <div className="cz-oo-progress-bar">
            <div style={{ width: pct + "%", background: pct === 100 ? "var(--green)" : "var(--indigo)", transition: "width .3s" }} />
          </div>
          <span className="cz-oo-progress-text num">{pct}%</span>
        </div>
      )}

      {/* Sections */}
      {loading ? (
        <p style={{ color: "var(--ink-3)", padding: 24 }}>Cargando deals...</p>
      ) : week.sections.length === 0 ? (
        <div className="cz-oo-empty">
          <Icon name="clock" size={32} style={{ color: "var(--ink-4)" }} />
          <p>Esta semana aún no está configurada.</p>
        </div>
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
      )}
    </div>
  );
}
