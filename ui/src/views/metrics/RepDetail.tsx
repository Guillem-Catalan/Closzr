import { Icon, Chip, fmtMRR } from "../components";
import type { Period, RepStatRow } from "../../data/useRepStats";

type Props = {
  email: string;
  name: string;
  stats: RepStatRow[];
  period: Period;
  onBack: () => void;
  onPeriodChange: (p: Period) => void;
};

function getStat(stats: RepStatRow[], key: string): number | null {
  return stats.find(s => s.key === key)?.value ?? null;
}

function getPattern(stats: RepStatRow[], key: string): string {
  return stats.find(s => s.key === key)?.pattern ?? "";
}

function fmtPct(v: number | null): string { return v != null ? `${Math.round(v)}%` : "—"; }
function fmtDays(v: number | null): string { return v != null ? `${Math.round(v)}d` : "—"; }
function fmtRatio(v: number | null): string { return v != null ? v.toFixed(2) : "—"; }
function fmtDec(v: number | null): string { return v != null ? v.toFixed(1) : "—"; }
function fmtInt(v: number | null): string { return v != null ? String(Math.round(v)) : "—"; }
function fmtMin(v: number | null): string { return v != null ? `${Math.round(v)} min` : "—"; }

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

function Stat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div>
      <div style={LABEL}>{label}</div>
      <div style={VAL} className="num">
        {value}{unit && <span style={{ fontSize: 12, fontWeight: 400, color: "var(--ink-3)", marginLeft: 2 }}>{unit}</span>}
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

const PERIODS: { value: Period; label: string }[] = [
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
];

export default function RepDetail({ email, name, stats, period, onBack, onPeriodChange }: Props) {
  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <button onClick={onBack} style={{
          background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)",
          fontSize: 13, display: "flex", alignItems: "center", gap: 4, padding: 0,
        }}>
          <Icon name="arrowLeft" size={16} /> Back
        </button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-1)", margin: 0 }}>{name}</h2>
          <span style={{ fontSize: 13, color: "var(--ink-3)" }}>{email}</span>
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

      {/* A. Closing Effectiveness */}
      <section style={CARD}>
        <div style={HEADING}>
          <Chip tone="indigo">A</Chip>
          Closing Effectiveness
        </div>
        <div style={GRID}>
          <Stat label="Win Rate" value={fmtPct(getStat(stats, "win_rate"))} />
          <Stat label="Avg Cycle (Won)" value={fmtDays(getStat(stats, "avg_cycle_won"))} />
          <Stat label="Avg Cycle (Lost)" value={fmtDays(getStat(stats, "avg_cycle_lost"))} />
          <Stat label="Cycle Waste Ratio" value={fmtRatio(getStat(stats, "cycle_waste_ratio"))} />
          <Stat label="Slow Deaths" value={fmtPct(getStat(stats, "slow_deaths"))} />
          <Stat label="High-Conf Losses" value={fmtPct(getStat(stats, "high_conf_losses"))} />
          <Stat label="Comeback Wins" value={fmtPct(getStat(stats, "comeback_wins"))} />
          <Stat label="Prob Climb Rate" value={fmtDec(getStat(stats, "prob_climb_rate_won"))} unit="%/snap" />
          <Stat label="Calls to Win" value={fmtDec(getStat(stats, "avg_calls_to_win"))} />
          <Stat label="Calls to Lose" value={fmtDec(getStat(stats, "avg_calls_to_lose"))} />
          <Stat label="Win Rate (6m)" value={fmtPct(getStat(stats, "win_rate_rolling_6m"))} />
        </div>
        <TextStat label="Death Stage Distribution" text={getPattern(stats, "death_stage_distribution")} />
        <TextStat label="Loss Reason Concentration" text={getPattern(stats, "loss_reason_concentration")} />
        <TextStat label="Stage Conversion Funnel" text={getPattern(stats, "stage_conversion_funnel")} />
        <TextStat label="Weakest MEDDIC at Loss" text={getPattern(stats, "weakest_meddic_at_loss")} />
      </section>

      {/* B. Pipeline Health */}
      <section style={CARD}>
        <div style={HEADING}>
          <Chip tone="teal">B</Chip>
          Pipeline Health
          <span style={{ fontSize: 11, color: "var(--ink-4)", fontWeight: 400, marginLeft: 4 }}>(live snapshot)</span>
        </div>
        <div style={GRID}>
          <Stat label="Active Deals" value={fmtInt(getStat(stats, "active_deals_count"))} />
          <Stat label="Pipeline Value" value={fmtMRR(getStat(stats, "pipeline_value"))} />
          <Stat label="Stale Deals" value={fmtPct(getStat(stats, "stale_deals"))} />
          <Stat label="Avg Deal Age" value={fmtDays(getStat(stats, "avg_deal_age"))} />
        </div>
        <TextStat label="Momentum Distribution" text={getPattern(stats, "momentum_distribution")} />
        <TextStat label="Stage Distribution" text={getPattern(stats, "stage_distribution")} />
      </section>

      {/* C. Process Quality */}
      <section style={CARD}>
        <div style={HEADING}>
          <Chip tone="violet">C</Chip>
          Process Quality / MEDDIC-BANT
        </div>
        <div style={GRID}>
          <Stat label="MEDDIC Avg" value={fmtDec(getStat(stats, "avg_meddic_per_pillar"))} unit="/10" />
          <Stat label="Discovery Level" value={fmtDec(getStat(stats, "discovery_level_avg"))} />
          <Stat label="Audit Score" value={fmtDec(getStat(stats, "win_rate_score_avg"))} />
          <Stat label="BANT Completion" value={fmtPct(getStat(stats, "bant_completion_rate"))} />
        </div>
        <TextStat label="Weakest Pillar" text={getPattern(stats, "weakest_pillar")} />
        <TextStat label="Strongest Pillar" text={getPattern(stats, "strongest_pillar")} />
        <TextStat label="Lead Temperature" text={getPattern(stats, "lead_temperature_distribution")} />
      </section>

      {/* D. Coaching & Gaps */}
      <section style={CARD}>
        <div style={HEADING}>
          <Chip tone="amber">D</Chip>
          Coaching & Gaps
        </div>
        <BulletStat label="Top Improvement Items" text={getPattern(stats, "top_improvement_items")} />
        <BulletStat label="Top Strengths" text={getPattern(stats, "top_strengths")} />
        <BulletStat label="Recurring Biggest Gaps" text={getPattern(stats, "recurring_biggest_gaps")} />
        <TextStat label="Red Flags Frequency" text={getPattern(stats, "red_flags_frequency")} />
      </section>

      {/* E. Activity & Cadence */}
      <section style={CARD}>
        <div style={HEADING}>
          <Chip tone="blue">E</Chip>
          Activity & Cadence
        </div>
        <div style={GRID}>
          <Stat label="Calls/Week" value={fmtDec(getStat(stats, "calls_per_week"))} />
          <Stat label="Avg Call Duration" value={fmtMin(getStat(stats, "avg_call_duration"))} />
          <Stat label="Calls/Deal" value={fmtDec(getStat(stats, "calls_per_deal"))} />
        </div>
      </section>
    </div>
  );
}
