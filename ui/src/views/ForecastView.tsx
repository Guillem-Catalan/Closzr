/* ============================================================
   CLOSZR — FORECAST v2
   5 KPI cards → clickable → deal list with forecast intelligence
   ============================================================ */
import { useState, useMemo } from "react";
import { Icon, Chip, fmtMRR } from "./components";
import { useData } from "../data/store";
import type { ForecastDeal, ClosedDeal, LostDeal } from "../data/store";
import { hubspotDealUrl, MOMENTUM_DISPLAY, CONFIDENCE_TONE } from "../display";
import { distinctTeams, distinctOwners } from "../data/filters";

function fmtEur(v: number | null | undefined): string {
  if (v == null || v === 0) return "—";
  return "€" + Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

const MOM = MOMENTUM_DISPLAY;
const CONF_TONE = CONFIDENCE_TONE;

type Panel = "hs" | "closzr" | "nextmonth" | "pushable" | "closed" | "lost";
type SortKey = "category" | "close_date_hs" | "close_date_closzr" | "owner" | "mrr" | "momentum";

/* ---- Expandable deal row ---- */
function FcRow({ d, open, onToggle }: { d: ForecastDeal; open: boolean; onToggle: () => void }) {
  const mom = d.momentum ? MOM[d.momentum] : null;
  const accelCount = d.forecastAccelerators ? d.forecastAccelerators.split(/\n|\d+\.\s+/).filter(Boolean).length : 0;
  const riskCount = d.forecastRisks ? d.forecastRisks.split(/\n|\d+\.\s+/).filter(Boolean).length : 0;

  return (
    <>
      <div className="cz-fctable-r" style={{ cursor: "pointer", gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 90px 90px 90px 50px 50px 24px" }} onClick={onToggle}>
        <div className="cz-fct-deal">
          <span className="cz-fct-name" style={{ display: "flex", alignItems: "center", gap: 5 }}>
            {d.deal}
            {d.hsId && (
              <a href={hubspotDealUrl(d.hsId!)}
                target="_blank" rel="noopener noreferrer" title="Abrir en HubSpot"
                onClick={e => e.stopPropagation()}
                style={{ display: "inline-flex", color: "var(--ink-4)", flex: "none" }}>
                <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor"><path d="M17.63 13.31a3.3 3.3 0 01-1.63.43 3.37 3.37 0 01-3.37-3.37c0-.6.16-1.17.44-1.66l-2.3-2.3a.99.99 0 01-.15-.17 2.48 2.48 0 01-1.52.53V9.3a1.35 1.35 0 110-2.7V4.06A2.06 2.06 0 007.04 2a2.06 2.06 0 00-2.06 2.06v2.53a2.73 2.73 0 00.88 5.31h.05a2.7 2.7 0 001.79-.68l2.38 2.38a3.34 3.34 0 00-.46 1.69A3.37 3.37 0 0013 18.66a3.3 3.3 0 001.86-.57l2.74 2.74a1.1 1.1 0 001.56-1.56zM13 16.92a1.63 1.63 0 110-3.25 1.63 1.63 0 010 3.25z"/></svg>
              </a>
            )}
          </span>
          <span className="cz-fct-owner">{d.owner}</span>
        </div>
        <div className="num" style={{ fontWeight: 700 }}>{fmtMRR(d.mrr)}</div>
        <div><Chip tone={d.hsCategory === "Commit" ? "green" : d.hsCategory === "Upside" ? "amber" : "ink"} style={{ fontSize: 10.5 }}>{d.hsCategory || "—"}</Chip></div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 16, textAlign: "center", color: mom ? mom.color : "transparent", fontWeight: 700, fontSize: 13, flex: "none" }}>{mom ? mom.icon : "—"}</span>
          {d.confidence && <Chip tone={CONF_TONE[d.confidence] || "ink"} style={{ fontSize: 10 }}>{d.confidence}</Chip>}
        </div>
        <div className="num" style={{ fontSize: 12, color: "var(--ink-2)" }}>{d.closeDate?.slice(0, 10) || "—"}</div>
        <div className="num" style={{ fontSize: 12, color: "var(--indigo)" }}>{d.claudioCloseDate || "—"}</div>
        <div style={{ textAlign: "center" }}>
          {accelCount > 0 && <span style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 12, fontWeight: 700, color: "var(--green-ink)", background: "var(--green-tint)", padding: "2px 7px", borderRadius: "var(--r-pill)" }}>{accelCount}</span>}
        </div>
        <div style={{ textAlign: "center" }}>
          {riskCount > 0 && <span style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 12, fontWeight: 700, color: "var(--red-ink)", background: "var(--red-tint)", padding: "2px 7px", borderRadius: "var(--r-pill)" }}>{riskCount}</span>}
        </div>
        <div><Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .18s" }} /></div>
      </div>
      {open && (
        <div style={{ padding: "16px 22px 20px", background: "var(--card-2)", borderBottom: "1px solid var(--line-2)", display: "flex", flexDirection: "column", gap: 12 }}>
          {d.pushable && d.pushAction && (
            <div style={{ padding: "12px 16px", background: "var(--amber-tint)", borderRadius: "var(--r-sm)", fontSize: 13.5, lineHeight: 1.55, color: "var(--amber-ink)" }}>
              <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--amber-ink)" }}>Push action</span>
              {d.pushAction}
            </div>
          )}
          {d.forecastReasoning && (
            <div>
              <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Por qué</span>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: "var(--ink-2)" }}>{d.forecastReasoning}</p>
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
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
          </div>
          <div style={{ display: "flex", gap: 12, fontSize: 12.5, color: "var(--ink-3)" }}>
            {d.claudioCloseDate && <span>Cierre Closzr: <b className="num">{d.claudioCloseDate}</b></span>}
            {d.closeDate && <span>Cierre HS: <b className="num">{d.closeDate}</b></span>}
          </div>
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
          {/* Cómo se ganó */}
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

          {/* Lecciones del deal */}
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

          {/* Contexto */}
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
          {d.hsId && (
            <a href={hubspotDealUrl(d.hsId!)}
              target="_blank" rel="noopener noreferrer" title="Abrir en HubSpot"
              onClick={e => e.stopPropagation()}
              style={{ display: "inline-flex", color: "var(--ink-4)", flex: "none" }}>
              <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor"><path d="M17.63 13.31a3.3 3.3 0 01-1.63.43 3.37 3.37 0 01-3.37-3.37c0-.6.16-1.17.44-1.66l-2.3-2.3a.99.99 0 01-.15-.17 2.48 2.48 0 01-1.52.53V9.3a1.35 1.35 0 110-2.7V4.06A2.06 2.06 0 007.04 2a2.06 2.06 0 00-2.06 2.06v2.53a2.73 2.73 0 00.88 5.31h.05a2.7 2.7 0 001.79-.68l2.38 2.38a3.34 3.34 0 00-.46 1.69A3.37 3.37 0 0013 18.66a3.3 3.3 0 001.86-.57l2.74 2.74a1.1 1.1 0 001.56-1.56zM13 16.92a1.63 1.63 0 110-3.25 1.63 1.63 0 010 3.25z"/></svg>
            </a>
          )}
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

/* ============================================================ */
export default function ForecastView() {
  const D = useData();
  const F = D.forecast;
  const [panel, setPanel] = useState<Panel>("pushable");
  const [teamFilter, setTeamFilter] = useState("");
  const [repFilter, setRepFilter] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("mrr");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const teams = useMemo(() => distinctTeams(F.allDeals), [F.allDeals]);
  const reps = useMemo(() => distinctOwners(F.allDeals, teamFilter || undefined), [F.allDeals, teamFilter]);

  const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const repNorm = repFilter ? norm(repFilter) : "";

  // Apply filters to a deal list
  const applyFilters = (deals: (ForecastDeal | ClosedDeal)[]) => {
    let out = deals;
    if (teamFilter) out = out.filter(d => d.team === teamFilter);
    if (repFilter) out = out.filter(d => {
      const on = norm(d.owner || "");
      return on === repNorm || on.startsWith(repNorm + " ");
    });
    if (search.trim()) {
      const q = search.toLowerCase();
      out = out.filter(d => d.deal.toLowerCase().includes(q) || (d.owner || "").toLowerCase().includes(q));
    }
    return out;
  };

  // Filtered lists for each panel
  const filteredHs = useMemo(() => applyFilters(F.hsDeals) as ForecastDeal[], [F.hsDeals, teamFilter, repFilter, search]);
  const filteredCloszr = useMemo(() => applyFilters(F.closzrDeals) as ForecastDeal[], [F.closzrDeals, teamFilter, repFilter, search]);
  const filteredNextMonth = useMemo(() => applyFilters(F.nextMonthDeals) as ForecastDeal[], [F.nextMonthDeals, teamFilter, repFilter, search]);
  const filteredPushable = useMemo(() => applyFilters(F.pushableDeals) as ForecastDeal[], [F.pushableDeals, teamFilter, repFilter, search]);
  const filteredClosed = useMemo(() => applyFilters(F.closedDeals), [F.closedDeals, teamFilter, repFilter, search]);
  const filteredLost = useMemo(() => applyFilters(F.lostDeals), [F.lostDeals, teamFilter, repFilter, search]);

  // KPIs (filtered)
  const target = useMemo(() => {
    if (!teamFilter) return F.target;
    return F.targets.filter(t => t.team === teamFilter && t.month === new Date().toISOString().slice(0, 7)).reduce((s, t) => s + (t.monthly_target || 0), 0);
  }, [F.target, F.targets, teamFilter]);
  const hsTotal = filteredHs.filter(d => d.hsCategory === "Commit" || d.hsCategory === "Upside").reduce((s, d) => s + (d.mrr || 0), 0);
  const closzrTotal = filteredCloszr.reduce((s, d) => s + (d.mrr || 0), 0);
  const nextMonthTotal = filteredNextMonth.reduce((s, d) => s + (d.mrr || 0), 0);
  const closedTotal = filteredClosed.reduce((s, d) => s + (d.mrr || 0), 0);

  const pct = (v: number) => target > 0 ? Math.round(v / target * 100) : 0;
  const toggle = (p: Panel) => { setPanel(p); setExpandedId(null); };

  // Sort the active deal list
  const CAT_ORDER: Record<string, number> = { "Commit": 0, "Upside": 1, "Pipeline_new": 2, "": 3 };
  void 0; // momentum order unused — confidence sort below
  const sortDeals = (deals: ForecastDeal[]) => {
    return [...deals].sort((a, b) => {
      if (sort === "category") return (CAT_ORDER[a.hsCategory] ?? 3) - (CAT_ORDER[b.hsCategory] ?? 3) || (b.mrr || 0) - (a.mrr || 0);
      if (sort === "close_date_hs") return (a.closeDate || "z").localeCompare(b.closeDate || "z") || (b.mrr || 0) - (a.mrr || 0);
      if (sort === "close_date_closzr") return (a.claudioCloseDate || "z").localeCompare(b.claudioCloseDate || "z") || (b.mrr || 0) - (a.mrr || 0);
      if (sort === "owner") return (a.owner || "").localeCompare(b.owner || "") || (b.mrr || 0) - (a.mrr || 0);
      if (sort === "momentum") {
        const CONF_ORDER: Record<string, number> = { "high": 0, "medium": 1, "low": 2 };
        return (CONF_ORDER[a.confidence || ""] ?? 3) - (CONF_ORDER[b.confidence || ""] ?? 3) || (b.mrr || 0) - (a.mrr || 0);
      }
      return (b.mrr || 0) - (a.mrr || 0);
    });
  };

  const activeDeals = panel === "hs" ? sortDeals(filteredHs)
    : panel === "closzr" ? sortDeals(filteredCloszr)
    : panel === "nextmonth" ? sortDeals(filteredNextMonth)
    : panel === "pushable" ? sortDeals(filteredPushable)
    : [];

  return (
    <div className="cz-fc">
      {/* Toolbar */}
      <div className="cz-toolbar" style={{ marginBottom: 4 }}>
        <div className="cz-tb-title">
          <h2 className="display">Forecast</h2>
        </div>
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

      {/* 5 KPI Cards */}
      <div className="cz-fc-kpis" style={{ gridTemplateColumns: "repeat(7, 1fr)" }}>
        {/* 1. Objetivo */}
        <div className="cz-fc-kpi">
          <span className="eyebrow">Objetivo</span>
          <div className="cz-fc-kpi-v display">{fmtEur(target)}</div>
        </div>

        {/* 2. Forecast HubSpot */}
        <button className={"cz-fc-kpi clickable" + (panel === "hs" ? " sel amber" : "")} onClick={() => toggle("hs")}>
          <div className="cz-fc-kpi-head"><span className="eyebrow">Forecast HubSpot</span><Chip tone={pct(hsTotal) >= 100 ? "green" : "amber"}>{pct(hsTotal)}%</Chip></div>
          <div className="cz-fc-kpi-v display">{fmtEur(hsTotal)}</div>
          <div className="cz-fc-kpi-foot">{filteredHs.length} deals · <span className="cz-fc-see">{panel === "hs" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>

        {/* 3. Forecast Closzr */}
        <button className={"cz-fc-kpi clickable accent" + (panel === "closzr" ? " sel" : "")} onClick={() => toggle("closzr")}>
          <div className="cz-fc-kpi-head"><span className="eyebrow" style={{ color: "var(--indigo)" }}>Forecast Closzr</span><Chip tone={pct(closzrTotal) >= 50 ? "green" : "amber"}>{pct(closzrTotal)}%</Chip></div>
          <div className="cz-fc-kpi-v display" style={{ color: "var(--indigo)" }}>{fmtEur(closzrTotal)}</div>
          <div className="cz-fc-kpi-foot">{filteredCloszr.length} deals · <span className="cz-fc-see">{panel === "closzr" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>

        {/* 4. Próximo mes */}
        <button className={"cz-fc-kpi clickable" + (panel === "nextmonth" ? " sel" : "")} onClick={() => toggle("nextmonth")}>
          <div className="cz-fc-kpi-head"><span className="eyebrow">Próximo mes</span></div>
          <div className="cz-fc-kpi-v display">{fmtEur(nextMonthTotal)}</div>
          <div className="cz-fc-kpi-foot">{filteredNextMonth.length} deals · <span className="cz-fc-see">{panel === "nextmonth" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>

        {/* 5. Pushable */}
        <button className={"cz-fc-kpi clickable" + (panel === "pushable" ? " sel amber" : "")} onClick={() => toggle("pushable")}>
          <div className="cz-fc-kpi-head"><span className="eyebrow">Pushable</span></div>
          <div className="cz-fc-kpi-v display">{fmtEur(filteredPushable.reduce((s, d) => s + (d.mrr || 0), 0))}</div>
          <div className="cz-fc-kpi-foot">{filteredPushable.length} deals · <span className="cz-fc-see">{panel === "pushable" ? "mostrando ▲" : "ver deals ▼"}</span></div>
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
          <div className="cz-fc-kpi-v display" style={{ color: "var(--red)" }}>{fmtEur(filteredLost.reduce((s, d) => s + (d.mrr || 0), 0))}</div>
          <div className="cz-fc-kpi-foot">{filteredLost.length} deals · <span className="cz-fc-see">{panel === "lost" ? "mostrando ▲" : "ver deals ▼"}</span></div>
        </button>
      </div>

      {/* Deal list */}
      <div className="cz-card cz-fctablecard">
        <div className="cz-fctable-top">
          <div>
            <span className="eyebrow">
              {panel === "hs" && "Forecast HubSpot"}
              {panel === "closzr" && "Forecast Closzr"}
              {panel === "nextmonth" && "Forecast próximo mes"}
              {panel === "pushable" && "Deals pushable"}
              {panel === "closed" && "Cerrados este mes"}
              {panel === "lost" && "Perdidos este mes"}
            </span>
            <span className="cz-fctable-sub num">
              {panel === "closed" ? filteredClosed.length : panel === "lost" ? filteredLost.length : activeDeals.length} deals
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
              <div>Deal</div>
              <div>MRR</div>
              <div>Fecha</div>
              <div>Ciclo</div>
              <div>Motivo</div>
            </div>
            {(filteredLost as LostDeal[]).map((d, i) => (
              <LostRow key={d.id || i} d={d} />
            ))}
            {!filteredLost.length && <div className="cz-empty">Sin deals perdidos este mes.</div>}
          </div>
        ) : panel === "closed" ? (
          <div className="cz-fctable">
            <div className="cz-fctable-h" style={{ gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 70px minmax(250px,1.5fr) 24px" }}>
              <div>Deal</div>
              <div>MRR</div>
              <div>Cierre</div>
              <div>Ciclo</div>
              <div>Por qué se ganó</div>
              <div />
            </div>
            {(filteredClosed as ClosedDeal[]).map((d, i) => (
              <ClosedRow key={d.id || i} d={d} open={expandedId === d.id} onToggle={() => setExpandedId(expandedId === d.id ? null : d.id || null)} />
            ))}
            {!filteredClosed.length && <div className="cz-empty">Sin deals cerrados este mes.</div>}
          </div>
        ) : (
          <div className="cz-fctable">
            <div className="cz-fctable-h" style={{ gridTemplateColumns: "minmax(200px,1.2fr) 80px 90px 90px 90px 90px 50px 50px 24px" }}>
              <div>Deal</div>
              <div>MRR</div>
              <div>HS</div>
              <div>Estado</div>
              <div>Cierre HS</div>
              <div>Cierre Closzr</div>
              <div style={{ textAlign: "center" }}>Acc.</div>
              <div style={{ textAlign: "center" }}>Risk</div>
              <div />
            </div>
            {activeDeals.map(d => (
              <FcRow
                key={d.id}
                d={d}
                open={expandedId === d.id}
                onToggle={() => setExpandedId(expandedId === d.id ? null : d.id || null)}
              />
            ))}
            {!activeDeals.length && <div className="cz-empty">Sin deals para estos filtros.</div>}
          </div>
        )}
      </div>
    </div>
  );
}
