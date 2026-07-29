import { useState, useMemo, useEffect } from "react";
import { useData } from "../../data/store";
import type { BenchmarkDeal, ForecastDeal } from "../../data/store";
import { Chip, fmtMRR, Icon } from "../components";
import { ACTIVE_TEAMS, ownerDisplayName, TEAM_HIERARCHY } from "../../display";
import { expandTeam } from "../../data/filters";
import { supabase } from "../../data/supabase";

// ---- Types ----

type DateRange = { from: string; to: string };
type PresetKey = "mtd" | "qtd" | "ytd" | "last3m" | "last6m" | "custom";
type SortDir = "asc" | "desc";

type DealRaw = {
  deal_id: string;
  pae: string | null;
  pbd: string | null;
  team: string | null;
  partner: string | null;
  amount: number | null;
  deal_stage: string | null;
  close_date: string | null;
  createdate: string | null;
  after_demo_date: string | null;
  first_meeting_at: string | null;
  pipeline_name: string | null;
  employees: string | null;
};

type Delta = { abs: number; pct: number };

// ---- Constants ----

const PRESETS: { key: PresetKey; label: string }[] = [
  { key: "mtd", label: "MTD" },
  { key: "qtd", label: "QTD" },
  { key: "ytd", label: "YTD" },
  { key: "last3m", label: "3M" },
  { key: "last6m", label: "6M" },
  { key: "custom", label: "Custom" },
];

const WON_STAGES = new Set(["closed won", "closedwon", "won"]);
const LOST_STAGES = new Set(["closed lost", "closedlost", "lost"]);
const CLOSED_STAGES = new Set([...WON_STAGES, ...LOST_STAGES]);

const SIZE_BUCKETS: { label: string; min: number; max: number }[] = [
  { label: "XS (<50)", min: 0, max: 49 },
  { label: "S (50–200)", min: 50, max: 200 },
  { label: "M (200–1K)", min: 201, max: 1000 },
  { label: "L (1K–5K)", min: 1001, max: 5000 },
  { label: "XL (5K+)", min: 5001, max: Infinity },
];

const NOISE_THRESHOLD = 0.05;

// ---- Utility functions ----

function monthKey(d: Date): string {
  return d.toISOString().slice(0, 7);
}

function monthLabel(mk: string): string {
  const [y, m] = mk.split("-");
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${names[parseInt(m, 10) - 1]} ${y}`;
}

function rangeLabel(range: DateRange): string {
  if (range.from === range.to) return monthLabel(range.from);
  return `${monthLabel(range.from)} – ${monthLabel(range.to)}`;
}

function inRange(dateStr: string | null, range: DateRange): boolean {
  if (!dateStr) return false;
  const mk = dateStr.slice(0, 7);
  return mk >= range.from && mk <= range.to;
}

function getPresetRange(key: PresetKey): DateRange {
  const now = new Date();
  const curMonth = monthKey(now);
  switch (key) {
    case "mtd":
      return { from: curMonth, to: curMonth };
    case "qtd": {
      const qStart = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1);
      return { from: monthKey(qStart), to: curMonth };
    }
    case "ytd":
      return { from: `${now.getFullYear()}-01`, to: curMonth };
    case "last3m": {
      const from = new Date(now.getFullYear(), now.getMonth() - 2, 1);
      return { from: monthKey(from), to: curMonth };
    }
    case "last6m": {
      const from = new Date(now.getFullYear(), now.getMonth() - 5, 1);
      return { from: monthKey(from), to: curMonth };
    }
    default:
      return { from: curMonth, to: curMonth };
  }
}

function getMonthOptions(): { value: string; label: string }[] {
  const opts: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = 0; i < 24; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const mk = monthKey(d);
    opts.push({ value: mk, label: monthLabel(mk) });
  }
  return opts;
}

function rangeMonths(range: DateRange): number {
  const [fy, fm] = range.from.split("-").map(Number);
  const [ty, tm] = range.to.split("-").map(Number);
  return (ty - fy) * 12 + (tm - fm) + 1;
}

function priorRange(range: DateRange): DateRange {
  const months = rangeMonths(range);
  const [fy, fm] = range.from.split("-").map(Number);
  const priorEnd = new Date(fy, fm - 1 - 1, 1); // month before range.from
  const priorStart = new Date(priorEnd.getFullYear(), priorEnd.getMonth() - months + 1, 1);
  return { from: monthKey(priorStart), to: monthKey(priorEnd) };
}

function computeDelta(current: number, prior: number): Delta {
  const abs = current - prior;
  const pct = prior !== 0 ? abs / prior : current !== 0 ? 1 : 0;
  return { abs, pct };
}

function deltaColor(delta: Delta, higherIsGood: boolean): "green" | "red" | "ink" {
  if (Math.abs(delta.pct) <= NOISE_THRESHOLD) return "ink";
  const isUp = delta.abs > 0;
  return (isUp === higherIsGood) ? "green" : "red";
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}

function parseEmployeeCount(emp: string | null): number | null {
  if (!emp) return null;
  const trimmed = emp.trim();
  if (!trimmed) return null;
  const direct = parseInt(trimmed, 10);
  if (!isNaN(direct) && direct > 0) return direct;
  const rangeMatch = trimmed.match(/(\d+)\s*[-–]\s*(\d+)/);
  if (rangeMatch) return Math.round((parseInt(rangeMatch[1]) + parseInt(rangeMatch[2])) / 2);
  return null;
}

function employeeBucket(count: number | null): string {
  if (count == null) return "Unknown";
  for (const b of SIZE_BUCKETS) {
    if (count >= b.min && count <= b.max) return b.label;
  }
  return "Unknown";
}

// ---- Shared styles ----

const CARD: React.CSSProperties = {
  background: "var(--card-2)", borderRadius: 12, padding: "20px 24px", marginBottom: 16,
};
const HEADING: React.CSSProperties = {
  fontSize: 14, fontWeight: 700, color: "var(--ink-1)", marginBottom: 16,
  display: "flex", alignItems: "center", gap: 8,
};
const TH: React.CSSProperties = {
  padding: "10px 12px", fontWeight: 600, color: "var(--ink-3)", fontSize: 11,
  textTransform: "uppercase", letterSpacing: ".08em", cursor: "pointer",
  userSelect: "none", borderBottom: "1px solid var(--line)", whiteSpace: "nowrap",
};
const TD: React.CSSProperties = { padding: "10px 12px", fontSize: 13 };

// ---- Sub-components ----

function DeltaChip({ delta, higherIsGood, isCurrency, isPct }: {
  delta: Delta; higherIsGood: boolean; isCurrency?: boolean; isPct?: boolean;
}) {
  const tone = deltaColor(delta, higherIsGood);
  const sign = delta.abs > 0 ? "+" : "";
  let label: string;
  if (isPct) {
    label = `${sign}${Math.round(delta.abs * 100)}pp`;
  } else if (isCurrency) {
    label = `${sign}${fmtMRR(delta.abs)} (${sign}${Math.round(delta.pct * 100)}%)`;
  } else {
    label = `${sign}${delta.abs} (${sign}${Math.round(delta.pct * 100)}%)`;
  }
  if (delta.abs === 0 && delta.pct === 0) label = "—";
  return <Chip tone={tone} style={{ fontSize: 11 }}>{label}</Chip>;
}

function HBar({ items, maxVal }: {
  items: { label: string; value: number; subLabel?: string; tone?: string }[];
  maxVal: number;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((item, i) => {
        const pct = maxVal > 0 ? Math.round((item.value / maxVal) * 100) : 0;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 12, color: "var(--ink-2)", minWidth: 140, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.label}</span>
            <div style={{ flex: 1, height: 8, background: "var(--card)", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${pct}%`, background: item.tone || "var(--indigo)", borderRadius: 4, minWidth: item.value > 0 ? 2 : 0 }} />
            </div>
            <span className="num" style={{ fontSize: 11, color: "var(--ink-3)", minWidth: 50, textAlign: "right" }}>{fmtMRR(item.value)}</span>
            {item.subLabel && <span className="num" style={{ fontSize: 11, color: "var(--ink-4)", minWidth: 30, textAlign: "right" }}>{item.subLabel}</span>}
          </div>
        );
      })}
    </div>
  );
}

// ---- Main component ----

export default function ExecSummaryView() {
  const D = useData();
  const [range, setRange] = useState<DateRange>(() => getPresetRange("mtd"));
  const [activePreset, setActivePreset] = useState<PresetKey>("mtd");
  const [dealsRaw, setDealsRaw] = useState<DealRaw[]>([]);
  const [dealsLoading, setDealsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"pae" | "pbd" | "partner" | "size">("pae");

  const monthOpts = useMemo(() => getMonthOptions(), []);

  const applyPreset = (key: PresetKey) => {
    setActivePreset(key);
    if (key !== "custom") setRange(getPresetRange(key));
  };
  const setFrom = (v: string) => {
    setActivePreset("custom");
    setRange(r => ({ from: v, to: v > r.to ? v : r.to }));
  };
  const setTo = (v: string) => {
    setActivePreset("custom");
    setRange(r => ({ from: r.from > v ? v : r.from, to: v }));
  };

  // Direct deals query for demo/hygiene/partner/cycle/size data
  useEffect(() => {
    let cancelled = false;
    setDealsLoading(true);
    (async () => {
      const PAGE = 1000;
      const all: DealRaw[] = [];
      let offset = 0;
      while (true) {
        const { data, error } = await supabase
          .from("deals")
          .select("deal_id,pae,pbd,team,partner,amount,deal_stage,close_date,createdate,after_demo_date,first_meeting_at,pipeline_name,employees")
          .range(offset, offset + PAGE - 1);
        if (error || !data) break;
        all.push(...(data as DealRaw[]));
        if (data.length < PAGE) break;
        offset += PAGE;
      }
      if (!cancelled) {
        setDealsRaw(all);
        setDealsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const prior = useMemo(() => priorRange(range), [range]);

  // ---- Core data from useData() ----
  const wonDeals = useMemo(() => D.benchmark.won.filter(d => inRange(d.closeDate, range)), [D.benchmark.won, range]);
  const lostDeals = useMemo(() => D.benchmark.lost.filter(d => inRange(d.closeDate, range)), [D.benchmark.lost, range]);
  const priorWon = useMemo(() => D.benchmark.won.filter(d => inRange(d.closeDate, prior)), [D.benchmark.won, prior]);
  const priorLost = useMemo(() => D.benchmark.lost.filter(d => inRange(d.closeDate, prior)), [D.benchmark.lost, prior]);
  const openDeals = D.forecast.allDeals;

  // ---- Deals raw lookups ----
  const dealsMap = useMemo(() => {
    const m = new Map<string, DealRaw>();
    for (const d of dealsRaw) m.set(d.deal_id, d);
    return m;
  }, [dealsRaw]);

  const demosInRange = useMemo(() => dealsRaw.filter(d => inRange(d.after_demo_date, range)), [dealsRaw, range]);
  const priorDemosInRange = useMemo(() => dealsRaw.filter(d => inRange(d.after_demo_date, prior)), [dealsRaw, prior]);

  // ---- Win Rate 6m rolling windows ----
  const winRate6m = useMemo(() => {
    const [ty, tm] = range.to.split("-").map(Number);
    const endDate = new Date(ty, tm, 0); // last day of range.to month
    const startDate = new Date(ty, tm - 6, 1);
    const window = { from: monthKey(startDate), to: monthKey(endDate) };
    const w = D.benchmark.won.filter(d => inRange(d.closeDate, window));
    const l = D.benchmark.lost.filter(d => inRange(d.closeDate, window));
    const total = w.length + l.length;
    return total > 0 ? w.length / total : null;
  }, [D.benchmark, range]);

  const priorWinRate6m = useMemo(() => {
    const [py, pm] = prior.to.split("-").map(Number);
    const startDate = new Date(py, pm - 6, 1);
    const window = { from: monthKey(startDate), to: prior.to };
    const w = D.benchmark.won.filter(d => inRange(d.closeDate, window));
    const l = D.benchmark.lost.filter(d => inRange(d.closeDate, window));
    const total = w.length + l.length;
    return total > 0 ? w.length / total : null;
  }, [D.benchmark, prior]);

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 4 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-1)", margin: 0 }}>Executive Summary</h2>
      </div>
      <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 16 }}>{rangeLabel(range)}</div>

      {/* Period selector */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 28, flexWrap: "wrap" }}>
        {PRESETS.map(p => (
          <button
            key={p.key}
            onClick={() => applyPreset(p.key)}
            style={{
              padding: "5px 14px", borderRadius: 8, border: "1px solid var(--line)",
              background: activePreset === p.key ? "var(--ink-1)" : "var(--card-2)",
              color: activePreset === p.key ? "var(--bg)" : "var(--ink-2)",
              fontSize: 12, fontWeight: 600, cursor: "pointer",
            }}
          >{p.label}</button>
        ))}
        {activePreset === "custom" && (
          <>
            <select value={range.from} onChange={e => setFrom(e.target.value)} className="cz-native-select" style={{ fontSize: 12, padding: "4px 10px" }}>
              {monthOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <span style={{ fontSize: 12, color: "var(--ink-3)" }}>to</span>
            <select value={range.to} onChange={e => setTo(e.target.value)} className="cz-native-select" style={{ fontSize: 12, padding: "4px 10px" }}>
              {monthOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </>
        )}
      </div>

      {/* Sections 1-5 are added in Tasks 3-5 */}
      <p style={{ color: "var(--ink-3)", fontSize: 13 }}>{dealsLoading ? "Loading deals data..." : `${dealsRaw.length} deals loaded.`}</p>
    </div>
  );
}
