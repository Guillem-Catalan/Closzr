import { useState, useMemo } from "react";
import { useRepStats, type Period, type RepStatRow } from "../../data/useRepStats";
import { Icon, MultiSelectTeam, fmtMRR } from "../components";
import { ownerDisplayName, ACTIVE_TEAMS } from "../../display";
import { expandTeams } from "../../data/filters";
import RepDetail from "./RepDetail";

type SortCol = "name" | "winRate" | "avgCycle" | "pipeline" | "deals" | "calls" | "meddic";
type SortDir = "asc" | "desc";

function getStat(stats: RepStatRow[], key: string): number | null {
  const s = stats.find(s => s.key === key);
  return s?.value ?? null;
}

function getStatPattern(stats: RepStatRow[], key: string): string {
  return stats.find(s => s.key === key)?.pattern ?? "";
}

type RepRow = {
  email: string;
  name: string;
  team: string;
  winRate: number | null;
  avgCycle: number | null;
  pipeline: number | null;
  deals: number | null;
  calls: number | null;
  meddic: number | null;
  stats: RepStatRow[];
};

const PERIODS: { value: Period; label: string }[] = [
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
];

const COLS: { key: SortCol; label: string; align: "left" | "right" }[] = [
  { key: "name", label: "Rep", align: "left" },
  { key: "winRate", label: "Win Rate", align: "right" },
  { key: "avgCycle", label: "Avg Cycle", align: "right" },
  { key: "pipeline", label: "Pipeline", align: "right" },
  { key: "deals", label: "Deals", align: "right" },
  { key: "calls", label: "Calls/Wk", align: "right" },
  { key: "meddic", label: "MEDDIC", align: "right" },
];

export default function MetricsRepView() {
  const [period, setPeriod] = useState<Period>("monthly");
  const [teams, setTeams] = useState<Set<string>>(new Set());
  const [sortCol, setSortCol] = useState<SortCol>("winRate");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selectedRep, setSelectedRep] = useState<string | null>(null);

  const { stats, loading, error } = useRepStats(period);

  const rows = useMemo(() => {
    const expanded = expandTeams(teams);
    const result: RepRow[] = [];

    for (const [email, repStats] of stats) {
      const name = ownerDisplayName(email);
      const scope = repStats[0]?.scope || "";
      const team = scope.startsWith("rep:") ? "" : "";

      result.push({
        email,
        name,
        team: "",
        winRate: getStat(repStats, "win_rate"),
        avgCycle: getStat(repStats, "avg_cycle_won"),
        pipeline: getStat(repStats, "pipeline_value"),
        deals: getStat(repStats, "active_deals_count"),
        calls: getStat(repStats, "calls_per_week"),
        meddic: getStat(repStats, "avg_meddic_per_pillar"),
        stats: repStats,
      });
    }

    result.sort((a, b) => {
      const av = a[sortCol] ?? -Infinity;
      const bv = b[sortCol] ?? -Infinity;
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });

    return result;
  }, [stats, teams, sortCol, sortDir]);

  const toggleSort = (col: SortCol) => {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("desc"); }
  };

  if (selectedRep) {
    const repStats = stats.get(selectedRep) || [];
    return (
      <div style={{ padding: "24px 32px" }}>
        <RepDetail
          email={selectedRep}
          name={ownerDisplayName(selectedRep)}
          stats={repStats}
          period={period}
          onBack={() => setSelectedRep(null)}
          onPeriodChange={setPeriod}
        />
      </div>
    );
  }

  const fmtPct = (v: number | null) => v != null ? `${Math.round(v)}%` : "—";
  const fmtDays = (v: number | null) => v != null ? `${Math.round(v)}d` : "—";
  const fmtInt = (v: number | null) => v != null ? String(Math.round(v)) : "—";
  const fmtDec = (v: number | null) => v != null ? v.toFixed(1) : "—";
  const fmtScore = (v: number | null) => v != null ? v.toFixed(1) : "—";

  return (
    <div style={{ padding: "24px 32px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-1)", margin: 0 }}>Rep Stats</h2>
        <span style={{ flex: 1 }} />

        {/* Period toggle */}
        <div style={{
          display: "inline-flex", borderRadius: "var(--r-pill)", background: "var(--card-2)",
          padding: 3, gap: 2,
        }}>
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              style={{
                padding: "5px 14px", borderRadius: "var(--r-pill)", border: "none", cursor: "pointer",
                fontSize: 13, fontWeight: period === p.value ? 600 : 400,
                background: period === p.value ? "var(--card)" : "transparent",
                color: period === p.value ? "var(--ink-1)" : "var(--ink-3)",
                boxShadow: period === p.value ? "0 1px 3px rgba(0,0,0,.1)" : "none",
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        <MultiSelectTeam
          teams={ACTIVE_TEAMS as unknown as string[]}
          selected={teams}
          onChange={setTeams}
        />
      </div>

      {/* Content */}
      {loading && <p style={{ color: "var(--ink-3)", fontSize: 14 }}>Loading rep stats...</p>}
      {error && <p style={{ color: "var(--red)", fontSize: 14 }}>Error: {error}</p>}
      {!loading && !error && rows.length === 0 && (
        <p style={{ color: "var(--ink-3)", fontSize: 14 }}>No rep stats found for this period.</p>
      )}

      {!loading && !error && rows.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                {COLS.map(col => (
                  <th
                    key={col.key}
                    onClick={() => toggleSort(col.key)}
                    style={{
                      textAlign: col.align, padding: "10px 12px", fontWeight: 600,
                      color: "var(--ink-3)", fontSize: 11, textTransform: "uppercase",
                      letterSpacing: ".08em", cursor: "pointer", userSelect: "none",
                      borderBottom: "1px solid var(--line)", whiteSpace: "nowrap",
                    }}
                  >
                    {col.label}
                    {sortCol === col.key && (
                      <span style={{ marginLeft: 4, fontSize: 9 }}>
                        {sortDir === "asc" ? "▲" : "▼"}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr
                  key={r.email}
                  onClick={() => setSelectedRep(r.email)}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "var(--paper-2)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                >
                  <td style={{ padding: "10px 12px", fontWeight: 500, color: "var(--ink-1)" }}>{r.name}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", fontWeight: 600, color: r.winRate != null && r.winRate >= 30 ? "var(--green-ink)" : r.winRate != null ? "var(--red-ink)" : "var(--ink-4)" }} className="num">{fmtPct(r.winRate)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "var(--ink-2)" }} className="num">{fmtDays(r.avgCycle)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "var(--ink-2)" }} className="num">{fmtMRR(r.pipeline)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "var(--ink-2)" }} className="num">{fmtInt(r.deals)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "var(--ink-2)" }} className="num">{fmtDec(r.calls)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "var(--ink-2)" }} className="num">{fmtScore(r.meddic)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
