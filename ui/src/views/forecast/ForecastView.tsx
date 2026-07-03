/* ============================================================
   CLOSZR — FORECAST v3
   7 KPI cards → clickable → deal list with forecast intelligence
   - Editable target for management roles
   - 3-section deal list (this month / next month / pushable)
   ============================================================ */
import { useState, useMemo } from "react";
import { Icon, Chip, fmtMRR } from "../components";
import { useData } from "../../data/store";
import type { ForecastDeal, ClosedDeal, LostDeal } from "../../data/store";
import { hubspotDealUrl, MOMENTUM_DISPLAY, CONFIDENCE_TONE, ADMIN_ROLES } from "../../display";
import { normalize, distinctTeams, distinctOwners } from "../../data/filters";
import { usePermissions } from "../../permissions";
import { supabase } from "../../data/supabase";

function fmtEur(v: number | null | undefined): string {
  if (v == null || v === 0) return "—";
  return "€" + Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

const MOM = MOMENTUM_DISPLAY;
const CONF_TONE = CONFIDENCE_TONE;
const MANAGEMENT_ROLES = new Set(ADMIN_ROLES.filter(r => ["Admin", "Manager", "Director", "TL"].includes(r)));
const CAT_ORDER: Record<string, number> = { "Commit": 0, "Upside": 1, "Pipeline_new": 2, "": 3 };
const CONF_ORDER: Record<string, number> = { "high": 0, "medium": 1, "low": 2 };

type Panel = "hs" | "forecast" | "closed" | "lost";
type SortKey = "category" | "close_date_hs" | "close_date_closzr" | "owner" | "mrr" | "momentum";
type Section = "thisMonth" | "nextMonth" | "pushable";

/* ---- HubSpot icon link ---- */
function HubSpotLink({ hsId, onClick }: { hsId: string; onClick?: (e: React.MouseEvent) => void }) {
  return (
    <a href={hubspotDealUrl(hsId)} target="_blank" rel="noopener noreferrer" title="Abrir en HubSpot"
      onClick={onClick} style={{ display: "inline-flex", color: "var(--ink-4)", flex: "none" }}>
      <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor"><path d="M17.63 13.31a3.3 3.3 0 01-1.63.43 3.37 3.37 0 01-3.37-3.37c0-.6.16-1.17.44-1.66l-2.3-2.3a.99.99 0 01-.15-.17 2.48 2.48 0 01-1.52.53V9.3a1.35 1.35 0 110-2.7V4.06A2.06 2.06 0 007.04 2a2.06 2.06 0 00-2.06 2.06v2.53a2.73 2.73 0 00.88 5.31h.05a2.7 2.7 0 001.79-.68l2.38 2.38a3.34 3.34 0 00-.46 1.69A3.37 3.37 0 0013 18.66a3.3 3.3 0 001.86-.57l2.74 2.74a1.1 1.1 0 001.56-1.56zM13 16.92a1.63 1.63 0 110-3.25 1.63 1.63 0 010 3.25z"/></svg>
    </a>
  );
}

/* ---- Expandable deal row ---- */
function FcRow({ d, open, onToggle, onOpen }: { d: ForecastDeal; open: boolean; onToggle: () => void; onOpen: (row: any, tab?: string) => void }) {
  const isWon = d.hsCategory === "Won";
  const mom = d.momentum ? MOM[d.momentum] : null;

  return (
    <>
      <div className="cz-fctable-r" style={{ cursor: "pointer", gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 90px 90px 90px 80px 24px", ...(isWon ? { background: "var(--green-tint)" } : {}) }} onClick={onToggle}>
        <div className="cz-fct-deal">
          <span className="cz-fct-name" style={{ display: "flex", alignItems: "center", gap: 5, ...(isWon ? { color: "var(--green-ink)" } : {}) }}>
            {d.deal}
            {d.hsId && <HubSpotLink hsId={d.hsId} onClick={e => e.stopPropagation()} />}
          </span>
          <span className="cz-fct-owner">{d.owner}</span>
        </div>
        <div className="num" style={{ fontWeight: 700, ...(isWon ? { color: "var(--green)" } : {}) }}>{fmtMRR(d.mrr)}</div>
        <div><Chip tone={isWon ? "green" : d.hsCategory === "Commit" ? "green" : d.hsCategory === "Upside" ? "amber" : "ink"} style={{ fontSize: 10.5 }}>{d.hsCategory || "—"}</Chip></div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {isWon ? <span style={{ fontSize: 12, color: "var(--green-ink)" }}>Cerrado</span> : <>
            <span style={{ width: 16, textAlign: "center", color: mom ? mom.color : "transparent", fontWeight: 700, fontSize: 13, flex: "none" }}>{mom ? mom.icon : "—"}</span>
            {d.confidence && <Chip tone={CONF_TONE[d.confidence] || "ink"} style={{ fontSize: 10 }}>{d.confidence}</Chip>}
          </>}
        </div>
        <div className="num" style={{ fontSize: 12, color: "var(--ink-2)" }}>{d.closeDate?.slice(0, 10) || "—"}</div>
        <div className="num" style={{ fontSize: 12, color: "var(--indigo)" }}>{isWon ? "—" : d.claudioCloseDate || "—"}</div>
        <div style={{ textAlign: "center" }}>
          <button onClick={e => { e.stopPropagation(); onOpen({ id: d.id }, "hist"); }}
            style={{ fontSize: 11, fontWeight: 600, color: "var(--indigo)", background: "var(--indigo-tint)", border: "none", padding: "4px 10px", borderRadius: "var(--r-pill)", cursor: "pointer", whiteSpace: "nowrap" }}>
            Ver deal
          </button>
        </div>
        <div><Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .18s" }} /></div>
      </div>
      {open && (
        <div style={{ padding: "16px 22px 20px", background: isWon ? "var(--green-tint)" : "var(--card-2)", borderBottom: "1px solid var(--line-2)", display: "flex", flexDirection: "column", gap: 12 }}>
          {isWon && d.forecastReasoning && (
            <div style={{ padding: "12px 16px", background: "var(--green-tint)", borderRadius: "var(--r-sm)" }}>
              <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--green-ink)" }}>Análisis del deal</span>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: "var(--green-ink)" }}>{d.forecastReasoning}</p>
            </div>
          )}
          {!isWon && d.pushable && d.pushAction && (
            <div style={{ padding: "12px 16px", background: "var(--amber-tint)", borderRadius: "var(--r-sm)", fontSize: 13.5, lineHeight: 1.55, color: "var(--amber-ink)" }}>
              <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--amber-ink)" }}>Push action</span>
              {d.pushAction}
            </div>
          )}
          {!isWon && d.forecastReasoning && (
            <div>
              <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Por qué</span>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: "var(--ink-2)" }}>{d.forecastReasoning}</p>
            </div>
          )}
          {!isWon && <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {d.forecastAccelerators && (
              <div style={{ padding: "10px 14px", background: "var(--green-tint)", borderRadius: "var(--r-sm)" }}>
                <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--green-ink)" }}>Aceleradores</span>
                <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                  {d.forecastAccelerators.split(/\n|\d+\.\s+/).filter(Boolean).map((b: string, i: number) => (
                    <li key={i} style={{ display: "flex", gap: 8, fontSize: 12.5, lineHeight: 1.5, color: "var(--green-ink)" }}>
                      <span style={{ color: "var(--green)", flex: "none" }}>•</span>
                      <span>{b.trim()}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {d.forecastRisks && (
              <div style={{ padding: "10px 14px", background: "var(--red-tint)", borderRadius: "var(--r-sm)" }}>
                <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--red-ink)" }}>Riesgos</span>
                <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                  {d.forecastRisks.split(/\n|\d+\.\s+/).filter(Boolean).map((b: string, i: number) => (
                    <li key={i} style={{ display: "flex", gap: 8, fontSize: 12.5, lineHeight: 1.5, color: "var(--red-ink)" }}>
                      <span style={{ color: "var(--red)", flex: "none" }}>•</span>
                      <span>{b.trim()}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>}
          {!isWon && <div style={{ display: "flex", gap: 12, fontSize: 12.5, color: "var(--ink-3)" }}>
            {d.claudioCloseDate && <span>Cierre Closzr: <b className="num">{d.claudioCloseDate}</b></span>}
            {d.closeDate && <span>Cierre HS: <b className="num">{d.closeDate}</b></span>}
          </div>}
          {isWon && <div style={{ fontSize: 12.5, color: "var(--green-ink)" }}>
            {d.closeDate && <span>Cerrado: <b className="num">{d.closeDate}</b></span>}
          </div>}
        </div>
      )}
    </>
  );
}

/* ---- Closed Won row with expand ---- */
function ClosedRow({ d, open, onToggle }: { d: ClosedDeal; open: boolean; onToggle: () => void }) {
  const hookLine = d.strengths?.split("\n")[0]?.replace(/^[-•]\s*/, "") || "";
  const strengthBullets = (d.strengths || "").split("\n").slice(1).map(s => s.replace(/^[-•]\s*/, "").trim()).filter(Boolean);

  return (
    <>
      <div className="cz-fctable-r" style={{ cursor: "pointer", gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 70px minmax(250px,1.5fr) 24px" }} onClick={onToggle}>
        <div className="cz-fct-deal">
          <span className="cz-fct-name">{d.deal}</span>
          <span className="cz-fct-owner">{d.owner}</span>
        </div>
        <div className="num" style={{ fontWeight: 700 }}>{fmtMRR(d.mrr)}</div>
        <div className="num" style={{ fontSize: 12.5, color: "var(--ink-3)" }}>{d.last}</div>
        <div className="num" style={{ fontSize: 12.5, color: "var(--ink-3)" }}>{d.dealAge ? d.dealAge + "d" : "—"}</div>
        <div style={{ fontSize: 12.5, color: "var(--green-ink)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{hookLine || <span style={{ color: "var(--ink-4)" }}>—</span>}</div>
        <div><Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .18s" }} /></div>
      </div>
      {open && (
        <div style={{ padding: "16px 22px 20px", background: "var(--card-2)", borderBottom: "1px solid var(--line-2)", display: "flex", flexDirection: "column", gap: 14 }}>
          {strengthBullets.length > 0 && (
            <div style={{ padding: "12px 16px", background: "var(--green-tint)", borderRadius: "var(--r-sm)" }}>
              <span className="eyebrow" style={{ display: "block", marginBottom: 8, color: "var(--green-ink)" }}>Cómo se ganó</span>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                {strengthBullets.map((b, i) => (
                  <li key={i} style={{ display: "flex", gap: 8, fontSize: 13, lineHeight: 1.55, color: "var(--green-ink)" }}>
                    <span style={{ color: "var(--green)", flex: "none" }}>•</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d.lessons.length > 0 && (
            <div style={{ padding: "12px 16px", background: "var(--indigo-tint)", borderRadius: "var(--r-sm)" }}>
              <span className="eyebrow" style={{ display: "block", marginBottom: 8, color: "var(--indigo-700)" }}>Lecciones del deal</span>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 8 }}>
                {d.lessons.map((l, i) => (
                  <li key={i} style={{ display: "flex", gap: 8, fontSize: 13, lineHeight: 1.55, color: "var(--ink-2)" }}>
                    <span style={{ color: "var(--indigo)", flex: "none", fontWeight: 700 }}>{i + 1}.</span>
                    <span>{l}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div style={{ fontSize: 12.5, color: "var(--ink-3)", display: "flex", gap: 12 }}>
            {d.dealAge && <span>{d.dealAge} días</span>}
            {d.interactions?.total_calls && <span>{d.interactions.total_calls} calls</span>}
            {d.interactions?.total_emails && <span>{d.interactions.total_emails} emails</span>}
            <span>{fmtMRR(d.mrr)} MRR</span>
          </div>
        </div>
      )}
    </>
  );
}

/* ---- Lost deal row ---- */
function LostRow({ d }: { d: LostDeal }) {
  return (
    <div className="cz-fctable-r" style={{ gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 70px 1fr" }}>
      <div className="cz-fct-deal">
        <span className="cz-fct-name" style={{ display: "flex", alignItems: "center", gap: 5 }}>
          {d.deal}
          {d.hsId && <HubSpotLink hsId={d.hsId} onClick={e => e.stopPropagation()} />}
        </span>
        <span className="cz-fct-owner">{d.owner}</span>
      </div>
      <div className="num" style={{ fontWeight: 700 }}>{fmtMRR(d.mrr)}</div>
      <div className="num" style={{ fontSize: 12.5, color: "var(--ink-3)" }}>{d.closeDate?.slice(0, 10) || "—"}</div>
      <div className="num" style={{ fontSize: 12.5, color: "var(--ink-3)" }}>{d.dealAge ? d.dealAge + "d" : "—"}</div>
      <div style={{ fontSize: 12.5, color: "var(--red-ink)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {d.lostReason || <span style={{ color: "var(--ink-4)" }}>Sin motivo registrado</span>}
      </div>
    </div>
  );
}

/* ---- Section header for grouped deal list ---- */
function SectionHeader({ label, count, mrr, tone, active, onClick }: { label: string; count: number; mrr: number; tone: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 10, width: "100%", padding: "10px 18px",
      background: active ? `var(--${tone}-tint)` : "var(--card-3)",
      border: "none", borderBottom: "1px solid var(--line-2)", cursor: "pointer", textAlign: "left",
    }}>
      <span style={{ fontWeight: 700, fontSize: 13, color: active ? `var(--${tone})` : "var(--ink-2)" }}>{label}</span>
      <Chip tone={tone as any} style={{ fontSize: 10 }}>{count} deals</Chip>
      <span className="num" style={{ fontSize: 12.5, fontWeight: 600, color: `var(--${tone})`, marginLeft: "auto" }}>{fmtEur(mrr)}</span>
      <Icon name="chevDown" size={12} style={{ color: "var(--ink-3)", transform: active ? "none" : "rotate(-90deg)", transition: "transform .18s" }} />
    </button>
  );
}

/* ---- Inline editable target ---- */
function EditableTarget({ value, teamFilter, targets, teams, canEdit }: { value: number; teamFilter: string; targets: { team: string; month: string; monthly_target: number }[]; teams: string[]; canEdit: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const cm = new Date().toISOString().slice(0, 7);

  const handleSave = async () => {
    const num = parseInt(draft.replace(/[^\d]/g, ""), 10);
    if (isNaN(num) || num <= 0) { setEditing(false); return; }

    if (teamFilter) {
      await supabase.from("forecast_targets").upsert({ team: teamFilter, month: cm, monthly_target: num }, { onConflict: "team,month" });
    } else {
      const teamTargets = targets.filter(t => t.month === cm);
      if (teamTargets.length === 0 && teams.length > 0) {
        const perTeam = Math.round(num / teams.length);
        for (const team of teams) {
          await supabase.from("forecast_targets").upsert({ team, month: cm, monthly_target: perTeam }, { onConflict: "team,month" });
        }
      } else {
        const ratio = num / (value || 1);
        for (const t of teamTargets) {
          await supabase.from("forecast_targets").upsert({ team: t.team, month: cm, monthly_target: Math.round(t.monthly_target * ratio) }, { onConflict: "team,month" });
        }
      }
    }
    setEditing(false);
    window.location.reload();
  };

  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={handleSave}
        onKeyDown={e => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") setEditing(false); }}
        className="display"
        style={{ width: 140, border: "none", borderBottom: "2px solid var(--indigo)", background: "transparent", fontSize: "inherit", fontWeight: "inherit", padding: 0, outline: "none", textAlign: "center" }}
      />
    );
  }

  return (
    <div
      className="cz-fc-kpi-v display"
      onClick={() => { if (canEdit) { setDraft(String(value)); setEditing(true); } }}
      style={{ cursor: canEdit ? "pointer" : "default" }}
      title={canEdit ? "Click para editar" : undefined}
    >
      {fmtEur(value)}
    </div>
  );
}

/* ============================================================ */
export default function ForecastView({ onOpen }: { onOpen: (row: any, tab?: string) => void }) {
  const D = useData();
  const F = D.forecast;
  const { profile } = usePermissions();
  const [panel, setPanel] = useState<Panel>("forecast");
  const [teamFilter, setTeamFilter] = useState("");
  const [repFilter, setRepFilter] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("mrr");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<Section | null>(null);

  const canEditTarget = profile ? MANAGEMENT_ROLES.has(profile.role) : false;
  const teams = useMemo(() => distinctTeams(F.allDeals), [F.allDeals]);
  const reps = useMemo(() => distinctOwners(F.allDeals, teamFilter || undefined), [F.allDeals, teamFilter]);

  const repNorm = repFilter ? normalize(repFilter) : "";

  const applyFilters = <T extends { team?: string; owner: string; deal: string }>(deals: T[]): T[] => {
    let out = deals;
    if (teamFilter) out = out.filter(d => d.team === teamFilter);
    if (repFilter) out = out.filter(d => {
      const on = normalize(d.owner || "");
      return on === repNorm || on.startsWith(repNorm + " ");
    });
    if (search.trim()) {
      const q = search.toLowerCase();
      out = out.filter(d => d.deal.toLowerCase().includes(q) || (d.owner || "").toLowerCase().includes(q));
    }
    return out;
  };

  const filteredHs = useMemo(() => applyFilters(F.hsDeals), [F.hsDeals, teamFilter, repFilter, search]);
  const filteredCloszr = useMemo(() => applyFilters(F.closzrDeals), [F.closzrDeals, teamFilter, repFilter, search]);
  const filteredNextMonth = useMemo(() => applyFilters(F.nextMonthDeals), [F.nextMonthDeals, teamFilter, repFilter, search]);
  const filteredPushable = useMemo(() => applyFilters(F.pushableDeals), [F.pushableDeals, teamFilter, repFilter, search]);
  const filteredClosed = useMemo(() => applyFilters(F.closedDeals), [F.closedDeals, teamFilter, repFilter, search]);
  const filteredLost = useMemo(() => applyFilters(F.lostDeals), [F.lostDeals, teamFilter, repFilter, search]);

  // KPIs (filtered)
  const cm = new Date().toISOString().slice(0, 7);
  const target = useMemo(() => {
    if (!teamFilter) return F.target;
    return F.targets.filter(t => t.team === teamFilter && t.month === cm).reduce((s, t) => s + (t.monthly_target || 0), 0);
  }, [F.target, F.targets, teamFilter, cm]);
  const hsTotal = Math.round(filteredHs.reduce((s, d) => s + (d.mrr || 0), 0));
  const closzrTotal = Math.round(filteredCloszr.reduce((s, d) => s + (d.mrr || 0), 0));
  const nextMonthTotal = Math.round(filteredNextMonth.reduce((s, d) => s + (d.mrr || 0), 0));
  const pushableTotal = Math.round(filteredPushable.reduce((s, d) => s + (d.mrr || 0), 0));
  const closedTotal = Math.round(filteredClosed.reduce((s, d) => s + (d.mrr || 0), 0));

  const pct = (v: number) => target > 0 ? Math.round(v / target * 100) : 0;
  const toggle = (p: Panel) => { setPanel(p); setExpandedId(null); if (p === "forecast") setActiveSection(null); };
  const toggleSection = (s: Section) => setActiveSection(activeSection === s ? null : s);

  // Sort deals
  const sortDeals = (deals: ForecastDeal[]) => {
    return [...deals].sort((a, b) => {
      if (sort === "category") return (CAT_ORDER[a.hsCategory] ?? 3) - (CAT_ORDER[b.hsCategory] ?? 3) || (b.mrr || 0) - (a.mrr || 0);
      if (sort === "close_date_hs") return (a.closeDate || "z").localeCompare(b.closeDate || "z") || (b.mrr || 0) - (a.mrr || 0);
      if (sort === "close_date_closzr") return (a.claudioCloseDate || "z").localeCompare(b.claudioCloseDate || "z") || (b.mrr || 0) - (a.mrr || 0);
      if (sort === "owner") return (a.owner || "").localeCompare(b.owner || "") || (b.mrr || 0) - (a.mrr || 0);
      if (sort === "momentum") return (CONF_ORDER[a.confidence || ""] ?? 3) - (CONF_ORDER[b.confidence || ""] ?? 3) || (b.mrr || 0) - (a.mrr || 0);
      return (b.mrr || 0) - (a.mrr || 0);
    });
  };

  const sortedHs = useMemo(() => sortDeals(filteredHs), [filteredHs, sort]);
  const sortedCloszr = useMemo(() => sortDeals(filteredCloszr), [filteredCloszr, sort]);
  const sortedNextMonth = useMemo(() => sortDeals(filteredNextMonth), [filteredNextMonth, sort]);
  const sortedPushable = useMemo(() => sortDeals(filteredPushable), [filteredPushable, sort]);

  const fcTableHeader = (
    <div className="cz-fctable-h" style={{ gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 90px 90px 90px 80px 24px" }}>
      <div>Deal</div><div>MRR</div><div>HS</div><div>Estado</div><div>Cierre HS</div><div>Cierre Closzr</div>
      <div /><div />
    </div>
  );

  const renderDealRows = (deals: ForecastDeal[]) =>
    deals.map(d => <FcRow key={d.id} d={d} open={expandedId === d.id} onToggle={() => setExpandedId(expandedId === d.id ? null : d.id || null)} onOpen={onOpen} />);

  return (
    <div className="cz-fc">
      {/* Toolbar */}
      <div className="cz-toolbar" style={{ marginBottom: 4 }}>
        <div className="cz-tb-title"><h2 className="display">Forecast</h2></div>
        <div style={{ flex: 1 }} />
        <select className="cz-native-select" value={teamFilter} onChange={e => { setTeamFilter(e.target.value); setRepFilter(""); }}>
          <option value="">All Teams</option>
          {teams.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className="cz-native-select" value={repFilter} onChange={e => setRepFilter(e.target.value)}>
          <option value="">All PAEs/PBDs</option>
          {reps.map((r: string) => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="cz-search">
          <Icon name="search" size={16} style={{ color: "var(--ink-3)" }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar deals…" />
        </label>
      </div>

      {/* 7 KPI Cards */}
      <div className="cz-fc-kpis" style={{ gridTemplateColumns: "repeat(7, 1fr)" }}>
        {/* 1. Objetivo */}
        <div className="cz-fc-kpi">
          <span className="eyebrow">Objetivo</span>
          <EditableTarget value={target} teamFilter={teamFilter} targets={F.targets} teams={teams} canEdit={canEditTarget} />
        </div>

        {/* 2. Forecast HubSpot */}
        <button className={"cz-fc-kpi clickable" + (panel === "hs" ? " sel amber" : "")} onClick={() => toggle("hs")}>
          <div className="cz-fc-kpi-head"><span className="eyebrow">Forecast HubSpot</span><Chip tone={pct(hsTotal) >= 100 ? "green" : "amber"}>{pct(hsTotal)}%</Chip></div>
          <div className="cz-fc-kpi-v display">{fmtEur(hsTotal)}</div>
          <div className="cz-fc-kpi-foot">{filteredHs.length} deals · <span className="cz-fc-see">{panel === "hs" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>

        {/* 3. Forecast Closzr */}
        <button className={"cz-fc-kpi clickable accent" + (panel === "forecast" ? " sel" : "")} onClick={() => toggle("forecast")}>
          <div className="cz-fc-kpi-head"><span className="eyebrow" style={{ color: "var(--indigo)" }}>Forecast Closzr</span><Chip tone={pct(closzrTotal) >= 50 ? "green" : "amber"}>{pct(closzrTotal)}%</Chip></div>
          <div className="cz-fc-kpi-v display" style={{ color: "var(--indigo)" }}>{fmtEur(closzrTotal)}</div>
          <div className="cz-fc-kpi-foot">{filteredCloszr.length} deals · <span className="cz-fc-see">{panel === "forecast" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>

        {/* 4. Próximo mes */}
        <button className={"cz-fc-kpi clickable" + (panel === "forecast" ? " sel" : "")} onClick={() => { toggle("forecast"); setActiveSection("nextMonth"); }}>
          <div className="cz-fc-kpi-head"><span className="eyebrow">Próximo mes</span></div>
          <div className="cz-fc-kpi-v display">{fmtEur(nextMonthTotal)}</div>
          <div className="cz-fc-kpi-foot">{filteredNextMonth.length} deals · <span className="cz-fc-see">{panel === "forecast" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>

        {/* 5. Pushable */}
        <button className={"cz-fc-kpi clickable" + (panel === "forecast" ? " sel amber" : "")} onClick={() => { toggle("forecast"); setActiveSection("pushable"); }}>
          <div className="cz-fc-kpi-head"><span className="eyebrow">Pushable</span></div>
          <div className="cz-fc-kpi-v display">{fmtEur(pushableTotal)}</div>
          <div className="cz-fc-kpi-foot">{filteredPushable.length} deals · <span className="cz-fc-see">{panel === "forecast" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>

        {/* 6. Closed Won */}
        <button className={"cz-fc-kpi clickable" + (panel === "closed" ? " sel green" : "")} onClick={() => toggle("closed")}>
          <div className="cz-fc-kpi-head"><span className="eyebrow">Cerrado</span><Chip tone={pct(closedTotal) >= 100 ? "green" : "red"}>{pct(closedTotal)}%</Chip></div>
          <div className="cz-fc-kpi-v display" style={{ color: "var(--green)" }}>{fmtEur(closedTotal)}</div>
          <div className="cz-fc-kpi-foot">{filteredClosed.length} deals · <span className="cz-fc-see">{panel === "closed" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>

        {/* 7. Perdidos */}
        <button className={"cz-fc-kpi clickable" + (panel === "lost" ? " sel red" : "")} onClick={() => toggle("lost")}>
          <div className="cz-fc-kpi-head"><span className="eyebrow">Perdidos</span></div>
          <div className="cz-fc-kpi-v display" style={{ color: "var(--red)" }}>{fmtEur(Math.round(filteredLost.reduce((s, d) => s + (d.mrr || 0), 0)))}</div>
          <div className="cz-fc-kpi-foot">{filteredLost.length} deals · <span className="cz-fc-see">{panel === "lost" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>
      </div>

      {/* Deal list */}
      <div className="cz-card cz-fctablecard">
        <div className="cz-fctable-top">
          <div>
            <span className="eyebrow">
              {panel === "hs" && "Forecast HubSpot"}
              {panel === "forecast" && "Forecast Closzr"}
              {panel === "closed" && "Cerrados este mes"}
              {panel === "lost" && "Perdidos este mes"}
            </span>
          </div>
          <label className="cz-search" style={{ minWidth: 180 }}>
            <Icon name="search" size={16} style={{ color: "var(--ink-3)" }} />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar deal…" />
          </label>
          {panel !== "closed" && panel !== "lost" && (
            <div className="cz-fctable-sorters">
              <span className="cz-tb-meta">Ordenar</span>
              {([["mrr", "MRR"], ["category", "HS Cat."], ["close_date_hs", "Cierre HS"], ["close_date_closzr", "Cierre Closzr"], ["momentum", "Confidence"], ["owner", "Owner"]] as const).map(([k, l]) => (
                <button key={k} className={"cz-sortbtn" + (sort === k ? " on" : "")} onClick={() => setSort(k)}>{l}</button>
              ))}
            </div>
          )}
        </div>

        {panel === "lost" ? (
          <div className="cz-fctable">
            <div className="cz-fctable-h" style={{ gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 70px 1fr" }}>
              <div>Deal</div><div>MRR</div><div>Fecha</div><div>Ciclo</div><div>Motivo</div>
            </div>
            {filteredLost.map((d, i) => <LostRow key={d.id || i} d={d} />)}
            {!filteredLost.length && <div className="cz-empty">Sin deals perdidos este mes.</div>}
          </div>
        ) : panel === "closed" ? (
          <div className="cz-fctable">
            <div className="cz-fctable-h" style={{ gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 70px minmax(250px,1.5fr) 24px" }}>
              <div>Deal</div><div>MRR</div><div>Cierre</div><div>Ciclo</div><div>Por qué se ganó</div><div />
            </div>
            {filteredClosed.map((d, i) => (
              <ClosedRow key={d.id || i} d={d} open={expandedId === d.id} onToggle={() => setExpandedId(expandedId === d.id ? null : d.id || null)} />
            ))}
            {!filteredClosed.length && <div className="cz-empty">Sin deals cerrados este mes.</div>}
          </div>
        ) : panel === "hs" ? (
          <div className="cz-fctable">
            {fcTableHeader}
            {renderDealRows(sortedHs)}
            {!sortedHs.length && <div className="cz-empty">Sin deals para estos filtros.</div>}
          </div>
        ) : (
          /* panel === "forecast" — 3 sections: this month / next month / pushable */
          <div className="cz-fctable">
            {fcTableHeader}

            {/* Section: Este mes */}
            <SectionHeader
              label="Este mes" count={filteredCloszr.length} mrr={closzrTotal}
              tone="indigo" active={activeSection !== "nextMonth" && activeSection !== "pushable"}
              onClick={() => toggleSection("thisMonth")}
            />
            {(activeSection === null || activeSection === "thisMonth") && renderDealRows(sortedCloszr)}

            {/* Section: Próximo mes */}
            <SectionHeader
              label="Próximo mes" count={filteredNextMonth.length} mrr={nextMonthTotal}
              tone="blue" active={activeSection !== "thisMonth" && activeSection !== "pushable"}
              onClick={() => toggleSection("nextMonth")}
            />
            {(activeSection === null || activeSection === "nextMonth") && renderDealRows(sortedNextMonth)}

            {/* Section: Pushable */}
            <SectionHeader
              label="Pushable" count={filteredPushable.length} mrr={pushableTotal}
              tone="amber" active={activeSection !== "thisMonth" && activeSection !== "nextMonth"}
              onClick={() => toggleSection("pushable")}
            />
            {(activeSection === null || activeSection === "pushable") && renderDealRows(sortedPushable)}

            {!filteredCloszr.length && !filteredNextMonth.length && !filteredPushable.length && (
              <div className="cz-empty">Sin deals para estos filtros.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
