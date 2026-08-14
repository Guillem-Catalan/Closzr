import { Icon, Chip, SectionLabel, Trend, AreaLine, fmtMRR, TONE } from "../components";
import type { Period, RepStatRow } from "../../data/useRepStats";
import type { TeamStatRow } from "../../data/useTeamStats";

/* ────────── Props ────────── */

type Props = {
  email: string;
  name: string;
  stats: RepStatRow[];
  teamStats: TeamStatRow[];
  allRepStats: Map<string, RepStatRow[]>;
  teamName: string;
  emailToTeam: Map<string, string>;
  period: Period;
  onBack: () => void;
  onPeriodChange: (p: Period) => void;
};

/* ────────── Data helpers ────────── */

function getStat(stats: RepStatRow[], key: string): number | null {
  return stats.find(s => s.key === key)?.value ?? null;
}

function getPattern(stats: RepStatRow[], key: string): string {
  return stats.find(s => s.key === key)?.pattern ?? "";
}

function getHistory(stats: RepStatRow[], key: string): number[] {
  const row = stats.find(s => s.key === key);
  if (!row?.history?.length) return [];
  return row.history.map(h => h.value);
}

function getTeamStat(teamStats: TeamStatRow[], statKey: string, aggregate: string): number | null {
  const lookupKey = `${statKey}_${aggregate}`;
  return teamStats.find(s => s.key === lookupKey)?.value ?? null;
}

function getTeamRank(
  allRepStats: Map<string, RepStatRow[]>,
  emailToTeam: Map<string, string>,
  teamName: string,
  email: string,
  statKey: string,
  lowerIsBetter = false,
): string {
  if (!teamName) return "";
  const teamValues: { email: string; value: number }[] = [];
  for (const [repEmail, repStats] of allRepStats) {
    if (emailToTeam.get(repEmail) !== teamName) continue;
    const v = getStat(repStats, statKey);
    if (v != null) teamValues.push({ email: repEmail, value: v });
  }
  if (teamValues.length < 2) return "";
  teamValues.sort((a, b) => lowerIsBetter ? a.value - b.value : b.value - a.value);
  const rank = teamValues.findIndex(t => t.email === email) + 1;
  if (rank === 0) return "";
  return `${rank}/${teamValues.length}`;
}

function rankTone(rank: string): string {
  if (!rank) return "ink";
  const parts = rank.split("/");
  const pos = parseInt(parts[0]);
  const total = parseInt(parts[1]);
  if (isNaN(pos) || isNaN(total) || total < 2) return "ink";
  const pct = pos / total;
  if (pct <= 0.25) return "green";
  if (pct <= 0.75) return "amber";
  return "red";
}

/* ────────── Formatters ────────── */

function fmtPct(v: number | null): string { return v != null ? `${Math.round(v)}%` : "—"; }
function fmtDays(v: number | null): string { return v != null ? `${Math.round(v)}d` : "—"; }
function fmtRatio(v: number | null): string { return v != null ? v.toFixed(2) : "—"; }
function fmtDec(v: number | null): string { return v != null ? v.toFixed(1) : "—"; }
function fmtInt(v: number | null): string { return v != null ? String(Math.round(v)) : "—"; }
function fmtMin(v: number | null): string { return v != null ? `${Math.round(v)} min` : "—"; }

/* ────────── Style constants ────────── */

const CARD: React.CSSProperties = {
  background: "var(--card-2)", borderRadius: 12, padding: "20px 24px", marginBottom: 16,
};

const HEADING: React.CSSProperties = {
  fontSize: 14, fontWeight: 700, color: "var(--ink-1)", marginBottom: 16,
  display: "flex", alignItems: "center", gap: 8,
};

const GRID: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "12px 24px",
};

const LABEL: React.CSSProperties = { fontSize: 11, color: "var(--ink-3)", marginBottom: 2, textTransform: "uppercase", letterSpacing: ".06em" };
const VAL: React.CSSProperties = { fontSize: 16, fontWeight: 700, color: "var(--ink-1)" };

const KPI_CARD: React.CSSProperties = {
  background: "var(--card)", borderRadius: 10, padding: "16px 18px",
  display: "flex", flexDirection: "column", gap: 6, minWidth: 0,
};

const TEAM_REF: React.CSSProperties = { fontSize: 12, fontWeight: 400, color: "var(--ink-3)", marginLeft: 4 };

/* ────────── Reusable sub-components ────────── */

function Stat({ label, value, unit, teamRef }: { label: string; value: string; unit?: string; teamRef?: string }) {
  return (
    <div>
      <div style={LABEL}>{label}</div>
      <div style={VAL} className="num">
        {value}
        {unit && <span style={{ fontSize: 12, fontWeight: 400, color: "var(--ink-3)", marginLeft: 2 }}>{unit}</span>}
        {teamRef && <span style={TEAM_REF}>(team: {teamRef})</span>}
      </div>
    </div>
  );
}

function TextStat({ label, text }: { label: string; text: string }) {
  if (!text || text === "—") return null;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={LABEL}>{label}</div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.5, marginTop: 4 }}>{text}</div>
    </div>
  );
}

function BulletStat({ label, text }: { label: string; text: string }) {
  if (!text) return null;
  const items = text.split(/[;,\n]/).map(s => s.trim()).filter(Boolean);
  if (items.length === 0) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={LABEL}>{label}</div>
      <ul style={{ margin: "6px 0 0 0", padding: "0 0 0 16px", fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7 }}>
        {items.map((item, i) => <li key={i}>{item}</li>)}
      </ul>
    </div>
  );
}

function HBar({ label, pct, count, tone = "indigo" }: { label: string; pct: number; count?: string; tone?: string }) {
  const t = TONE[tone] || TONE.indigo;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
      <span style={{ fontSize: 12, color: "var(--ink-2)", width: 60, textAlign: "right", flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 14, borderRadius: 7, background: "var(--line)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${Math.min(pct, 100)}%`, background: t.fg, borderRadius: 7, transition: "width .3s" }} />
      </div>
      <span className="num" style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-1)", width: 40, textAlign: "right" }}>{Math.round(pct)}%</span>
      {count && <span style={{ fontSize: 11, color: "var(--ink-4)", width: 30, textAlign: "right" }}>({count})</span>}
    </div>
  );
}

function AlertCard({ pattern, severity }: { pattern: string; severity: number }) {
  const tone = severity >= 3 ? "red" : severity >= 2 ? "amber" : "blue";
  const t = TONE[tone] || TONE.ink;
  return (
    <div style={{
      background: "var(--card)", borderRadius: 10, padding: "14px 18px",
      borderLeft: `4px solid ${t.fg}`, marginBottom: 8,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <Chip tone={tone} style={{ fontSize: 11 }}>
          {severity >= 3 ? "HIGH" : severity >= 2 ? "MEDIUM" : "LOW"}
        </Chip>
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.5 }}>{pattern}</div>
    </div>
  );
}

/* ────────── Period toggle ────────── */

const PERIODS: { value: Period; label: string }[] = [
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
];

/* ────────── KPI card for Performance Summary ────────── */

function KpiCard({ label, value, history, delta, rank, rankColor }: {
  label: string;
  value: string;
  history: number[];
  delta: number | null;
  rank: string;
  rankColor: string;
}) {
  return (
    <div style={KPI_CARD}>
      <div style={LABEL}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 22, fontWeight: 800, color: "var(--ink-1)" }} className="num">{value}</span>
        <Trend value={delta != null ? Math.round(delta) : null} />
      </div>
      {history.length > 1 && (
        <div style={{ height: 44, marginTop: 2 }}>
          <AreaLine points={history} h={44} w={200} min={Math.min(...history) * 0.8} max={Math.max(...history) * 1.2 || 100} />
        </div>
      )}
      {rank && (
        <div style={{ marginTop: 4 }}>
          <Chip tone={rankColor} style={{ fontSize: 11 }}>{rank}</Chip>
        </div>
      )}
    </div>
  );
}

/* ────────── Parse WR by employee size pattern ────────── */

function parseWrBySize(pattern: string): { label: string; pct: number; count: string }[] {
  if (!pattern) return [];
  // Pattern format: "WR by size: XS(1-10): 15% (8d), S(11-50): 22% (12d), ..."
  const data = pattern.replace(/^[^:]+:\s*/, "");
  const results: { label: string; pct: number; count: string }[] = [];
  const segments = data.split(",").map(s => s.trim());
  for (const seg of segments) {
    const m = seg.match(/^([^:]+):\s*([\d.]+)%\s*\((\d+)d\)/);
    if (m) {
      results.push({ label: m[1].trim(), pct: parseFloat(m[2]), count: m[3] });
    }
  }
  return results;
}

/* ────────── Parse role distribution pattern ────────── */

function parseRoleDistribution(pattern: string): { label: string; pct: number; tone: string }[] {
  if (!pattern) return [];
  // Pattern format: "Role distribution: C-suite: 15%, Director: 20%, HR: 10%, Manager: 25%, Other: 30%"
  const data = pattern.replace(/^[^:]+:\s*/, "");
  const ROLE_TONES: Record<string, string> = {
    "C-suite": "indigo", "Director": "blue", "HR": "violet", "Manager": "amber", "Other": "ink",
  };
  const results: { label: string; pct: number; tone: string }[] = [];
  const segments = data.split(",").map(s => s.trim());
  for (const seg of segments) {
    const m = seg.match(/^([^:]+):\s*([\d.]+)%/);
    if (m) {
      const label = m[1].trim();
      const tone = ROLE_TONES[label] || "ink";
      results.push({ label, pct: parseFloat(m[2]), tone });
    }
  }
  return results;
}

/* ────────── Main component ────────── */

export default function RepDetail({
  email, name, stats, teamStats, allRepStats, teamName, emailToTeam,
  period, onBack, onPeriodChange,
}: Props) {

  /* ── Compute trend deltas from history ── */
  const trendDelta = (key: string): number | null => {
    const h = getHistory(stats, key);
    const current = getStat(stats, key);
    if (!h.length || current == null) return null;
    return current - h[h.length - 1];
  };

  /* ── Team reference shorthand ── */
  const teamMedian = (key: string) => {
    const v = getTeamStat(teamStats, key, "median");
    return v != null ? fmtPct(v) : null;
  };
  const teamMedianDays = (key: string) => {
    const v = getTeamStat(teamStats, key, "median");
    return v != null ? fmtDays(v) : null;
  };
  const teamMedianDec = (key: string) => {
    const v = getTeamStat(teamStats, key, "median");
    return v != null ? fmtDec(v) : null;
  };
  const teamMedianRatio = (key: string) => {
    const v = getTeamStat(teamStats, key, "median");
    return v != null ? fmtRatio(v) : null;
  };
  const teamMedianMin = (key: string) => {
    const v = getTeamStat(teamStats, key, "median");
    return v != null ? fmtMin(v) : null;
  };

  /* ── Alerts ── */
  const alerts = stats
    .filter(s => s.key.startsWith("alert_"))
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

  /* ── Parse pattern-based stats ── */
  const wrBySizeData = parseWrBySize(getPattern(stats, "wr_by_employee_size"));
  const roleDistData = parseRoleDistribution(getPattern(stats, "contact_role_distribution"));
  const sweetSpot = getPattern(stats, "sweet_spot_segment");

  return (
    <div>
      {/* ━━━ Header ━━━ */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <button onClick={onBack} style={{
          background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)",
          fontSize: 13, display: "flex", alignItems: "center", gap: 4, padding: 0,
        }}>
          <Icon name="arrowLeft" size={16} /> Back
        </button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-1)", margin: 0 }}>{name}</h2>
          <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
            {email}
            {teamName && <> &middot; {teamName}</>}
          </span>
        </div>
        <div style={{
          display: "inline-flex", borderRadius: "var(--r-pill)", background: "var(--card-2)",
          padding: 3, gap: 2,
        }}>
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => onPeriodChange(p.value)}
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
      </div>

      {/* ━━━ 1. Performance Summary ━━━ */}
      <section style={{ ...CARD, padding: "20px 20px" }}>
        <SectionLabel letter="A" tone="indigo">PERFORMANCE SUMMARY</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
          {([
            { label: "Win Rate", key: "win_rate", fmt: fmtPct, lowerIsBetter: false },
            { label: "Post-Demo WR", key: "post_demo_win_rate", fmt: fmtPct, lowerIsBetter: false },
            { label: "Avg Cycle (Won)", key: "avg_cycle_won", fmt: fmtDays, lowerIsBetter: true },
            { label: "Pipeline Value", key: "pipeline_value", fmt: fmtMRR, lowerIsBetter: false },
            { label: "Demo Rate", key: "demo_rate", fmt: fmtPct, lowerIsBetter: false },
          ] as const).map(kpi => {
            const v = getStat(stats, kpi.key);
            const rank = getTeamRank(allRepStats, emailToTeam, teamName, email, kpi.key, kpi.lowerIsBetter);
            return (
              <KpiCard
                key={kpi.key}
                label={kpi.label}
                value={kpi.fmt(v)}
                history={getHistory(stats, kpi.key)}
                delta={trendDelta(kpi.key)}
                rank={rank}
                rankColor={rankTone(rank)}
              />
            );
          })}
        </div>
      </section>

      {/* ━━━ 2. Closing Effectiveness ━━━ */}
      <section style={CARD}>
        <SectionLabel letter="B" tone="blue">CLOSING EFFECTIVENESS</SectionLabel>
        <div style={GRID}>
          <Stat label="Win Rate" value={fmtPct(getStat(stats, "win_rate"))} teamRef={teamMedian("win_rate") ?? undefined} />
          <Stat label="Avg Cycle (Won)" value={fmtDays(getStat(stats, "avg_cycle_won"))} teamRef={teamMedianDays("avg_cycle_won") ?? undefined} />
          <Stat label="Avg Cycle (Lost)" value={fmtDays(getStat(stats, "avg_cycle_lost"))} teamRef={teamMedianDays("avg_cycle_lost") ?? undefined} />
          <Stat label="Cycle Waste Ratio" value={fmtRatio(getStat(stats, "cycle_waste_ratio"))} teamRef={teamMedianRatio("cycle_waste_ratio") ?? undefined} />
          <Stat label="Slow Deaths" value={fmtPct(getStat(stats, "slow_deaths"))} teamRef={teamMedian("slow_deaths") ?? undefined} />
          <Stat label="High-Conf Losses" value={fmtPct(getStat(stats, "high_conf_losses"))} teamRef={teamMedian("high_conf_losses") ?? undefined} />
          <Stat label="Comeback Wins" value={fmtPct(getStat(stats, "comeback_wins"))} teamRef={teamMedian("comeback_wins") ?? undefined} />
          <Stat label="Prob Climb Rate" value={fmtDec(getStat(stats, "prob_climb_rate_won"))} unit="%/snap" teamRef={teamMedianDec("prob_climb_rate_won") ?? undefined} />
          <Stat label="Calls to Win" value={fmtDec(getStat(stats, "avg_calls_to_win"))} teamRef={teamMedianDec("avg_calls_to_win") ?? undefined} />
          <Stat label="Calls to Lose" value={fmtDec(getStat(stats, "avg_calls_to_lose"))} teamRef={teamMedianDec("avg_calls_to_lose") ?? undefined} />
          <Stat label="Win Rate (6m)" value={fmtPct(getStat(stats, "win_rate_rolling_6m"))} teamRef={teamMedian("win_rate_rolling_6m") ?? undefined} />
        </div>
        <TextStat label="Death Stage Distribution" text={getPattern(stats, "death_stage_distribution")} />
        <TextStat label="Loss Reason Concentration" text={getPattern(stats, "loss_reason_concentration")} />
        <TextStat label="Stage Conversion Funnel" text={getPattern(stats, "stage_conversion_funnel")} />
        <TextStat label="Weakest MEDDIC at Loss" text={getPattern(stats, "weakest_meddic_at_loss")} />
      </section>

      {/* ━━━ 3. Demo Funnel ━━━ */}
      <section style={CARD}>
        <SectionLabel letter="C" tone="violet">DEMO FUNNEL</SectionLabel>
        <div style={GRID}>
          <Stat label="Demo Rate" value={fmtPct(getStat(stats, "demo_rate"))} teamRef={teamMedian("demo_rate") ?? undefined} />
          <Stat label="Post-Demo Win Rate" value={fmtPct(getStat(stats, "post_demo_win_rate"))} teamRef={teamMedian("post_demo_win_rate") ?? undefined} />
          <Stat label="Avg Days to Demo" value={fmtDays(getStat(stats, "avg_days_to_demo"))} teamRef={teamMedianDays("avg_days_to_demo") ?? undefined} />
          <Stat label="Demo-to-Close Days" value={fmtDays(getStat(stats, "demo_to_close_days"))} teamRef={teamMedianDays("demo_to_close_days") ?? undefined} />
          <Stat label="No-Demo Loss Rate" value={fmtPct(getStat(stats, "no_demo_loss_rate"))} teamRef={teamMedian("no_demo_loss_rate") ?? undefined} />
        </div>
      </section>

      {/* ━━━ 4. Contact & Stakeholder Quality ━━━ */}
      <section style={CARD}>
        <SectionLabel letter="D" tone="teal">CONTACT & STAKEHOLDER QUALITY</SectionLabel>
        <div style={GRID}>
          <Stat label="Avg Contacts/Deal" value={fmtDec(getStat(stats, "avg_contacts_per_deal"))} teamRef={teamMedianDec("avg_contacts_per_deal") ?? undefined} />
          <Stat label="Multi-Thread Rate" value={fmtPct(getStat(stats, "multi_thread_rate"))} teamRef={teamMedian("multi_thread_rate") ?? undefined} />
          <Stat label="Multi-Thread Demo Rate" value={fmtPct(getStat(stats, "multi_thread_demo_rate"))} teamRef={teamMedian("multi_thread_demo_rate") ?? undefined} />
          <Stat label="DM Access Rate" value={fmtPct(getStat(stats, "dm_access_rate"))} teamRef={teamMedian("dm_access_rate") ?? undefined} />
        </div>
        {roleDistData.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div style={LABEL}>ROLE DISTRIBUTION</div>
            <div style={{ marginTop: 8 }}>
              {roleDistData.map((rd, i) => (
                <HBar key={i} label={rd.label} pct={rd.pct} tone={rd.tone} />
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ━━━ 5. Pipeline Health ━━━ */}
      <section style={CARD}>
        <SectionLabel letter="E" tone="amber" right={
          <span style={{ fontSize: 11, color: "var(--ink-4)", fontWeight: 400 }}>(live snapshot)</span>
        }>PIPELINE HEALTH</SectionLabel>
        <div style={GRID}>
          <Stat label="Active Deals" value={fmtInt(getStat(stats, "active_deals_count"))} />
          <Stat label="Pipeline Value" value={fmtMRR(getStat(stats, "pipeline_value"))} />
          <Stat label="Stale Deals" value={fmtPct(getStat(stats, "stale_deals"))} />
          <Stat label="Avg Deal Age" value={fmtDays(getStat(stats, "avg_deal_age"))} />
        </div>
        <TextStat label="Momentum Distribution" text={getPattern(stats, "momentum_distribution")} />
        <TextStat label="Stage Distribution" text={getPattern(stats, "stage_distribution")} />
      </section>

      {/* ━━━ 6. Process Quality ━━━ */}
      <section style={CARD}>
        <SectionLabel letter="F" tone="green">PROCESS QUALITY / MEDDIC-BANT</SectionLabel>
        <div style={GRID}>
          <Stat label="MEDDIC Avg" value={fmtDec(getStat(stats, "avg_meddic_per_pillar"))} unit="/10" teamRef={teamMedianDec("avg_meddic_per_pillar") ?? undefined} />
          <Stat label="Discovery Level" value={fmtDec(getStat(stats, "discovery_level_avg"))} teamRef={teamMedianDec("discovery_level_avg") ?? undefined} />
          <Stat label="Audit Score" value={fmtDec(getStat(stats, "win_rate_score_avg"))} teamRef={teamMedianDec("win_rate_score_avg") ?? undefined} />
          <Stat label="BANT Completion" value={fmtPct(getStat(stats, "bant_completion_rate"))} teamRef={teamMedian("bant_completion_rate") ?? undefined} />
        </div>
        <TextStat label="Weakest Pillar" text={getPattern(stats, "weakest_pillar")} />
        <TextStat label="Strongest Pillar" text={getPattern(stats, "strongest_pillar")} />
        <TextStat label="Lead Temperature" text={getPattern(stats, "lead_temperature_distribution")} />
      </section>

      {/* ━━━ 7. Segment Performance ━━━ */}
      <section style={CARD}>
        <SectionLabel letter="G" tone="blue">SEGMENT PERFORMANCE</SectionLabel>
        {wrBySizeData.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={LABEL}>WIN RATE BY EMPLOYEE SIZE</div>
            <div style={{ marginTop: 8 }}>
              {wrBySizeData.map((d, i) => (
                <HBar key={i} label={d.label} pct={d.pct} count={d.count} tone="blue" />
              ))}
            </div>
          </div>
        )}
        <div style={GRID}>
          {sweetSpot && (
            <div>
              <div style={LABEL}>Sweet Spot</div>
              <div style={{ marginTop: 4 }}><Chip tone="green">{sweetSpot}</Chip></div>
            </div>
          )}
          <Stat label="Avg Deal Size (Won)" value={fmtMRR(getStat(stats, "avg_deal_size_won"))} teamRef={(() => { const v = getTeamStat(teamStats, "avg_deal_size_won", "median"); return v != null ? fmtMRR(v) : undefined; })()} />
        </div>
      </section>

      {/* ━━━ 8. Coaching Alerts ━━━ */}
      {alerts.length > 0 && (
        <section style={CARD}>
          <SectionLabel letter="H" tone="red">COACHING ALERTS</SectionLabel>
          {alerts.map((a, i) => (
            <AlertCard key={i} pattern={a.pattern} severity={a.value ?? 1} />
          ))}
        </section>
      )}

      {/* ━━━ Activity & Cadence (compact) ━━━ */}
      {(getStat(stats, "calls_per_week") != null || getStat(stats, "avg_call_duration") != null) && (
        <section style={{ ...CARD, opacity: 0.85 }}>
          <div style={{ ...HEADING, fontSize: 12, color: "var(--ink-3)" }}>Activity & Cadence</div>
          <div style={GRID}>
            <Stat label="Calls/Week" value={fmtDec(getStat(stats, "calls_per_week"))} teamRef={teamMedianDec("calls_per_week") ?? undefined} />
            <Stat label="Avg Call Duration" value={fmtMin(getStat(stats, "avg_call_duration"))} teamRef={teamMedianMin("avg_call_duration") ?? undefined} />
            <Stat label="Calls/Deal" value={fmtDec(getStat(stats, "calls_per_deal"))} teamRef={teamMedianDec("calls_per_deal") ?? undefined} />
          </div>
        </section>
      )}
    </div>
  );
}
