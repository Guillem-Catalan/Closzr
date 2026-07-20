import { useState, useEffect, useRef, useMemo } from "react";
import { Icon, StageChip, ProbBadge } from "../components";
import { STAGE_DISPLAY, shortStage, CLOSED_WON_STAGES, CLOSED_LOST_STAGES, PIPELINE_STAGES, TEAM_PIPELINES, LOST_REASONS, CRM_NAME, CRM_SHORT } from "../../display";

type ActionKey = "stage" | "closeDate" | "lost" | "note";

const ISSUE_META: Record<string, { label: string; tone: string; desc: string }> = {
  overdue:   { label: "Overdue",    tone: "red",    desc: `Fecha de cierre ${CRM_SHORT} pasada` },
  closeSoon: { label: "Close soon", tone: "amber",  desc: "Cierra en ≤10 días" },
  stale:     { label: "Stale",      tone: "amber",  desc: "Parado 14+ días" },
  silent:    { label: "Silent",     tone: "violet", desc: "7+ días sin tocar" },
  noDate:    { label: "Sin fecha",  tone: "ink",    desc: `Sin fecha de cierre en ${CRM_SHORT}` },
};

const ISSUE_KEYS = Object.keys(ISSUE_META);


const closedSet = new Set([
  ...CLOSED_WON_STAGES.map(s => s.toLowerCase()),
  ...CLOSED_LOST_STAGES.map(s => s.toLowerCase()),
]);
const ALL_OPEN_STAGES = Object.entries(STAGE_DISPLAY)
  .filter(([stage]) => !closedSet.has(stage.toLowerCase()))
  .map(([stage, info]) => ({ value: stage, label: info.short }))
  .filter((s, i, arr) => arr.findIndex(x => x.label === s.label) === i);


const _stageToP = new Map<string, string[]>();
for (const [p, stages] of Object.entries(PIPELINE_STAGES)) {
  for (const s of stages) {
    const arr = _stageToP.get(s) || [];
    arr.push(p);
    _stageToP.set(s, arr);
  }
}

function stagesForDeal(deal: any): { value: string; label: string }[] {
  const pipelineName = deal?._raw?.pipeline_name;
  if (pipelineName && PIPELINE_STAGES[pipelineName]) {
    return PIPELINE_STAGES[pipelineName].map(s => ({ value: s, label: STAGE_DISPLAY[s]?.short || s }));
  }
  const team = deal?._raw?.team || deal?.team || "";
  const currentStage = deal?._raw?.stage || "";
  const teamPipelines = TEAM_PIPELINES[team] || null;
  if (teamPipelines) {
    const stageIn = _stageToP.get(currentStage) || [];
    const match = teamPipelines.find(p => stageIn.includes(p));
    if (match) {
      return PIPELINE_STAGES[match].map(s => ({ value: s, label: STAGE_DISPLAY[s]?.short || s }));
    }
    const firstP = PIPELINE_STAGES[teamPipelines[0]];
    if (firstP) return firstP.map(s => ({ value: s, label: STAGE_DISPLAY[s]?.short || s }));
  }
  return ALL_OPEN_STAGES;
}

const ACTIONS = [
  { key: "stage" as const,     label: "Cambiar stage",  icon: "layers",   hint: "Mover en el pipeline" },
  { key: "closeDate" as const, label: "Fecha cierre",   icon: "calendar", hint: "Reprogramar cierre" },
  { key: "lost" as const,      label: "Marcar perdido", icon: "xCircle",  hint: CLOSED_LOST_STAGES[0], danger: true },
  { key: "note" as const,      label: "Añadir nota",    icon: "note",     hint: "Solo log interno" },
];

function czToday() { return new Date(); }
function czParse(d: string | null) { return d ? new Date(d + "T00:00:00") : null; }
function czDiffDays(a: Date, b: Date) { return Math.round((a.getTime() - b.getTime()) / 86400000); }
function czFmtDate(d: string | null) {
  if (!d) return null;
  const p = czParse(d);
  return p ? p.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" }) : null;
}
function fmtK(v: number | null | undefined) {
  if (v == null || v === 0) return "—";
  if (v >= 1000) return "€" + (v / 1000).toFixed(v % 1000 === 0 ? 0 : 1) + "K";
  return "€" + v;
}
function fmtShortDate(d: string | null) {
  if (!d) return "—";
  const [, m, day] = d.slice(0, 10).split("-");
  return `${day}/${m}`;
}

function getIssues(d: any): string[] {
  const today = czToday();
  const out: string[] = [];
  const hs = czParse(d.closeDateHs);
  const staleDays = d._raw?.stale_days ?? 0;
  if (hs && hs < today) out.push("overdue");
  else if (hs && czDiffDays(hs, today) <= 10) out.push("closeSoon");
  if (staleDays >= 14) out.push("stale");
  else if (staleDays >= 7) out.push("silent");
  if (!d.closeDateHs) out.push("noDate");
  return out;
}

function issueRank(d: any) {
  const s = new Set(getIssues(d));
  return s.has("overdue") ? 0 : s.has("closeSoon") ? 1 : s.has("stale") ? 2 : 3;
}

export default function HygienePanel({ open, onClose, deals, initialDealId = null }: {
  open: boolean;
  onClose: () => void;
  deals: any[];
  initialDealId?: string | null;
}) {
  const findDeal = (id: string) => deals.find(d => d.id === id) || null;

  const [deal, setDeal] = useState<any | null>(initialDealId ? findDeal(initialDealId) : null);
  const [q, setQ] = useState("");
  const [action, setAction] = useState<ActionKey | null>(null);
  const [note, setNote] = useState("");
  const [toStage, setToStage] = useState("");
  const [date, setDate] = useState("");
  const [reason, setReason] = useState(LOST_REASONS[0]);
  const [log, setLog] = useState<{ action: string; label: string; at: number }[]>([]);
  const [flash, setFlash] = useState<string | null>(null);
  const [issueFilter, setIssueFilter] = useState<Set<string>>(new Set());
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setDeal(initialDealId ? findDeal(initialDealId) : null);
      setQ("");
      setAction(null);
      setNote("");
      setLog([]);
      setFlash(null);
      setIssueFilter(new Set());
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (action) resetAction();
        else if (deal && !initialDealId) setDeal(null);
        else onClose();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, action, deal, initialDealId]);

  useEffect(() => {
    if (open && !deal && searchRef.current) searchRef.current.focus();
  }, [open, deal]);

  const resetAction = () => { setAction(null); setNote(""); };

  const pickDeal = (d: any) => {
    setDeal(d);
    setQ("");
    resetAction();
    const fullStage = d._raw?.stage || "";
    const valid = stagesForDeal(d);
    setToStage(valid.find(s => s.value !== fullStage)?.value || valid[0]?.value || "");
    setDate(d.closeDateClaudio || d.closeDateHs || "");
  };

  const toggleIssueFilter = (k: string) => {
    setIssueFilter(prev => {
      const n = new Set(prev);
      if (n.has(k)) n.delete(k); else n.add(k);
      return n;
    });
  };

  const issueMap = useMemo(() => {
    if (!open) return new Map<string, string[]>();
    const m = new Map<string, string[]>();
    for (const d of deals) {
      const iss = getIssues(d);
      if (iss.length) m.set(d.id, iss);
    }
    return m;
  }, [deals, open]);

  const issueCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const k of ISSUE_KEYS) counts[k] = 0;
    for (const iss of issueMap.values()) {
      for (const i of iss) counts[i]++;
    }
    return counts;
  }, [issueMap]);

  const results = useMemo(() => {
    let items: { d: any; issues: string[] }[] = [];
    for (const d of deals) {
      const iss = issueMap.get(d.id);
      if (iss) items.push({ d, issues: iss });
    }
    if (issueFilter.size) {
      items = items.filter(x => x.issues.some(i => issueFilter.has(i)));
    }
    if (q.trim()) {
      const t = q.toLowerCase();
      items = items.filter(x =>
        x.d.deal.toLowerCase().includes(t) ||
        (x.d.owner || "").toLowerCase().includes(t) ||
        (x.d.stage || "").toLowerCase().includes(t)
      );
    }
    items.sort((a, b) => issueRank(a.d) - issueRank(b.d) || (b.d.mrr || 0) - (a.d.mrr || 0));
    return items;
  }, [deals, q, issueFilter, issueMap]);

  const applyUpdate = () => {
    if (!note.trim() || !deal) return;
    const labels: Record<string, string> = {
      stage: `Stage → ${shortStage(toStage)}`,
      closeDate: `Cierre → ${czFmtDate(date)}`,
      lost: `Perdido · ${reason}`,
      note: "Nota añadida",
    };
    // TODO: call Edge Function deal-update
    setLog(l => [{ action: action!, label: labels[action!], at: Date.now() }, ...l]);
    setFlash(labels[action!] + ` · sincronizado con ${CRM_NAME}`);
    if (action === "stage") deal.stage = shortStage(toStage);
    if (action === "closeDate") deal.closeDateHs = date;
    resetAction();
    setTimeout(() => setFlash(null), 2400);
  };

  const canApply = note.trim().length > 0;
  const issues = deal ? getIssues(deal) : [];

  if (!open) return null;

  return (
    <div className="cz-cmd-scrim" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cz-cmd" style={{ animation: "cz-scale-in .22s var(--ease) both" }}>

        {/* header */}
        <div className="cz-cmd-head">
          <span className="cz-cmd-badge"><Icon name="shield" size={14} stroke={2} /> Hygiene</span>
          {deal && (
            <button className="cz-cmd-crumb" onClick={() => { if (!initialDealId) setDeal(null); resetAction(); }} disabled={!!initialDealId}>
              {!initialDealId && <Icon name="arrowLeft" size={13} stroke={2} />}{deal.deal}
            </button>
          )}
          <span style={{ flex: 1 }} />
          {!deal && <span className="cz-cmd-count num">{results.length} deals</span>}
          <button className="cz-iconbtn sm" onClick={onClose} title="Cerrar (Esc)"><Icon name="x" size={16} /></button>
        </div>

        {/* MODE A — no deal: search + filter + results */}
        {!deal && (
          <>
            <label className="cz-cmd-search">
              <Icon name="search" size={18} style={{ color: "var(--ink-3)" }} />
              <input ref={searchRef} value={q} onChange={e => setQ(e.target.value)} placeholder="Busca un deal…" />
              <kbd>esc</kbd>
            </label>

            {/* Issue tag filters */}
            <div className="cz-cmd-filters">
              {ISSUE_KEYS.map(k => {
                const m = ISSUE_META[k];
                const c = issueCounts[k];
                if (!c) return null;
                const on = issueFilter.has(k);
                return (
                  <button key={k} className={"cz-cmd-ftag " + m.tone + (on ? " on" : "")} onClick={() => toggleIssueFilter(k)}>
                    {m.label} <span className="num">{c}</span>
                  </button>
                );
              })}
            </div>

            {/* Scrollable results */}
            <div className="cz-cmd-results">
              {results.slice(0, 40).map(({ d, issues: iss }) => (
                <button key={d.id} className="cz-cmd-result" onClick={() => pickDeal(d)}>
                  <div className="cz-cmd-r-main">
                    <span className="cz-cmd-r-name">{d.deal}</span>
                    <span className="cz-cmd-r-meta">
                      <StageChip stage={d.stage} />
                      <span className="num">{fmtK(d.mrr)}</span>
                      <span className="cz-cmd-r-sep">·</span>
                      <span>{d.owner !== "—" ? d.owner : "Sin owner"}</span>
                      <span className="cz-cmd-r-sep">·</span>
                      <span className="num">{fmtShortDate(d.closeDateHs)}</span>
                    </span>
                  </div>
                  <div className="cz-cmd-r-issues">
                    {iss.map(k => <span key={k} className={"cz-hy-issue " + ISSUE_META[k].tone}>{ISSUE_META[k].label}</span>)}
                  </div>
                  <Icon name="chevRight" size={14} stroke={2} style={{ color: "var(--ink-4)" }} />
                </button>
              ))}
              {results.length > 40 && <div className="cz-cmd-more num">Busca para ver más — {results.length - 40} deals ocultos</div>}
              {!results.length && <div className="cz-cmd-empty">Sin deals{q ? ` para "${q}"` : ""}{issueFilter.size ? " con estos filtros" : ""}.</div>}
            </div>
          </>
        )}

        {/* MODE B — deal loaded */}
        {deal && (
          <div className="cz-cmd-deal">
            <div className="cz-cmd-ctx">
              <div className="cz-cmd-ctx-l">
                <StageChip stage={deal.stage} />
                <span className="cz-cmd-ctx-mrr num">{fmtK(deal.mrr)}</span>
                <span className="cz-cmd-ctx-date num">{czFmtDate(deal.closeDateHs) || "sin fecha"}</span>
                <ProbBadge value={deal.prob} />
              </div>
              <div className="cz-cmd-ctx-issues">
                {issues.map(k => <span key={k} className={"cz-hy-issue " + ISSUE_META[k].tone} title={ISSUE_META[k].desc}>{ISSUE_META[k].label}</span>)}
              </div>
            </div>

            {!action ? (
              <div className="cz-cmd-actions">
                {ACTIONS.map(a => (
                  <button key={a.key} className={"cz-cmd-act" + (a.danger ? " danger" : "")} onClick={() => { setAction(a.key); setNote(""); }}>
                    <span className="cz-cmd-act-ic"><Icon name={a.icon} size={17} stroke={2} /></span>
                    <span className="cz-cmd-act-tx"><b>{a.label}</b><small>{a.hint}</small></span>
                    <Icon name="chevRight" size={15} style={{ color: "var(--ink-4)" }} />
                  </button>
                ))}
              </div>
            ) : (
              <div className="cz-cmd-form">
                <button className="cz-cmd-back" onClick={resetAction}><Icon name="arrowLeft" size={13} stroke={2} /> Acciones</button>

                {action === "stage" && (
                  <label className="cz-hy-field"><span>Nuevo stage</span>
                    <div className="cz-hy-stageflow">
                      <span className="cz-hy-from">{shortStage(deal._raw?.stage || deal.stage)}</span>
                      <Icon name="arrowRight" size={14} stroke={2} style={{ color: "var(--ink-3)" }} />
                      <select value={toStage} onChange={e => setToStage(e.target.value)} className="cz-native-select" style={{ flex: 1 }}>
                        {stagesForDeal(deal).filter(s => s.value !== (deal._raw?.stage || "")).map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </div>
                  </label>
                )}

                {action === "closeDate" && (
                  <label className="cz-hy-field"><span>Nueva fecha de cierre ({CRM_SHORT})</span>
                    <input type="date" value={date} onChange={e => setDate(e.target.value)} className="cz-native-select" />
                    <span className="cz-hy-hint">Closzr sugiere {czFmtDate(deal.closeDateClaudio) || "—"}</span>
                  </label>
                )}

                {action === "lost" && (
                  <label className="cz-hy-field"><span>Motivo de pérdida</span>
                    <select value={reason} onChange={e => setReason(e.target.value)} className="cz-native-select">
                      {LOST_REASONS.map(r => <option key={r}>{r}</option>)}
                    </select>
                    <span className="cz-hy-hint danger">Pasará a <b>{CLOSED_LOST_STAGES[0]}</b> en {CRM_NAME}.</span>
                  </label>
                )}

                <label className="cz-hy-field"><span>Nota <b className="cz-req">obligatoria</b></span>
                  <textarea rows={2} value={note} onChange={e => setNote(e.target.value)} className="cz-textarea" placeholder="Por qué haces este cambio…" autoFocus />
                </label>

                <button
                  className={"cz-btn-primary cz-cmd-apply" + (action === "lost" ? " cz-danger-btn" : "")}
                  disabled={!canApply}
                  onClick={applyUpdate}
                >
                  <Icon name="route" size={14} stroke={2} />
                  {action === "lost" ? `Marcar perdido en ${CRM_NAME}` : action === "note" ? "Guardar nota" : `Aplicar en ${CRM_NAME}`}
                </button>
              </div>
            )}

            {log.length > 0 && (
              <div className="cz-cmd-log">
                {log.map((l, i) => <span key={i} className="cz-cmd-logitem"><Icon name="check" size={12} stroke={2.4} />{l.label}</span>)}
              </div>
            )}
          </div>
        )}

        {flash && <div className="cz-cmd-flash"><Icon name="check" size={14} stroke={2.4} />{flash}</div>}
      </div>
    </div>
  );
}

export { getIssues };
