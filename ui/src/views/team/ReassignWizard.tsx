import { useState, useMemo, useCallback } from "react";
import type { OrgPerson, OrgNode } from "./useOrgchart";
import type { ReassignDeal, RepCapacity, ReassignStep } from "./useReassign";
import { getInitials } from "../components";

type Props = {
  step: ReassignStep;
  allRows: OrgPerson[];
  selectedEmail: string;
  selectedFullName: string;
  deals: ReassignDeal[];
  reps: RepCapacity[];
  loadingDeals: boolean;
  loadingReps: boolean;
  saving: boolean;
  error: string;
  results: { deal_id: string; ok: boolean }[];
  someAssigned: boolean;
  onSelectPerson: (email: string, team: string, fullName: string) => void;
  onAssignDeal: (dealId: string, newEmail: string) => void;
  onGoBack: () => void;
  onGoToSummary: () => void;
  onGoToSafetyConfirm: () => void;
  onConfirm: () => void;
  onClose: () => void;
};

function formatMrr(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return String(Math.round(v));
}

function formatMeeting(iso: string | null): string {
  if (!iso) return "Sin meeting";
  const d = new Date(iso);
  const day = d.toLocaleDateString("es-ES", { weekday: "short", day: "numeric", month: "short" });
  const time = d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  return `${day} ${time}`;
}

const STAGE_LABEL: Record<string, string> = { closing: "Closing", evaluating: "Evaluating", demo: "Demo" };
const STAGE_COLOR: Record<string, string> = { closing: "var(--green)", evaluating: "var(--amber)", demo: "var(--blue)" };
const STAGE_ORDER = ["closing", "evaluating", "demo"];

// ── Recommendation scoring (9 criteria, 100 pts total) ──────
type ScoredRep = RepCapacity & { score: number; reasons: string[]; cons: string[] };

function normRange(val: number, min: number, max: number): number {
  const range = max - min;
  return range > 0 ? (val - min) / range : 0;
}

function parseEmployeeBucket(v: string | null): number {
  if (!v) return 0;
  const n = parseInt(v.replace(/[^0-9]/g, ""), 10);
  return isNaN(n) ? 0 : n;
}

function isRecent90d(dateStr: string | null): boolean {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const now = new Date();
  return (now.getTime() - d.getTime()) < 90 * 24 * 60 * 60 * 1000;
}

function scoreReps(reps: RepCapacity[], deal: ReassignDeal): ScoredRep[] {
  if (reps.length === 0) return [];

  const maxDeals = Math.max(...reps.map(r => r.deal_count));
  const minDeals = Math.min(...reps.map(r => r.deal_count));
  const maxMrr = Math.max(...reps.map(r => r.total_mrr));
  const minMrr = Math.min(...reps.map(r => r.total_mrr));
  const dealMrr = deal.mrr || 0;
  const dealIndustry = (deal.atlas_industry || "").toLowerCase();
  const dealSize = parseEmployeeBucket(deal.atlas_employees);
  const dealPipeline = (deal.pipeline_name || "").toLowerCase();

  return reps.map(r => {
    let score = 0;
    const reasons: string[] = [];
    const cons: string[] = [];
    const won = r.won_deals || [];
    const wonCount = won.length;
    const lostCount = r.lost_count || 0;

    // 1. Carga actual Demo+ (30 pts)
    const capPct = 1 - normRange(r.deal_count, minDeals, maxDeals);
    score += 30 * capPct;
    if (r.deal_count === minDeals) reasons.push(`Menor carga (${r.deal_count} deals Demo+)`);
    else if (r.deal_count === maxDeals) cons.push(`Mayor carga (${r.deal_count} deals Demo+)`);
    else reasons.push(`${r.deal_count} deals activos`);

    // 2. MRR gestionado (15 pts)
    const mrrPct = 1 - normRange(r.total_mrr, minMrr, maxMrr);
    score += 15 * mrrPct;
    if (r.total_mrr <= minMrr + (maxMrr - minMrr) * 0.3) reasons.push(`MRR bajo (${formatMrr(r.total_mrr)})`);
    else if (r.total_mrr >= minMrr + (maxMrr - minMrr) * 0.7) cons.push(`MRR alto (${formatMrr(r.total_mrr)})`);

    // 3. Afinidad de stage (15 pts)
    const stageKey = deal.macro_stage as "demo" | "evaluating" | "closing";
    const countKey = stageKey === "demo" ? "demo_count" : stageKey === "evaluating" ? "eval_count" : "closing_count";
    const stageCount = r[countKey];
    const maxStage = Math.max(...reps.map(x => x[countKey]));
    const stagePct = maxStage > 0 ? 1 - stageCount / maxStage : 1;
    score += 15 * stagePct;
    if (stageCount === 0) reasons.push(`Sin deals en ${STAGE_LABEL[stageKey]}`);
    else if (stageCount === maxStage && maxStage > 1) cons.push(`Ya tiene ${stageCount} en ${STAGE_LABEL[stageKey]}`);

    // 4. Mismo sector (10 pts)
    if (dealIndustry && won.length > 0) {
      const sectorWins = won.filter(w => (w.atlas_industry || "").toLowerCase() === dealIndustry).length;
      if (sectorWins > 0) {
        score += 10;
        reasons.push(`${sectorWins} won en ${deal.atlas_industry}`);
      }
    }

    // 5. Tamano empresa similar (5 pts)
    if (dealSize > 0 && won.length > 0) {
      const sizeWins = won.filter(w => {
        const ws = parseEmployeeBucket(w.atlas_employees);
        if (ws === 0) return false;
        const ratio = ws / dealSize;
        return ratio >= 0.3 && ratio <= 3;
      }).length;
      if (sizeWins > 0) {
        score += 5;
        reasons.push(`${sizeWins} won en tamano similar`);
      }
    }

    // 6. MRR similar (5 pts)
    if (dealMrr > 0 && won.length > 0) {
      const mrrWins = won.filter(w => {
        if (!w.mrr) return false;
        const ratio = w.mrr / dealMrr;
        return ratio >= 0.3 && ratio <= 3;
      }).length;
      if (mrrWins > 0) {
        score += 5;
        reasons.push(`${mrrWins} won con MRR similar`);
      }
    }

    // 7. Win rate (10 pts)
    const totalClosed = wonCount + lostCount;
    if (totalClosed >= 3) {
      const winRate = wonCount / totalClosed;
      score += 10 * winRate;
      const pct = Math.round(winRate * 100);
      if (winRate >= 0.4) reasons.push(`Win rate ${pct}%`);
      else if (winRate < 0.2) cons.push(`Win rate bajo (${pct}%)`);
    }

    // 8. Cierres recientes 90d (5 pts)
    const recentWins = won.filter(w => isRecent90d(w.close_date)).length;
    if (recentWins > 0) {
      const maxRecent = Math.max(...reps.map(x => (x.won_deals || []).filter(w => isRecent90d(w.close_date)).length));
      score += 5 * (maxRecent > 0 ? recentWins / maxRecent : 1);
      reasons.push(`${recentWins} cierre${recentWins > 1 ? "s" : ""} reciente${recentWins > 1 ? "s" : ""}`);
    } else if (totalClosed > 0) {
      cons.push("Sin cierres en 90 dias");
    }

    // 9. Mismo pipeline (5 pts)
    if (dealPipeline && won.length > 0) {
      const pipeWins = won.filter(w => (w.pipeline_name || "").toLowerCase() === dealPipeline).length;
      if (pipeWins > 0) {
        score += 5;
        reasons.push(`${pipeWins} won en mismo pipeline`);
      }
    }

    return { ...r, score, reasons, cons };
  }).sort((a, b) => b.score - a.score);
}

// ── Tree builder for person selection ───────────────────────
function buildSelectTree(rows: OrgPerson[]): { label: string; roots: OrgNode[] }[] {
  const map = new Map<string, OrgNode>();
  for (const r of rows) {
    if (!r.is_active) continue;
    map.set(r.email, { ...r, children: [], descendantCount: 0 });
  }

  const roots: OrgNode[] = [];
  for (const node of map.values()) {
    if (node.reports_to && map.has(node.reports_to)) {
      map.get(node.reports_to)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  function count(n: OrgNode): number {
    let c = 0;
    for (const ch of n.children) c += 1 + count(ch);
    n.descendantCount = c;
    return c;
  }
  roots.forEach(count);

  const channelOrder = ["direct_sales", "partners", "xl"];
  const channelLabel: Record<string, string> = { direct_sales: "Direct Sales", partners: "Partners", xl: "XL" };
  const buckets = new Map<string, OrgNode[]>();
  for (const r of roots) {
    const ch = r.channel || "other";
    if (!buckets.has(ch)) buckets.set(ch, []);
    buckets.get(ch)!.push(r);
  }

  return channelOrder
    .filter(ch => buckets.has(ch))
    .map(ch => ({ label: channelLabel[ch] || ch, roots: buckets.get(ch)! }));
}

function matchesSearch(node: OrgNode, q: string): boolean {
  if (node.full_name.toLowerCase().includes(q) || node.email.toLowerCase().includes(q)) return true;
  return node.children.some(ch => matchesSearch(ch, q));
}

// ── Main component ──────────────────────────────────────────
export default function ReassignWizard(props: Props) {
  const {
    step, allRows, selectedEmail, selectedFullName, deals, reps,
    loadingDeals, loadingReps, saving, error, results, someAssigned,
    onSelectPerson, onAssignDeal, onGoBack, onGoToSummary, onGoToSafetyConfirm, onConfirm, onClose,
  } = props;

  const person = allRows.find(r => r.email === selectedEmail);

  const stepTitle: Record<ReassignStep, string> = {
    select_person: "Reasignar deals",
    assign_deals: `Deals de ${person?.full_name || selectedFullName || selectedEmail}`,
    summary: "Resumen de reasignacion",
    safety_confirm: "Confirmar cambios",
    confirm: "Resultado",
  };

  return (
    <div className="cz-overlay" onClick={onClose}>
      <div
        className="cz-edit-dialog cz-edit-dialog--form"
        style={{ maxWidth: step === "assign_deals" || step === "summary" ? 580 : 440 }}
        onClick={e => e.stopPropagation()}
      >
        <div className="cz-edit-dialog__icon cz-edit-dialog__icon--indigo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 10 20 15 15 20" />
            <path d="M4 4v7a4 4 0 004 4h12" />
          </svg>
        </div>
        <h3 className="cz-edit-dialog__title">{stepTitle[step]}</h3>

        {error && <div className="cz-edit-dialog__error">{error}</div>}

        {step === "select_person" && (
          <SelectPersonStep allRows={allRows} onSelect={onSelectPerson} />
        )}

        {step === "assign_deals" && (
          <AssignDealsStep
            deals={deals}
            reps={reps}
            loadingDeals={loadingDeals}
            loadingReps={loadingReps}
            someAssigned={someAssigned}
            onAssign={onAssignDeal}
            onContinue={onGoToSummary}
            onGoBack={onGoBack}
          />
        )}

        {step === "summary" && (
          <SummaryStep
            deals={deals}
            reps={reps}
            sourceName={person?.full_name || selectedFullName}
            onContinue={onGoToSafetyConfirm}
            onGoBack={onGoBack}
          />
        )}

        {step === "safety_confirm" && (
          <SafetyConfirmStep
            deals={deals}
            saving={saving}
            onConfirm={onConfirm}
            onGoBack={onGoBack}
          />
        )}

        {step === "confirm" && (
          <ConfirmStep deals={deals} results={results} onClose={onClose} />
        )}

        {step === "select_person" && (
          <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
            <button className="cz-edit-dialog__btn" onClick={onClose}>Cancelar</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Step 1: Hierarchical person selection ───────────────────
function SelectPersonStep({ allRows, onSelect }: {
  allRows: OrgPerson[];
  onSelect: (email: string, team: string, fullName: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const channelGroups = useMemo(() => buildSelectTree(allRows), [allRows]);

  const q = search.trim().toLowerCase();

  const toggle = useCallback((email: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(email)) next.delete(email); else next.add(email);
      return next;
    });
  }, []);

  return (
    <>
      <p className="cz-edit-dialog__text">
        Selecciona la persona cuyos deals quieres reasignar.
      </p>
      <div className="cz-edit-dialog__fields">
        <input
          className="cz-field__input"
          type="text"
          placeholder="Buscar por nombre o email..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          autoFocus
        />
      </div>
      <div className="cz-ra-tree" style={{ maxHeight: 360, overflowY: "auto", width: "100%" }}>
        {channelGroups.map(g => {
          const visibleRoots = q ? g.roots.filter(r => matchesSearch(r, q)) : g.roots;
          if (visibleRoots.length === 0) return null;
          return (
            <div key={g.label} className="cz-ra-channel">
              <div className="cz-ra-channel__label">{g.label}</div>
              {visibleRoots.map(root => (
                <TreeNode
                  key={root.email}
                  node={root}
                  depth={0}
                  expanded={expanded}
                  onToggle={toggle}
                  onSelect={onSelect}
                  search={q}
                />
              ))}
            </div>
          );
        })}
      </div>
    </>
  );
}

function TreeNode({ node, depth, expanded, onToggle, onSelect, search }: {
  node: OrgNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (email: string) => void;
  onSelect: (email: string, team: string, fullName: string) => void;
  search: string;
}) {
  const hasChildren = node.children.length > 0;
  const isOpen = expanded.has(node.email) || (search.length > 0 && matchesSearch(node, search));
  const selfMatch = !search || node.full_name.toLowerCase().includes(search) || node.email.toLowerCase().includes(search);

  const visibleChildren = search
    ? node.children.filter(ch => matchesSearch(ch, search))
    : node.children;

  return (
    <div className="cz-ra-node">
      <div
        className={`cz-ra-row${selfMatch && search ? " cz-ra-row--match" : ""}`}
        style={{ paddingLeft: 12 + depth * 16 }}
      >
        {hasChildren ? (
          <button
            className="cz-ra-chevron-btn"
            onClick={() => onToggle(node.email)}
          >
            <svg
              className="cz-ra-chevron"
              width="12" height="12" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2.5"
              style={{ transform: isOpen ? "rotate(0)" : "rotate(-90deg)" }}
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
        ) : (
          <span className="cz-ra-dot" />
        )}
        <button
          className="cz-ra-row__select"
          onClick={() => onSelect(node.email, node.team_name, node.full_name)}
        >
          <span className="cz-ra-avatar">{getInitials(node.full_name)}</span>
          <span className="cz-ra-name">{node.full_name}</span>
        </button>
        <span className="cz-ra-role">{node.role}</span>
      </div>
      {isOpen && visibleChildren.length > 0 && (
        <div className="cz-ra-children">
          {visibleChildren.map(ch => (
            <TreeNode
              key={ch.email}
              node={ch}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              onSelect={onSelect}
              search={search}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Step 2: Deals grouped by stage + recommendation ─────────
function AssignDealsStep({ deals, reps, loadingDeals, loadingReps, someAssigned, onAssign, onContinue, onGoBack }: {
  deals: ReassignDeal[];
  reps: RepCapacity[];
  loadingDeals: boolean;
  loadingReps: boolean;
  someAssigned: boolean;
  onAssign: (dealId: string, newEmail: string) => void;
  onContinue: () => void;
  onGoBack: () => void;
}) {
  const [expandedDeal, setExpandedDeal] = useState<string | null>(null);
  const [collapsedStages, setCollapsedStages] = useState<Set<string>>(new Set());

  // Augment rep capacity with deals already assigned in this session
  const augmentedReps = useMemo(() => {
    return reps.map(r => {
      const pending = deals.filter(d => d.assigned_to === r.email);
      if (pending.length === 0) return r;
      return {
        ...r,
        deal_count: r.deal_count + pending.length,
        total_mrr: r.total_mrr + pending.reduce((s, d) => s + (d.mrr || 0), 0),
        demo_count: r.demo_count + pending.filter(d => d.macro_stage === "demo").length,
        eval_count: r.eval_count + pending.filter(d => d.macro_stage === "evaluating").length,
        closing_count: r.closing_count + pending.filter(d => d.macro_stage === "closing").length,
      };
    });
  }, [reps, deals]);

  const toggleStage = useCallback((stage: string) => {
    setCollapsedStages(prev => {
      const next = new Set(prev);
      if (next.has(stage)) next.delete(stage); else next.add(stage);
      return next;
    });
  }, []);

  if (loadingDeals || loadingReps) {
    return <p className="cz-edit-dialog__text">Cargando deals y capacidad del equipo...</p>;
  }

  if (deals.length === 0) {
    return (
      <>
        <p className="cz-edit-dialog__text">Esta persona no tiene deals activos en Demo+.</p>
        <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
          <button className="cz-edit-dialog__btn" onClick={onGoBack}>Volver</button>
        </div>
      </>
    );
  }

  const stageGroups = STAGE_ORDER
    .map(s => ({ stage: s, items: deals.filter(d => d.macro_stage === s) }))
    .filter(g => g.items.length > 0);

  return (
    <div style={{ width: "100%" }}>
      <div className="cz-ra-tree" style={{ maxHeight: 400, overflowY: "auto" }}>
        {stageGroups.map(({ stage, items }) => (
          <div key={stage} className="cz-ra-stage-group">
            <button
              className="cz-ra-stage-header"
              onClick={() => toggleStage(stage)}
            >
              <svg
                className="cz-ra-chevron"
                width="12" height="12" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" strokeWidth="2.5"
                style={{ transform: collapsedStages.has(stage) ? "rotate(-90deg)" : "rotate(0)" }}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
              <span className="cz-ra-stage-pill" style={{ background: STAGE_COLOR[stage] }}>
                {STAGE_LABEL[stage]}
              </span>
              <span className="cz-ra-stage-count">{items.length} deal{items.length > 1 ? "s" : ""}</span>
            </button>
            {!collapsedStages.has(stage) && items.map(deal => (
              <DealRow
                key={deal.deal_id}
                deal={deal}
                reps={augmentedReps}
                isExpanded={expandedDeal === deal.deal_id}
                onToggle={() => setExpandedDeal(prev => prev === deal.deal_id ? null : deal.deal_id)}
                onAssign={onAssign}
              />
            ))}
          </div>
        ))}
      </div>

      <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row" style={{ marginTop: 16 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)", flex: 1 }}>
          {deals.filter(d => d.assigned_to).length}/{deals.length} asignados
        </span>
        <button className="cz-edit-dialog__btn" onClick={onGoBack}>Volver</button>
        <button
          className="cz-edit-dialog__btn cz-edit-dialog__btn--primary"
          disabled={!someAssigned}
          onClick={onContinue}
        >
          Continuar
        </button>
      </div>
    </div>
  );
}

function DealRow({ deal, reps, isExpanded, onToggle, onAssign }: {
  deal: ReassignDeal;
  reps: RepCapacity[];
  isExpanded: boolean;
  onToggle: () => void;
  onAssign: (dealId: string, newEmail: string) => void;
}) {
  const scored = useMemo(() => scoreReps(reps, deal), [reps, deal]);

  return (
    <div className={`cz-ra-deal${isExpanded ? " cz-ra-deal--open" : ""}${deal.assigned_to ? " cz-ra-deal--assigned" : ""}`}>
      <button className="cz-ra-deal__row" onClick={onToggle}>
        <svg
          className="cz-ra-chevron"
          width="10" height="10" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth="2.5"
          style={{ transform: isExpanded ? "rotate(0)" : "rotate(-90deg)" }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
        <strong className="cz-ra-deal__company">{deal.company_name}</strong>
        <span className="cz-ra-deal__mrr">{formatMrr(deal.mrr || 0)}</span>
        {deal.macro_stage === "demo" && (
          <span className="cz-ra-deal__meeting">{formatMeeting(deal.next_meeting)}</span>
        )}
        {deal.assigned_to && (
          <span className="cz-ra-deal__assigned-badge">
            {reps.find(r => r.email === deal.assigned_to)?.full_name || deal.assigned_to}
          </span>
        )}
      </button>

      {isExpanded && (
        <div className="cz-ra-recs">
          {scored.map((rep, i) => (
            <button
              key={rep.email}
              className={`cz-ra-rec${deal.assigned_to === rep.email ? " cz-ra-rec--selected" : ""}${i === 0 ? " cz-ra-rec--top" : ""}`}
              onClick={() => onAssign(deal.deal_id, rep.email)}
            >
              <div className="cz-ra-rec__header">
                <span className="cz-ra-rec__avatar">{getInitials(rep.full_name)}</span>
                <span className="cz-ra-rec__name">{rep.full_name}</span>
                {i === 0 && <span className="cz-ra-rec__badge">Recomendado</span>}
                {deal.assigned_to === rep.email && <span className="cz-ra-rec__badge cz-ra-rec__badge--assigned">Asignado</span>}
                <span className="cz-ra-rec__score">{Math.round(rep.score)}pts</span>
              </div>
              <div className="cz-ra-rec__details">
                {rep.reasons.map((r, j) => (
                  <span key={j} className="cz-ra-rec__pro">{r}</span>
                ))}
                {rep.cons.map((c, j) => (
                  <span key={j} className="cz-ra-rec__con">{c}</span>
                ))}
              </div>
            </button>
          ))}
          {scored.length === 0 && (
            <p style={{ color: "var(--ink-3)", fontSize: 12, padding: 8 }}>No hay reps disponibles en el equipo.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Step 3: Summary ─────────────────────────────────────────
function SummaryStep({ deals, reps, sourceName, onContinue, onGoBack }: {
  deals: ReassignDeal[];
  reps: RepCapacity[];
  sourceName: string;
  onContinue: () => void;
  onGoBack: () => void;
}) {
  const assigned = deals.filter(d => d.assigned_to);

  // Group by receiving rep
  const byRep = new Map<string, ReassignDeal[]>();
  for (const d of assigned) {
    const key = d.assigned_to!;
    if (!byRep.has(key)) byRep.set(key, []);
    byRep.get(key)!.push(d);
  }

  const remaining = deals.length - assigned.length;
  const totalMrrTransferred = assigned.reduce((s, d) => s + (d.mrr || 0), 0);

  return (
    <div style={{ width: "100%" }}>
      <p className="cz-edit-dialog__text" style={{ textAlign: "left" }}>
        Se reasignaran <strong>{assigned.length} deal{assigned.length > 1 ? "s" : ""}</strong> de <strong>{sourceName}</strong>:
      </p>

      <div className="cz-ra-tree" style={{ maxHeight: 300, overflowY: "auto" }}>
        {[...byRep.entries()].map(([email, repDeals]) => {
          const rep = reps.find(r => r.email === email);
          const repName = rep?.full_name || email;
          const repMrr = repDeals.reduce((s, d) => s + (d.mrr || 0), 0);

          return (
            <div key={email} className="cz-ra-summary-group">
              <div className="cz-ra-summary-rep">
                <span className="cz-ra-avatar">{getInitials(repName)}</span>
                <span className="cz-ra-name">{repName}</span>
                <span className="cz-ra-summary-badge">
                  {repDeals.length} deal{repDeals.length > 1 ? "s" : ""} ({formatMrr(repMrr)} MRR)
                </span>
              </div>
              {repDeals.map(d => (
                <div key={d.deal_id} className="cz-ra-summary-deal">
                  <span className="cz-ra-stage-pill" style={{ background: STAGE_COLOR[d.macro_stage], fontSize: 10, padding: "1px 6px" }}>
                    {STAGE_LABEL[d.macro_stage]}
                  </span>
                  <span style={{ flex: 1, fontSize: 13 }}>{d.company_name}</span>
                  <span style={{ fontSize: 12, color: "var(--ink-3)" }}>{formatMrr(d.mrr || 0)}</span>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      <div className="cz-ra-summary-stats">
        <div className="cz-ra-summary-stat">
          <span className="cz-ra-summary-stat__label">MRR total transferido</span>
          <span className="cz-ra-summary-stat__value">{formatMrr(totalMrrTransferred)}</span>
        </div>
        {remaining > 0 && (
          <div className="cz-ra-summary-stat">
            <span className="cz-ra-summary-stat__label">Deals sin reasignar</span>
            <span className="cz-ra-summary-stat__value">{remaining}</span>
          </div>
        )}
      </div>

      <div className="cz-ra-hs-warning">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span>
          Los cambios se aplicaran en el backend y en HubSpot. Los deals apareceran en el pipeline del nuevo owner en 1-2 minutos.
        </span>
      </div>

      <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row" style={{ marginTop: 16 }}>
        <button className="cz-edit-dialog__btn" onClick={onGoBack}>Volver</button>
        <button
          className="cz-edit-dialog__btn cz-edit-dialog__btn--primary"
          onClick={onContinue}
        >
          Confirmar cambios
        </button>
      </div>
    </div>
  );
}

// ── Step 4: Safety confirmation ─────────────────────────────
function SafetyConfirmStep({ deals, saving, onConfirm, onGoBack }: {
  deals: ReassignDeal[];
  saving: boolean;
  onConfirm: () => void;
  onGoBack: () => void;
}) {
  const count = deals.filter(d => d.assigned_to).length;

  return (
    <>
      <div className="cz-ra-safety-icon">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--amber)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </div>
      <p className="cz-edit-dialog__text">
        Vas a reasignar <strong>{count} deal{count > 1 ? "s" : ""}</strong>. Esta accion cambiara el owner en el backend y en HubSpot.
      </p>
      <p className="cz-edit-dialog__text" style={{ color: "var(--ink-3)", fontSize: 12, marginTop: 0 }}>
        Este cambio no se puede deshacer automaticamente. Si necesitas revertirlo tendras que reasignar cada deal manualmente.
      </p>

      <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row" style={{ marginTop: 16 }}>
        <button className="cz-edit-dialog__btn" onClick={onGoBack}>Volver</button>
        <button
          className="cz-edit-dialog__btn cz-edit-dialog__btn--warn"
          disabled={saving}
          onClick={onConfirm}
        >
          {saving ? "Aplicando cambios..." : "Si, reasignar"}
        </button>
      </div>
    </>
  );
}

// ── Step 5: Results ─────────────────────────────────────────
function ConfirmStep({ deals, results, onClose }: {
  deals: ReassignDeal[];
  results: { deal_id: string; ok: boolean }[];
  onClose: () => void;
}) {
  const ok = results.filter(r => r.ok).length;
  const fail = results.filter(r => !r.ok).length;

  return (
    <>
      <div className="cz-ra-safety-icon">
        {fail === 0 ? (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        ) : (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--amber)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        )}
      </div>
      <p className="cz-edit-dialog__text">
        {fail === 0
          ? `${ok} deal${ok > 1 ? "s" : ""} reasignado${ok > 1 ? "s" : ""} correctamente.`
          : `${ok} reasignado${ok > 1 ? "s" : ""}, ${fail} con error.`}
      </p>
      {fail > 0 && (
        <div style={{ width: "100%" }}>
          {results.filter(r => !r.ok).map(r => {
            const deal = deals.find(d => d.deal_id === r.deal_id);
            return (
              <p key={r.deal_id} style={{ color: "var(--red-ink)", fontSize: 13, margin: "4px 0" }}>
                {deal?.company_name || r.deal_id}
              </p>
            );
          })}
        </div>
      )}
      <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
        <button className="cz-edit-dialog__btn cz-edit-dialog__btn--primary" onClick={onClose}>Cerrar</button>
      </div>
    </>
  );
}
