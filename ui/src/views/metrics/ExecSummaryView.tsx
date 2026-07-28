import { useState, useMemo, useEffect } from "react";
import { useData } from "../../data/store";
import type { BenchmarkDeal, ForecastDeal } from "../../data/store";
import { Chip, fmtMRR, Icon } from "../components";
import { ACTIVE_TEAMS, ownerDisplayName } from "../../display";
import { expandTeam } from "../../data/filters";
import { supabase } from "../../data/supabase";

type SortCol = "team" | "mrrWon" | "demos" | "logos" | "pipeline" | "winRate" | "avgCycle";
type SortDir = "asc" | "desc";
type PartnerSortCol = "partner" | "mrrWon" | "deals" | "pipeline";

function monthKey(d: Date): string {
  return d.toISOString().slice(0, 7);
}

function monthLabel(mk: string): string {
  const [y, m] = mk.split("-");
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${names[parseInt(m, 10) - 1]} ${y}`;
}

function getMonthOptions(): { value: string; label: string }[] {
  const opts: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const mk = monthKey(d);
    opts.push({ value: mk, label: monthLabel(mk) });
  }
  return opts;
}

const CARD: React.CSSProperties = {
  background: "var(--card-2)", borderRadius: 12, padding: "20px 24px", marginBottom: 16,
};
const HEADING: React.CSSProperties = {
  fontSize: 14, fontWeight: 700, color: "var(--ink-1)", marginBottom: 16,
  display: "flex", alignItems: "center", gap: 8,
};
const KPI_GRID: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 16,
};
const KPI_LABEL: React.CSSProperties = { fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 };
const KPI_VAL: React.CSSProperties = { fontSize: 22, fontWeight: 800, color: "var(--ink-1)" };

function KpiCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 20px" }}>
      <div style={KPI_LABEL}>{label}</div>
      <div style={{ ...KPI_VAL, color: tone || "var(--ink-1)" }} className="num">{value}</div>
    </div>
  );
}

type PartnerRow = { partner: string; mrrWon: number; deals: number; pipeline: number };

export default function ExecSummaryView() {
  const D = useData();
  const [month, setMonth] = useState(() => monthKey(new Date()));
  const [sortCol, setSortCol] = useState<SortCol>("mrrWon");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [pSortCol, setPSortCol] = useState<PartnerSortCol>("mrrWon");
  const [pSortDir, setPSortDir] = useState<SortDir>("desc");
  const [partnerData, setPartnerData] = useState<PartnerRow[]>([]);
  const [partnerLoading, setPartnerLoading] = useState(true);

  const monthOpts = useMemo(() => getMonthOptions(), []);

  useEffect(() => {
    let cancelled = false;
    setPartnerLoading(true);
    (async () => {
      const { data } = await supabase
        .from("deals")
        .select("partner,amount,deal_stage,close_date")
        .not("partner", "is", null);
      if (cancelled || !data) { setPartnerLoading(false); return; }

      const wonStages = new Set(["closed won", "closedwon", "won"]);
      const openStages = new Set(["closed won", "closedwon", "won", "closed lost", "closedlost", "lost"]);
      const byPartner = new Map<string, { mrrWon: number; deals: number; pipeline: number }>();

      for (const d of data as any[]) {
        const p = (d.partner || "").trim();
        if (!p) continue;
        const stage = (d.deal_stage || "").toLowerCase().trim();
        const amt = d.amount || 0;
        const close = d.close_date || "";

        if (!byPartner.has(p)) byPartner.set(p, { mrrWon: 0, deals: 0, pipeline: 0 });
        const row = byPartner.get(p)!;

        if (wonStages.has(stage) && close.startsWith(month)) {
          row.mrrWon += amt;
          row.deals += 1;
        }
        if (!openStages.has(stage)) {
          row.pipeline += amt;
        }
      }

      const rows: PartnerRow[] = [...byPartner.entries()]
        .map(([partner, v]) => ({ partner, ...v }))
        .filter(r => r.mrrWon > 0 || r.pipeline > 0);

      if (!cancelled) {
        setPartnerData(rows);
        setPartnerLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [month]);

  const { wonDeals, lostDeals, openDeals } = useMemo(() => {
    const won = D.benchmark.won.filter(d => d.closeDate && d.closeDate.startsWith(month));
    const lost = D.benchmark.lost.filter(d => d.closeDate && d.closeDate.startsWith(month));
    const open = D.forecast.allDeals;
    return { wonDeals: won, lostDeals: lost, openDeals: open };
  }, [D.benchmark, D.forecast.allDeals, month]);

  const kpis = useMemo(() => {
    const mrrWon = wonDeals.reduce((s, d) => s + (d.mrr || 0), 0);
    const logos = wonDeals.length;
    const totalClosed = wonDeals.length + lostDeals.length;
    const winRate = totalClosed > 0 ? Math.round((wonDeals.length / totalClosed) * 100) : 0;
    const pipeline = openDeals.reduce((s, d) => s + (d.mrr || 0), 0);
    const avgCycle = wonDeals.length > 0
      ? Math.round(wonDeals.reduce((s, d) => s + (d.dealAge || 0), 0) / wonDeals.length)
      : 0;

    const demoStages = new Set(["demo", "after demo", "demo scheduled", "demo completed", "product alignment"]);
    const demos = wonDeals.length + lostDeals.length > 0
      ? wonDeals.filter(d => d.dealAge != null).length + lostDeals.filter(d => d.dealAge != null).length
      : 0;

    return { mrrWon, logos, winRate, pipeline, avgCycle, demos };
  }, [wonDeals, lostDeals, openDeals]);

  const teamRows = useMemo(() => {
    const teams = ACTIVE_TEAMS as unknown as string[];
    return teams.map(team => {
      const teamEmails = expandTeam(team);
      const tw = wonDeals.filter(d => teamEmails.has(d.team));
      const tl = lostDeals.filter(d => teamEmails.has(d.team));
      const to = openDeals.filter(d => teamEmails.has(d.team || ""));
      const totalClosed = tw.length + tl.length;
      return {
        team,
        mrrWon: tw.reduce((s, d) => s + (d.mrr || 0), 0),
        demos: totalClosed,
        logos: tw.length,
        pipeline: to.reduce((s, d) => s + (d.mrr || 0), 0),
        winRate: totalClosed > 0 ? Math.round((tw.length / totalClosed) * 100) : 0,
        avgCycle: tw.length > 0 ? Math.round(tw.reduce((s, d) => s + (d.dealAge || 0), 0) / tw.length) : 0,
      };
    }).filter(r => r.mrrWon > 0 || r.pipeline > 0 || r.logos > 0);
  }, [wonDeals, lostDeals, openDeals]);

  const sortedTeams = useMemo(() => {
    const rows = [...teamRows];
    rows.sort((a, b) => {
      const av = a[sortCol] ?? "";
      const bv = b[sortCol] ?? "";
      if (typeof av === "string" && typeof bv === "string")
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return rows;
  }, [teamRows, sortCol, sortDir]);

  const stageDistribution = useMemo(() => {
    const byStage = new Map<string, { count: number; mrr: number }>();
    for (const d of openDeals) {
      const s = d.stage || "Other";
      const cur = byStage.get(s) || { count: 0, mrr: 0 };
      cur.count += 1;
      cur.mrr += d.mrr || 0;
      byStage.set(s, cur);
    }
    return [...byStage.entries()]
      .map(([stage, v]) => ({ stage, ...v }))
      .sort((a, b) => b.mrr - a.mrr);
  }, [openDeals]);

  const forecastCategories = useMemo(() => {
    const cats = new Map<string, { count: number; mrr: number }>();
    for (const d of openDeals) {
      const cat = (d as any).hsCategory || "Unset";
      const cur = cats.get(cat) || { count: 0, mrr: 0 };
      cur.count += 1;
      cur.mrr += d.mrr || 0;
      cats.set(cat, cur);
    }
    return [...cats.entries()]
      .map(([category, v]) => ({ category, ...v }))
      .sort((a, b) => b.mrr - a.mrr);
  }, [openDeals]);

  const lossReasons = useMemo(() => {
    const reasons = new Map<string, number>();
    for (const d of lostDeals) {
      const r = d.lostReason || "Unknown";
      reasons.set(r, (reasons.get(r) || 0) + 1);
    }
    return [...reasons.entries()]
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [lostDeals]);

  const sortedPartners = useMemo(() => {
    const rows = [...partnerData];
    rows.sort((a, b) => {
      const av = a[pSortCol] ?? "";
      const bv = b[pSortCol] ?? "";
      if (typeof av === "string" && typeof bv === "string")
        return pSortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return pSortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return rows;
  }, [partnerData, pSortCol, pSortDir]);

  const toggleSort = (col: SortCol) => {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("desc"); }
  };
  const togglePSort = (col: PartnerSortCol) => {
    if (pSortCol === col) setPSortDir(d => d === "asc" ? "desc" : "asc");
    else { setPSortCol(col); setPSortDir("desc"); }
  };

  const fmtPct = (v: number) => `${v}%`;
  const fmtDays = (v: number) => v > 0 ? `${v}d` : "—";
  const fmtInt = (v: number) => String(v);

  const TH: React.CSSProperties = {
    padding: "10px 12px", fontWeight: 600, color: "var(--ink-3)", fontSize: 11,
    textTransform: "uppercase", letterSpacing: ".08em", cursor: "pointer",
    userSelect: "none", borderBottom: "1px solid var(--line)", whiteSpace: "nowrap",
  };
  const TD: React.CSSProperties = { padding: "10px 12px", fontSize: 13 };

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 28 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-1)", margin: 0 }}>Executive Summary</h2>
        <span style={{ flex: 1 }} />
        <select
          value={month}
          onChange={e => setMonth(e.target.value)}
          className="cz-native-select"
          style={{ fontSize: 13, padding: "6px 12px" }}
        >
          {monthOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {/* Section 1: KPI Cards */}
      <div style={KPI_GRID}>
        <KpiCard label="MRR Won" value={fmtMRR(kpis.mrrWon)} tone={kpis.mrrWon > 0 ? "var(--green-ink)" : undefined} />
        <KpiCard label="Logos Won" value={fmtInt(kpis.logos)} />
        <KpiCard label="Win Rate" value={fmtPct(kpis.winRate)} tone={kpis.winRate >= 30 ? "var(--green-ink)" : kpis.winRate > 0 ? "var(--red-ink)" : undefined} />
        <KpiCard label="Open Pipeline" value={fmtMRR(kpis.pipeline)} />
        <KpiCard label="Avg Sales Cycle" value={fmtDays(kpis.avgCycle)} />
        <KpiCard label="Deals Closed" value={fmtInt(kpis.demos)} />
      </div>

      {/* Section 2: Team Performance */}
      <section style={{ ...CARD, marginTop: 24 }}>
        <div style={HEADING}>
          <Icon name="users" size={18} />
          Team Performance
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: "var(--ink-4)", fontWeight: 400 }}>{monthLabel(month)}</span>
        </div>
        {sortedTeams.length === 0 ? (
          <p style={{ color: "var(--ink-3)", fontSize: 13 }}>No team data for this period.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {([["team","Team","left"],["mrrWon","MRR Won","right"],["demos","Closed","right"],["logos","Logos","right"],["pipeline","Pipeline","right"],["winRate","Win Rate","right"],["avgCycle","Avg Cycle","right"]] as [SortCol,string,string][]).map(([key,label,align]) => (
                    <th key={key} onClick={() => toggleSort(key)} style={{ ...TH, textAlign: align as any }}>
                      {label}
                      {sortCol === key && <span style={{ marginLeft: 4, fontSize: 9 }}>{sortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedTeams.map(r => (
                  <tr key={r.team}>
                    <td style={{ ...TD, fontWeight: 500, color: "var(--ink-1)" }}>{r.team}</td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600 }} className="num">{fmtMRR(r.mrrWon)}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.demos}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.logos}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(r.pipeline)}</td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600, color: r.winRate >= 30 ? "var(--green-ink)" : r.winRate > 0 ? "var(--red-ink)" : "var(--ink-4)" }} className="num">{fmtPct(r.winRate)}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{fmtDays(r.avgCycle)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Section 3: Pipeline Analysis */}
      <section style={CARD}>
        <div style={HEADING}>
          <Icon name="layers" size={18} />
          Pipeline Analysis
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* Stage distribution */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 10 }}>Stage Distribution</div>
            {stageDistribution.length === 0 ? (
              <p style={{ color: "var(--ink-4)", fontSize: 12 }}>No open deals.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {stageDistribution.slice(0, 8).map(s => {
                  const maxMrr = stageDistribution[0]?.mrr || 1;
                  const pct = Math.round((s.mrr / maxMrr) * 100);
                  return (
                    <div key={s.stage} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 12, color: "var(--ink-2)", minWidth: 110, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.stage}</span>
                      <div style={{ flex: 1, height: 8, background: "var(--card)", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${pct}%`, background: "var(--indigo)", borderRadius: 4, minWidth: 2 }} />
                      </div>
                      <span className="num" style={{ fontSize: 11, color: "var(--ink-3)", minWidth: 50, textAlign: "right" }}>{fmtMRR(s.mrr)}</span>
                      <span className="num" style={{ fontSize: 11, color: "var(--ink-4)", minWidth: 24, textAlign: "right" }}>{s.count}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Forecast categories */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 10 }}>Forecast Categories</div>
            {forecastCategories.length === 0 ? (
              <p style={{ color: "var(--ink-4)", fontSize: 12 }}>No forecast data.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {forecastCategories.map(c => {
                  const maxMrr = forecastCategories[0]?.mrr || 1;
                  const pct = Math.round((c.mrr / maxMrr) * 100);
                  const tone = c.category === "Commit" ? "var(--green)" : c.category === "Pipeline" ? "var(--blue)" : c.category === "Upside" ? "var(--amber)" : "var(--ink-3)";
                  return (
                    <div key={c.category} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 12, color: "var(--ink-2)", minWidth: 80 }}>{c.category}</span>
                      <div style={{ flex: 1, height: 8, background: "var(--card)", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${pct}%`, background: tone, borderRadius: 4, minWidth: 2 }} />
                      </div>
                      <span className="num" style={{ fontSize: 11, color: "var(--ink-3)", minWidth: 50, textAlign: "right" }}>{fmtMRR(c.mrr)}</span>
                      <span className="num" style={{ fontSize: 11, color: "var(--ink-4)", minWidth: 24, textAlign: "right" }}>{c.count}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Section 4: Loss Analysis */}
      <section style={CARD}>
        <div style={HEADING}>
          <Icon name="xCircle" size={18} />
          Loss Analysis
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: "var(--ink-4)", fontWeight: 400 }}>{lostDeals.length} lost in {monthLabel(month)}</span>
        </div>
        {lossReasons.length === 0 ? (
          <p style={{ color: "var(--ink-3)", fontSize: 13 }}>No lost deals in this period.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {lossReasons.map(r => {
              const maxCount = lossReasons[0]?.count || 1;
              const pct = Math.round((r.count / maxCount) * 100);
              return (
                <div key={r.reason} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 12, color: "var(--ink-2)", minWidth: 200, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.reason}</span>
                  <div style={{ flex: 1, height: 8, background: "var(--card)", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: "var(--red)", borderRadius: 4, minWidth: 2 }} />
                  </div>
                  <span className="num" style={{ fontSize: 12, fontWeight: 600, color: "var(--red-ink)", minWidth: 24, textAlign: "right" }}>{r.count}</span>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Section 5: Partner Performance */}
      <section style={CARD}>
        <div style={HEADING}>
          <Icon name="building" size={18} />
          Partner Performance
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: "var(--ink-4)", fontWeight: 400 }}>{monthLabel(month)}</span>
        </div>
        {partnerLoading ? (
          <p style={{ color: "var(--ink-3)", fontSize: 13 }}>Loading partner data...</p>
        ) : sortedPartners.length === 0 ? (
          <p style={{ color: "var(--ink-3)", fontSize: 13 }}>No partner data for this period.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {([["partner","Partner","left"],["mrrWon","MRR Won","right"],["deals","Won Deals","right"],["pipeline","Open Pipeline","right"]] as [PartnerSortCol,string,string][]).map(([key,label,align]) => (
                    <th key={key} onClick={() => togglePSort(key)} style={{ ...TH, textAlign: align as any }}>
                      {label}
                      {pSortCol === key && <span style={{ marginLeft: 4, fontSize: 9 }}>{pSortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedPartners.map(r => (
                  <tr key={r.partner}>
                    <td style={{ ...TD, fontWeight: 500, color: "var(--ink-1)" }}>{r.partner}</td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600 }} className="num">{fmtMRR(r.mrrWon)}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.deals}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(r.pipeline)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
