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

function HBar({ items, maxVal, fmtValue }: {
  items: { label: string; value: number; subLabel?: string; tone?: string }[];
  maxVal: number;
  fmtValue?: (v: number) => string;
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
            <span className="num" style={{ fontSize: 11, color: "var(--ink-3)", minWidth: 50, textAlign: "right" }}>{(fmtValue || fmtMRR)(item.value)}</span>
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

  // ---- Section 1: KPI computations ----
  const kpis = useMemo(() => {
    const mrrWon = wonDeals.reduce((s, d) => s + (d.mrr || 0), 0);
    const priorMrr = priorWon.reduce((s, d) => s + (d.mrr || 0), 0);
    const logos = wonDeals.length;
    const priorLogos = priorWon.length;
    const demos = demosInRange.length;
    const priorDemos = priorDemosInRange.length;
    const demoWon = demos > 0 ? wonDeals.length / demos : null;
    const priorDemoWon = priorDemos > 0 ? priorWon.length / priorDemos : null;
    const pipeline = openDeals.reduce((s, d) => s + (d.mrr || 0), 0);
    const wonCycles = wonDeals.filter(d => d.dealAge != null && d.dealAge > 0).map(d => d.dealAge!);
    const medianCycle = wonCycles.length > 0 ? median(wonCycles) : null;
    const priorCycles = priorWon.filter(d => d.dealAge != null && d.dealAge > 0).map(d => d.dealAge!);
    const priorMedianCycle = priorCycles.length > 0 ? median(priorCycles) : null;

    // Attainment
    const targetMonths = D.forecast.targets.filter(t => t.month >= range.from && t.month <= range.to);
    const totalTarget = targetMonths.reduce((s, t) => s + t.monthly_target, 0);

    // Post-demo / pre-demo pipeline split
    let postDemoPipeline = 0, preDemoPipeline = 0;
    for (const d of openDeals) {
      const raw = d.id ? dealsMap.get(d.id) : null;
      if (raw?.after_demo_date) postDemoPipeline += d.mrr || 0;
      else preDemoPipeline += d.mrr || 0;
    }

    return {
      mrrWon, priorMrr, logos, priorLogos, demos, priorDemos,
      demoWon, priorDemoWon,
      winRate6m, priorWinRate6m,
      pipeline, postDemoPipeline, preDemoPipeline,
      medianCycle, priorMedianCycle,
      totalTarget,
    };
  }, [wonDeals, priorWon, lostDeals, demosInRange, priorDemosInRange, openDeals, dealsMap, D.forecast.targets, range, winRate6m, priorWinRate6m]);

  // ---- Section 2: Team Scorecard ----
  type TeamSortCol = "team" | "mrrWon" | "demos" | "demoWon" | "logos" | "pipeline" | "winRate" | "avgDealSize" | "avgCycle" | "hygiene";
  const [teamSortCol, setTeamSortCol] = useState<TeamSortCol>("mrrWon");
  const [teamSortDir, setTeamSortDir] = useState<SortDir>("desc");

  const teamRows = useMemo(() => {
    const teams = ACTIVE_TEAMS as unknown as string[];
    const rows = teams.map(team => {
      const teamEmails = expandTeam(team);
      const tw = wonDeals.filter(d => teamEmails.has(d.team));
      const tl = lostDeals.filter(d => teamEmails.has(d.team));
      const to = openDeals.filter(d => teamEmails.has(d.team || ""));
      const totalClosed = tw.length + tl.length;
      const teamDemos = demosInRange.filter(d => teamEmails.has(d.team || ""));
      const mrrWon = tw.reduce((s, d) => s + (d.mrr || 0), 0);
      const logos = tw.length;

      // Win rate — 6m rolling per team
      const [ty, tm] = range.to.split("-").map(Number);
      const w6start = new Date(ty, tm - 6, 1);
      const w6 = { from: monthKey(w6start), to: range.to };
      const tw6 = D.benchmark.won.filter(d => teamEmails.has(d.team) && inRange(d.closeDate, w6));
      const tl6 = D.benchmark.lost.filter(d => teamEmails.has(d.team) && inRange(d.closeDate, w6));
      const t6total = tw6.length + tl6.length;
      const winRate = t6total > 0 ? tw6.length / t6total : null;

      // Cycle
      const cycles = tw.filter(d => d.dealAge != null && d.dealAge > 0).map(d => d.dealAge!);
      const avgCycle = cycles.length > 0 ? median(cycles) : null;

      // Hygiene: stale + missing first meeting + to reschedule
      const stale = to.filter(d => (d as any).stale).length;
      const toReschedule = to.filter(d => {
        const s = (d.stage || "").toLowerCase();
        return s.includes("reschedul") || s === "to reschedule";
      }).length;
      const missingFirstMeeting = dealsRaw.filter(d => {
        if (!teamEmails.has(d.team || "")) return false;
        const stage = (d.deal_stage || "").toLowerCase();
        if (CLOSED_STAGES.has(stage)) return false;
        if (stage === "prospecting" || stage === "new" || stage === "") return false;
        return !d.first_meeting_at;
      }).length;
      const hygiene = stale + toReschedule + missingFirstMeeting;

      return {
        team, mrrWon, demos: teamDemos.length,
        demoWon: teamDemos.length > 0 ? logos / teamDemos.length : null,
        logos, pipeline: to.reduce((s, d) => s + (d.mrr || 0), 0),
        winRate, avgDealSize: logos > 0 ? mrrWon / logos : null,
        avgCycle, hygiene,
      };
    }).filter(r => r.mrrWon > 0 || r.pipeline > 0 || r.logos > 0 || r.demos > 0);

    return rows;
  }, [wonDeals, lostDeals, openDeals, demosInRange, dealsRaw, D.benchmark, range]);

  // TOTAL row
  const totalRow = useMemo(() => {
    const mrrWon = teamRows.reduce((s, r) => s + r.mrrWon, 0);
    const demos = teamRows.reduce((s, r) => s + r.demos, 0);
    const logos = teamRows.reduce((s, r) => s + r.logos, 0);
    const pipeline = teamRows.reduce((s, r) => s + r.pipeline, 0);
    const hygiene = teamRows.reduce((s, r) => s + r.hygiene, 0);
    const demoWon = demos > 0 ? logos / demos : null;
    const avgDealSize = logos > 0 ? mrrWon / logos : null;
    const allCycles = wonDeals.filter(d => d.dealAge != null && d.dealAge > 0).map(d => d.dealAge!);
    const avgCycle = allCycles.length > 0 ? median(allCycles) : null;
    return { team: "TOTAL", mrrWon, demos, demoWon, logos, pipeline, winRate: kpis.winRate6m, avgDealSize, avgCycle, hygiene };
  }, [teamRows, wonDeals, kpis.winRate6m]);

  // Rank badges for MRR Won
  const mrrRanks = useMemo(() => {
    const sorted = [...teamRows].sort((a, b) => b.mrrWon - a.mrrWon);
    const ranks = new Map<string, number>();
    sorted.forEach((r, i) => ranks.set(r.team, i + 1));
    return ranks;
  }, [teamRows]);

  // Conditional formatting thresholds
  const teamAvgWinRate = useMemo(() => {
    const rates = teamRows.filter(r => r.winRate != null).map(r => r.winRate!);
    if (rates.length === 0) return null;
    const avg = rates.reduce((s, v) => s + v, 0) / rates.length;
    const variance = rates.reduce((s, v) => s + (v - avg) ** 2, 0) / rates.length;
    return { avg, stdDev: Math.sqrt(variance) };
  }, [teamRows]);

  const medianTeamCycle = useMemo(() => {
    const cycles = teamRows.filter(r => r.avgCycle != null).map(r => r.avgCycle!);
    return cycles.length > 0 ? median(cycles) : null;
  }, [teamRows]);

  const sortedTeams = useMemo(() => {
    const rows = [...teamRows];
    rows.sort((a, b) => {
      const av = a[teamSortCol] ?? -Infinity;
      const bv = b[teamSortCol] ?? -Infinity;
      if (typeof av === "string" && typeof bv === "string")
        return teamSortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return teamSortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return rows;
  }, [teamRows, teamSortCol, teamSortDir]);

  const toggleTeamSort = (col: TeamSortCol) => {
    if (teamSortCol === col) setTeamSortDir(d => d === "asc" ? "desc" : "asc");
    else { setTeamSortCol(col); setTeamSortDir("desc"); }
  };

  function winRateColor(rate: number | null): string {
    if (rate == null || !teamAvgWinRate) return "var(--ink-4)";
    if (rate >= teamAvgWinRate.avg) return "var(--green-ink)";
    if (rate >= teamAvgWinRate.avg - teamAvgWinRate.stdDev) return "var(--amber-ink)";
    return "var(--red-ink)";
  }

  function cycleColor(cycle: number | null): string {
    if (cycle == null || medianTeamCycle == null) return "var(--ink-4)";
    if (cycle <= medianTeamCycle) return "var(--green-ink)";
    if (cycle >= medianTeamCycle * 1.5) return "var(--red-ink)";
    return "var(--ink-2)";
  }

  function hygieneColor(count: number): string {
    if (count > 5) return "var(--red-ink)";
    if (count > 0) return "var(--amber-ink)";
    return "var(--ink-4)";
  }

  // ---- Section 3: Pipeline Health ----
  const coverageRatio = useMemo(() => {
    const remaining = kpis.totalTarget > 0 ? kpis.totalTarget - kpis.mrrWon : 0;
    if (remaining <= 0 && kpis.totalTarget > 0) return Infinity; // already hit target
    if (kpis.totalTarget === 0) return null;
    return kpis.pipeline / remaining;
  }, [kpis]);

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
      .sort((a, b) => b.mrr - a.mrr)
      .slice(0, 6);
  }, [openDeals]);

  const hygieneAlerts = useMemo(() => {
    const stale = openDeals.filter(d => (d as any).stale).length;
    const toReschedule = openDeals.filter(d => {
      const s = (d.stage || "").toLowerCase();
      return s.includes("reschedul") || s === "to reschedule";
    }).length;
    const missingFirstMeeting = dealsRaw.filter(d => {
      const stage = (d.deal_stage || "").toLowerCase();
      if (CLOSED_STAGES.has(stage)) return false;
      if (stage === "prospecting" || stage === "new" || stage === "") return false;
      return !d.first_meeting_at;
    }).length;
    return { stale, toReschedule, missingFirstMeeting };
  }, [openDeals, dealsRaw]);

  // ---- Section 4: Monthly Trends (trailing 6 months) ----
  const monthlyTrends = useMemo(() => {
    const now = new Date();
    const months: string[] = [];
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      months.push(monthKey(d));
    }
    const curMonth = monthKey(now);

    const mrrByMonth = months.map(m => {
      const mrr = D.benchmark.won
        .filter(d => d.closeDate && d.closeDate.slice(0, 7) === m)
        .reduce((s, d) => s + (d.mrr || 0), 0);
      return { month: m, value: mrr, isCurrent: m === curMonth };
    });

    const demosByMonth = months.map(m => {
      const count = dealsRaw.filter(d => d.after_demo_date && d.after_demo_date.slice(0, 7) === m).length;
      return { month: m, value: count, isCurrent: m === curMonth };
    });

    return { months, mrrByMonth, demosByMonth };
  }, [D.benchmark.won, dealsRaw]);

  // ---- Section 4: Loss Reasons ----
  const lossReasons = useMemo(() => {
    const reasons = new Map<string, { count: number; mrr: number }>();
    for (const d of lostDeals) {
      const r = d.lostReason || "Unknown";
      const cur = reasons.get(r) || { count: 0, mrr: 0 };
      cur.count += 1;
      cur.mrr += d.mrr || 0;
      reasons.set(r, cur);
    }
    const sorted = [...reasons.entries()]
      .map(([reason, v]) => ({ reason, ...v }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);

    const unknownCount = reasons.get("Unknown")?.count || 0;
    const unknownPct = lostDeals.length > 0 ? unknownCount / lostDeals.length : 0;

    return { reasons: sorted, unknownPct, totalLost: lostDeals.length };
  }, [lostDeals]);

  // ---- Section 5: Drill-down tab data ----

  // By PAE
  type PaeRow = { pae: string; mrrWon: number; demos: number; demoWon: number | null; logos: number; arpu: number | null; avgCycle: number | null };
  const paeRows = useMemo(() => {
    const byPae = new Map<string, { won: BenchmarkDeal[]; demos: number }>();
    for (const d of wonDeals) {
      const pae = (d.owner && d.owner !== "—") ? d.owner : "Unknown";
      const cur = byPae.get(pae) || { won: [], demos: 0 };
      cur.won.push(d);
      byPae.set(pae, cur);
    }
    for (const d of demosInRange) {
      const pae = d.pae || "Unknown";
      const cur = byPae.get(pae) || { won: [], demos: 0 };
      cur.demos += 1;
      byPae.set(pae, cur);
    }
    return [...byPae.entries()].map(([pae, v]) => {
      const mrrWon = v.won.reduce((s, d) => s + (d.mrr || 0), 0);
      const logos = v.won.length;
      const cycles = v.won.filter(d => d.dealAge != null && d.dealAge > 0).map(d => d.dealAge!);
      return {
        pae,
        mrrWon,
        demos: v.demos,
        demoWon: v.demos > 0 ? logos / v.demos : null,
        logos,
        arpu: logos > 0 ? mrrWon / logos : null,
        avgCycle: cycles.length > 0 ? median(cycles) : null,
      };
    }).sort((a, b) => b.mrrWon - a.mrrWon);
  }, [wonDeals, demosInRange]);

  type PaeSortCol = "pae" | "mrrWon" | "demos" | "demoWon" | "logos" | "arpu" | "avgCycle";
  const [paeSortCol, setPaeSortCol] = useState<PaeSortCol>("mrrWon");
  const [paeSortDir, setPaeSortDir] = useState<SortDir>("desc");
  const togglePaeSort = (col: PaeSortCol) => {
    if (paeSortCol === col) setPaeSortDir(d => d === "asc" ? "desc" : "asc");
    else { setPaeSortCol(col); setPaeSortDir("desc"); }
  };
  const sortedPaeRows = useMemo(() => {
    const rows = [...paeRows];
    rows.sort((a, b) => {
      const av = a[paeSortCol] ?? -Infinity;
      const bv = b[paeSortCol] ?? -Infinity;
      if (typeof av === "string" && typeof bv === "string")
        return paeSortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return paeSortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return rows;
  }, [paeRows, paeSortCol, paeSortDir]);

  // By PBD
  type PbdRow = { pbd: string; demos: number; pipeline: number };
  const pbdRows = useMemo(() => {
    const byPbd = new Map<string, { demos: number; pipeline: number }>();
    for (const d of demosInRange) {
      const pbd = d.pbd || "Unknown";
      const cur = byPbd.get(pbd) || { demos: 0, pipeline: 0 };
      cur.demos += 1;
      byPbd.set(pbd, cur);
    }
    for (const d of openDeals) {
      const raw = d.id ? dealsMap.get(d.id) : null;
      const pbd = raw?.pbd || "Unknown";
      const cur = byPbd.get(pbd) || { demos: 0, pipeline: 0 };
      cur.pipeline += d.mrr || 0;
      byPbd.set(pbd, cur);
    }
    return [...byPbd.entries()]
      .map(([pbd, v]) => ({ pbd, ...v }))
      .sort((a, b) => b.demos - a.demos);
  }, [demosInRange, openDeals, dealsMap]);

  type PbdSortCol = "pbd" | "demos" | "pipeline";
  const [pbdSortCol, setPbdSortCol] = useState<PbdSortCol>("demos");
  const [pbdSortDir, setPbdSortDir] = useState<SortDir>("desc");
  const togglePbdSort = (col: PbdSortCol) => {
    if (pbdSortCol === col) setPbdSortDir(d => d === "asc" ? "desc" : "asc");
    else { setPbdSortCol(col); setPbdSortDir("desc"); }
  };
  const sortedPbdRows = useMemo(() => {
    const rows = [...pbdRows];
    rows.sort((a, b) => {
      const av = a[pbdSortCol] ?? -Infinity;
      const bv = b[pbdSortCol] ?? -Infinity;
      if (typeof av === "string" && typeof bv === "string")
        return pbdSortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return pbdSortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return rows;
  }, [pbdRows, pbdSortCol, pbdSortDir]);

  // By Partner
  type PartnerRow = { partner: string; mrrWon: number; wonDeals: number; pipeline: number; avgDealSize: number | null; avgCycle: number | null };
  const partnerRows = useMemo(() => {
    const byPartner = new Map<string, { wonMrr: number; wonCount: number; pipeline: number; cycles: number[] }>();
    for (const d of dealsRaw) {
      const p = (d.partner || "").trim();
      if (!p) continue;
      const stage = (d.deal_stage || "").toLowerCase().trim();
      const amt = d.amount || 0;
      if (!byPartner.has(p)) byPartner.set(p, { wonMrr: 0, wonCount: 0, pipeline: 0, cycles: [] });
      const row = byPartner.get(p)!;
      if (WON_STAGES.has(stage) && inRange(d.close_date, range)) {
        row.wonMrr += amt;
        row.wonCount += 1;
        if (d.createdate && d.close_date) {
          const days = Math.round((new Date(d.close_date).getTime() - new Date(d.createdate).getTime()) / 86400000);
          if (days > 0) row.cycles.push(days);
        }
      }
      if (!CLOSED_STAGES.has(stage)) {
        row.pipeline += amt;
      }
    }
    return [...byPartner.entries()]
      .map(([partner, v]) => ({
        partner,
        mrrWon: v.wonMrr,
        wonDeals: v.wonCount,
        pipeline: v.pipeline,
        avgDealSize: v.wonCount > 0 ? v.wonMrr / v.wonCount : null,
        avgCycle: v.cycles.length > 0 ? median(v.cycles) : null,
      }))
      .filter(r => r.mrrWon > 0 || r.pipeline > 0)
      .sort((a, b) => b.mrrWon - a.mrrWon);
  }, [dealsRaw, range]);

  type PartnerSortCol = "partner" | "mrrWon" | "wonDeals" | "pipeline" | "avgDealSize" | "avgCycle";
  const [partnerSortCol, setPartnerSortCol] = useState<PartnerSortCol>("mrrWon");
  const [partnerSortDir, setPartnerSortDir] = useState<SortDir>("desc");
  const togglePartnerSort = (col: PartnerSortCol) => {
    if (partnerSortCol === col) setPartnerSortDir(d => d === "asc" ? "desc" : "asc");
    else { setPartnerSortCol(col); setPartnerSortDir("desc"); }
  };
  const sortedPartnerRows = useMemo(() => {
    const rows = [...partnerRows];
    rows.sort((a, b) => {
      const av = a[partnerSortCol] ?? -Infinity;
      const bv = b[partnerSortCol] ?? -Infinity;
      if (typeof av === "string" && typeof bv === "string")
        return partnerSortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return partnerSortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return rows;
  }, [partnerRows, partnerSortCol, partnerSortDir]);

  // By Size
  type SizeRow = { bucket: string; dealCount: number; mrrWon: number; winRate: number | null; avgDealSize: number | null };
  const sizeRows = useMemo(() => {
    const allBenchmark = [...wonDeals, ...lostDeals];
    const byBucket = new Map<string, { won: number; lost: number; mrrWon: number }>();
    for (const d of allBenchmark) {
      const count = parseEmployeeCount(d.employees);
      const bucket = employeeBucket(count);
      const cur = byBucket.get(bucket) || { won: 0, lost: 0, mrrWon: 0 };
      if (d.outcome === "won") {
        cur.won += 1;
        cur.mrrWon += d.mrr || 0;
      } else {
        cur.lost += 1;
      }
      byBucket.set(bucket, cur);
    }
    return [...byBucket.entries()]
      .map(([bucket, v]) => {
        const total = v.won + v.lost;
        return {
          bucket,
          dealCount: total,
          mrrWon: v.mrrWon,
          winRate: total > 0 ? v.won / total : null,
          avgDealSize: v.won > 0 ? v.mrrWon / v.won : null,
        };
      })
      .sort((a, b) => b.mrrWon - a.mrrWon);
  }, [wonDeals, lostDeals]);

  type SizeSortCol = "bucket" | "dealCount" | "mrrWon" | "winRate" | "avgDealSize";
  const [sizeSortCol, setSizeSortCol] = useState<SizeSortCol>("mrrWon");
  const [sizeSortDir, setSizeSortDir] = useState<SortDir>("desc");
  const toggleSizeSort = (col: SizeSortCol) => {
    if (sizeSortCol === col) setSizeSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSizeSortCol(col); setSizeSortDir("desc"); }
  };
  const sortedSizeRows = useMemo(() => {
    const rows = [...sizeRows];
    rows.sort((a, b) => {
      const av = a[sizeSortCol] ?? -Infinity;
      const bv = b[sizeSortCol] ?? -Infinity;
      if (typeof av === "string" && typeof bv === "string")
        return sizeSortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return sizeSortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return rows;
  }, [sizeRows, sizeSortCol, sizeSortDir]);

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

      {/* Section 1: Headline KPI Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(145px, 1fr))", gap: 12, marginBottom: 24 }}>
        {/* MRR Won */}
        <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 18px" }}>
          <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>MRR Won</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--ink-1)" }} className="num">{fmtMRR(kpis.mrrWon)}</div>
          {kpis.totalTarget > 0 && (
            <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>
              {fmtMRR(kpis.mrrWon)} / {fmtMRR(kpis.totalTarget)} ({Math.round((kpis.mrrWon / kpis.totalTarget) * 100)}%)
            </div>
          )}
          <div style={{ marginTop: 6 }}>
            <DeltaChip delta={computeDelta(kpis.mrrWon, kpis.priorMrr)} higherIsGood isCurrency />
          </div>
        </div>

        {/* Logos Won */}
        <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 18px" }}>
          <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>Logos Won</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--ink-1)" }} className="num">{kpis.logos}</div>
          <div style={{ marginTop: 6 }}>
            <DeltaChip delta={computeDelta(kpis.logos, kpis.priorLogos)} higherIsGood />
          </div>
        </div>

        {/* Demos Held */}
        <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 18px" }}>
          <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>Demos Held</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--ink-1)" }} className="num">{kpis.demos}</div>
          <div style={{ marginTop: 6 }}>
            <DeltaChip delta={computeDelta(kpis.demos, kpis.priorDemos)} higherIsGood />
          </div>
        </div>

        {/* Demo → Won */}
        <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 18px" }}>
          <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>{"Demo → Won"}</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--ink-1)" }} className="num">
            {kpis.demoWon != null ? `${Math.round(kpis.demoWon * 100)}%` : "—"}
          </div>
          <div style={{ marginTop: 6 }}>
            {kpis.demoWon != null && kpis.priorDemoWon != null
              ? <DeltaChip delta={computeDelta(kpis.demoWon, kpis.priorDemoWon)} higherIsGood isPct />
              : <span style={{ fontSize: 11, color: "var(--ink-4)" }}>{"—"}</span>}
          </div>
        </div>

        {/* Win Rate (6m) */}
        <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 18px" }}>
          <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>Win Rate (6m)</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--ink-1)" }} className="num">
            {kpis.winRate6m != null ? `${Math.round(kpis.winRate6m * 100)}%` : "—"}
          </div>
          <div style={{ marginTop: 6 }}>
            {kpis.winRate6m != null && kpis.priorWinRate6m != null
              ? <DeltaChip delta={computeDelta(kpis.winRate6m, kpis.priorWinRate6m)} higherIsGood isPct />
              : <span style={{ fontSize: 11, color: "var(--ink-4)" }}>{"—"}</span>}
          </div>
        </div>

        {/* Open Pipeline */}
        <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 18px" }}>
          <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>Open Pipeline</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--ink-1)" }} className="num">{fmtMRR(kpis.pipeline)}</div>
          <div style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 4 }}>
            {fmtMRR(kpis.postDemoPipeline)} post-demo {"·"} {fmtMRR(kpis.preDemoPipeline)} pre-demo
          </div>
        </div>

        {/* Avg Sales Cycle */}
        <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 18px" }}>
          <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>Avg Cycle</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--ink-1)" }} className="num">
            {kpis.medianCycle != null ? `${kpis.medianCycle}d` : "—"}
          </div>
          <div style={{ marginTop: 6 }}>
            {kpis.medianCycle != null && kpis.priorMedianCycle != null
              ? <DeltaChip delta={computeDelta(kpis.medianCycle, kpis.priorMedianCycle)} higherIsGood={false} />
              : <span style={{ fontSize: 11, color: "var(--ink-4)" }}>{"—"}</span>}
          </div>
        </div>
      </div>

      {/* Section 2: Team Performance Scorecard */}
      <section style={{ ...CARD, marginTop: 8 }}>
        <div style={HEADING}>
          <Icon name="users" size={18} />
          Team Performance
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: "var(--ink-4)", fontWeight: 400 }}>{rangeLabel(range)}</span>
        </div>
        {sortedTeams.length === 0 ? (
          <p style={{ color: "var(--ink-3)", fontSize: 13 }}>No team data for this period.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {([
                    ["team", "Team", "left"],
                    ["mrrWon", "MRR Won", "right"],
                    ["demos", "Demos", "right"],
                    ["demoWon", "Demo→Won", "right"],
                    ["logos", "Logos", "right"],
                    ["pipeline", "Pipeline", "right"],
                    ["winRate", "Win Rate (6m)", "right"],
                    ["avgDealSize", "Avg Deal", "right"],
                    ["avgCycle", "Avg Cycle", "right"],
                    ["hygiene", "Hygiene", "right"],
                  ] as [TeamSortCol, string, string][]).map(([key, label, align]) => (
                    <th key={key} onClick={() => toggleTeamSort(key)} style={{ ...TH, textAlign: align as any }}>
                      {label}
                      {teamSortCol === key && <span style={{ marginLeft: 4, fontSize: 9 }}>{teamSortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* TOTAL row pinned at top */}
                <tr style={{ background: "var(--card)", fontWeight: 600 }}>
                  <td style={{ ...TD, fontWeight: 700, color: "var(--ink-1)" }}>TOTAL / AVG</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(totalRow.mrrWon)}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{totalRow.demos}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{totalRow.demoWon != null ? `${Math.round(totalRow.demoWon * 100)}%` : "—"}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{totalRow.logos}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(totalRow.pipeline)}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{totalRow.winRate != null ? `${Math.round(totalRow.winRate * 100)}%` : "—"}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{totalRow.avgDealSize != null ? fmtMRR(totalRow.avgDealSize) : "—"}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{totalRow.avgCycle != null ? `${totalRow.avgCycle}d` : "—"}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{totalRow.hygiene}</td>
                </tr>
                {sortedTeams.map(r => (
                  <tr key={r.team}>
                    <td style={{ ...TD, fontWeight: 500, color: "var(--ink-1)" }}>{r.team}</td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600 }} className="num">
                      {fmtMRR(r.mrrWon)}
                      {mrrRanks.get(r.team) != null && (
                        <span style={{ marginLeft: 6, fontSize: 10, color: "var(--ink-4)", fontWeight: 400 }}>#{mrrRanks.get(r.team)}</span>
                      )}
                    </td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.demos}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.demoWon != null ? `${Math.round(r.demoWon * 100)}%` : "—"}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.logos}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(r.pipeline)}</td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600, color: winRateColor(r.winRate) }} className="num">
                      {r.winRate != null ? `${Math.round(r.winRate * 100)}%` : "—"}
                    </td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.avgDealSize != null ? fmtMRR(r.avgDealSize) : "—"}</td>
                    <td style={{ ...TD, textAlign: "right", color: cycleColor(r.avgCycle) }} className="num">
                      {r.avgCycle != null ? `${r.avgCycle}d` : "—"}
                    </td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600, color: hygieneColor(r.hygiene) }} className="num">{r.hygiene}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Section 3: Pipeline Health Strip */}
      <section style={CARD}>
        <div style={HEADING}>
          <Icon name="layers" size={18} />
          Pipeline Health
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* 3a. Coverage Ratio */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 8 }}>Coverage Ratio</div>
            {coverageRatio == null ? (
              <div>
                <span style={{ fontSize: 28, fontWeight: 800, color: "var(--ink-1)" }} className="num">{fmtMRR(kpis.pipeline)}</span>
                <div style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 4 }}>No target set</div>
              </div>
            ) : coverageRatio === Infinity ? (
              <div>
                <span style={{ fontSize: 28, fontWeight: 800, color: "var(--green-ink)" }} className="num">{"Target hit ✓"}</span>
              </div>
            ) : (
              <div>
                <span style={{
                  fontSize: 28, fontWeight: 800,
                  color: coverageRatio >= 3 ? "var(--green-ink)" : coverageRatio >= 2 ? "var(--amber-ink)" : "var(--red-ink)",
                }} className="num">{coverageRatio.toFixed(1)}{"×"}</span>
                <div style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 4 }}>
                  {fmtMRR(kpis.pipeline)} pipeline {"÷"} {fmtMRR(kpis.totalTarget - kpis.mrrWon)} remaining
                </div>
              </div>
            )}
          </div>

          {/* 3b. Pre/Post Demo Pipeline */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 8 }}>Pipeline by Demo Status</div>
            {(() => {
              const total = kpis.postDemoPipeline + kpis.preDemoPipeline;
              const postPct = total > 0 ? Math.round((kpis.postDemoPipeline / total) * 100) : 0;
              return (
                <>
                  <div style={{ height: 16, borderRadius: 8, overflow: "hidden", display: "flex", background: "var(--card)" }}>
                    <div style={{ width: `${postPct}%`, background: "var(--indigo)", minWidth: kpis.postDemoPipeline > 0 ? 4 : 0 }} />
                    <div style={{ flex: 1, background: "var(--indigo)", opacity: 0.3 }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--ink-3)", marginTop: 6 }}>
                    <span>{fmtMRR(kpis.postDemoPipeline)} post-demo</span>
                    <span>{fmtMRR(kpis.preDemoPipeline)} pre-demo</span>
                  </div>
                </>
              );
            })()}
          </div>

          {/* 3c. Stage Distribution */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 8 }}>Stage Distribution</div>
            {stageDistribution.length === 0 ? (
              <p style={{ color: "var(--ink-4)", fontSize: 12 }}>No open deals.</p>
            ) : (
              <HBar
                items={stageDistribution.map(s => ({
                  label: s.stage,
                  value: s.mrr,
                  subLabel: String(s.count),
                }))}
                maxVal={stageDistribution[0]?.mrr || 1}
              />
            )}
          </div>

          {/* 3d. Hygiene Alerts */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 8 }}>Hygiene Alerts</div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {[
                { label: "stale deals", count: hygieneAlerts.stale },
                { label: "missing 1st meeting", count: hygieneAlerts.missingFirstMeeting },
                { label: "to reschedule", count: hygieneAlerts.toReschedule },
              ].map(h => (
                <Chip
                  key={h.label}
                  tone={h.count > 5 ? "red" : h.count > 0 ? "amber" : "ink"}
                  style={{ fontSize: 12 }}
                >
                  {h.count} {h.label}
                </Chip>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Section 4: Funnel & Loss */}
      <section style={CARD}>
        <div style={HEADING}>
          <Icon name="trendUp" size={18} />
          Trends & Loss Analysis
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* 4a. Monthly Trends */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 10 }}>MRR Won by Month</div>
            <div style={{ fontSize: 10, color: "var(--ink-4)", marginBottom: 8 }}>Last 6 months</div>
            {(() => {
              const maxMrr = Math.max(...monthlyTrends.mrrByMonth.map(m => m.value), 1);
              return (
                <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 80 }}>
                  {monthlyTrends.mrrByMonth.map(m => {
                    const h = maxMrr > 0 ? Math.round((m.value / maxMrr) * 70) : 0;
                    return (
                      <div key={m.month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <span className="num" style={{ fontSize: 9, color: "var(--ink-3)", marginBottom: 2 }}>{fmtMRR(m.value)}</span>
                        <div style={{
                          width: "100%", height: h, borderRadius: 3,
                          background: "var(--indigo)", opacity: m.isCurrent ? 0.5 : 1,
                        }} />
                        <span style={{ fontSize: 9, color: "var(--ink-4)", marginTop: 3 }}>{monthLabel(m.month).slice(0, 3)}</span>
                      </div>
                    );
                  })}
                </div>
              );
            })()}

            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 10, marginTop: 20 }}>Demos by Month</div>
            {(() => {
              const maxDemos = Math.max(...monthlyTrends.demosByMonth.map(m => m.value), 1);
              return (
                <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 80 }}>
                  {monthlyTrends.demosByMonth.map(m => {
                    const h = maxDemos > 0 ? Math.round((m.value / maxDemos) * 70) : 0;
                    return (
                      <div key={m.month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <span className="num" style={{ fontSize: 9, color: "var(--ink-3)", marginBottom: 2 }}>{m.value}</span>
                        <div style={{
                          width: "100%", height: h, borderRadius: 3,
                          background: "var(--green)", opacity: m.isCurrent ? 0.5 : 1,
                        }} />
                        <span style={{ fontSize: 9, color: "var(--ink-4)", marginTop: 3 }}>{monthLabel(m.month).slice(0, 3)}</span>
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </div>

          {/* 4b. Loss Reasons */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 4 }}>Loss Reasons</div>
            <div style={{ fontSize: 11, color: "var(--ink-4)", marginBottom: 10 }}>{lossReasons.totalLost} lost in {rangeLabel(range)}</div>
            {lossReasons.reasons.length === 0 ? (
              <p style={{ color: "var(--ink-3)", fontSize: 13 }}>No lost deals in this period.</p>
            ) : (
              <>
                <HBar
                  items={lossReasons.reasons.map(r => ({
                    label: r.reason,
                    value: r.count,
                    subLabel: fmtMRR(r.mrr),
                    tone: "var(--red)",
                  }))}
                  maxVal={lossReasons.reasons[0]?.count || 1}
                  fmtValue={v => String(v)}
                />
                {lossReasons.unknownPct > 0.5 && (
                  <div style={{
                    marginTop: 12, padding: "8px 12px", borderRadius: 8,
                    background: "var(--amber-tint)", fontSize: 12, color: "var(--amber-ink)",
                  }}>
                    {Math.round(lossReasons.unknownPct * 100)}% of losses have no reason recorded.
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </section>

      {/* Section 5: Drill-down Tabs */}
      <section style={CARD}>
        <div style={{ display: "flex", gap: 0, borderBottom: "1px solid var(--line)", marginBottom: 16 }}>
          {([
            ["pae", "By PAE"],
            ["pbd", "By PBD"],
            ["partner", "By Partner"],
            ["size", "By Size"],
          ] as [typeof activeTab, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              style={{
                padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer",
                border: "none", background: "none",
                color: activeTab === key ? "var(--ink-1)" : "var(--ink-3)",
                borderBottom: activeTab === key ? "2px solid var(--indigo)" : "2px solid transparent",
              }}
            >
              {label}
              {(key === "partner" || key === "size") && (
                <span style={{ marginLeft: 6, fontSize: 10, color: "var(--ink-4)" }}>{"≈"}</span>
              )}
            </button>
          ))}
        </div>

        {/* PAE Tab */}
        {activeTab === "pae" && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {([
                    ["pae", "PAE", "left"],
                    ["mrrWon", "MRR Won", "right"],
                    ["demos", "Demos", "right"],
                    ["demoWon", "Demo→Won", "right"],
                    ["logos", "Logos", "right"],
                    ["arpu", "ARPU", "right"],
                    ["avgCycle", "Avg Cycle", "right"],
                  ] as [PaeSortCol, string, string][]).map(([key, label, align]) => (
                    <th key={key} onClick={() => togglePaeSort(key)} style={{ ...TH, textAlign: align as any }}>
                      {label}
                      {paeSortCol === key && <span style={{ marginLeft: 4, fontSize: 9 }}>{paeSortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* TOTAL row */}
                {(() => {
                  const totMrr = paeRows.reduce((s, r) => s + r.mrrWon, 0);
                  const totDemos = paeRows.reduce((s, r) => s + r.demos, 0);
                  const totLogos = paeRows.reduce((s, r) => s + r.logos, 0);
                  return (
                    <tr style={{ background: "var(--card)", fontWeight: 600 }}>
                      <td style={{ ...TD, fontWeight: 700 }}>TOTAL / AVG</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(totMrr)}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totDemos}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totDemos > 0 ? `${Math.round((totLogos / totDemos) * 100)}%` : "—"}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totLogos}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totLogos > 0 ? fmtMRR(totMrr / totLogos) : "—"}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{kpis.medianCycle != null ? `${kpis.medianCycle}d` : "—"}</td>
                    </tr>
                  );
                })()}
                {sortedPaeRows.map(r => (
                  <tr key={r.pae}>
                    <td style={{ ...TD, fontWeight: 500, color: "var(--ink-1)" }}>{ownerDisplayName(r.pae)}</td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600 }} className="num">{fmtMRR(r.mrrWon)}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.demos}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.demoWon != null ? `${Math.round(r.demoWon * 100)}%` : "—"}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.logos}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.arpu != null ? fmtMRR(r.arpu) : "—"}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.avgCycle != null ? `${r.avgCycle}d` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* PBD Tab */}
        {activeTab === "pbd" && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {([
                    ["pbd", "PBD", "left"],
                    ["demos", "Demos Attributed", "right"],
                    ["pipeline", "Pipeline Generated", "right"],
                  ] as [PbdSortCol, string, string][]).map(([key, label, align]) => (
                    <th key={key} onClick={() => togglePbdSort(key)} style={{ ...TH, textAlign: align as any }}>
                      {label}
                      {pbdSortCol === key && <span style={{ marginLeft: 4, fontSize: 9 }}>{pbdSortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr style={{ background: "var(--card)", fontWeight: 600 }}>
                  <td style={{ ...TD, fontWeight: 700 }}>TOTAL</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{pbdRows.reduce((s, r) => s + r.demos, 0)}</td>
                  <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(pbdRows.reduce((s, r) => s + r.pipeline, 0))}</td>
                </tr>
                {sortedPbdRows.map(r => (
                  <tr key={r.pbd}>
                    <td style={{ ...TD, fontWeight: 500, color: "var(--ink-1)" }}>{ownerDisplayName(r.pbd)}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.demos}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(r.pipeline)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Partner Tab */}
        {activeTab === "partner" && (
          <div style={{ overflowX: "auto" }}>
            <div style={{ marginBottom: 10 }}>
              <Chip tone="amber" style={{ fontSize: 11 }}>{"≈ pending #29"}</Chip>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {([
                    ["partner", "Partner", "left"],
                    ["mrrWon", "MRR Won", "right"],
                    ["wonDeals", "Won Deals", "right"],
                    ["pipeline", "Open Pipeline", "right"],
                    ["avgDealSize", "Avg Deal Size", "right"],
                    ["avgCycle", "Avg Cycle", "right"],
                  ] as [PartnerSortCol, string, string][]).map(([key, label, align]) => (
                    <th key={key} onClick={() => togglePartnerSort(key)} style={{ ...TH, textAlign: align as any }}>
                      {label}
                      {partnerSortCol === key && <span style={{ marginLeft: 4, fontSize: 9 }}>{partnerSortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const totMrr = partnerRows.reduce((s, r) => s + r.mrrWon, 0);
                  const totDeals = partnerRows.reduce((s, r) => s + r.wonDeals, 0);
                  const totPipeline = partnerRows.reduce((s, r) => s + r.pipeline, 0);
                  return (
                    <tr style={{ background: "var(--card)", fontWeight: 600 }}>
                      <td style={{ ...TD, fontWeight: 700 }}>TOTAL</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(totMrr)}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totDeals}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(totPipeline)}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totDeals > 0 ? fmtMRR(totMrr / totDeals) : "—"}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{"—"}</td>
                    </tr>
                  );
                })()}
                {sortedPartnerRows.map(r => (
                  <tr key={r.partner}>
                    <td style={{ ...TD, fontWeight: 500, color: "var(--ink-1)" }}>{r.partner}</td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600 }} className="num">{fmtMRR(r.mrrWon)}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.wonDeals}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(r.pipeline)}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.avgDealSize != null ? fmtMRR(r.avgDealSize) : "—"}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.avgCycle != null ? `${r.avgCycle}d` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Size Tab */}
        {activeTab === "size" && (
          <div style={{ overflowX: "auto" }}>
            <div style={{ marginBottom: 10 }}>
              <Chip tone="amber" style={{ fontSize: 11 }}>{"≈ pending #29"}</Chip>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {([
                    ["bucket", "Size Bucket", "left"],
                    ["dealCount", "Deal Count", "right"],
                    ["mrrWon", "MRR Won", "right"],
                    ["winRate", "Win Rate", "right"],
                    ["avgDealSize", "Avg Deal Size", "right"],
                  ] as [SizeSortCol, string, string][]).map(([key, label, align]) => (
                    <th key={key} onClick={() => toggleSizeSort(key)} style={{ ...TH, textAlign: align as any }}>
                      {label}
                      {sizeSortCol === key && <span style={{ marginLeft: 4, fontSize: 9 }}>{sizeSortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const totCount = sizeRows.reduce((s, r) => s + r.dealCount, 0);
                  const totMrr = sizeRows.reduce((s, r) => s + r.mrrWon, 0);
                  const totWon = wonDeals.length;
                  const totClosed = wonDeals.length + lostDeals.length;
                  return (
                    <tr style={{ background: "var(--card)", fontWeight: 600 }}>
                      <td style={{ ...TD, fontWeight: 700 }}>TOTAL</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totCount}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{fmtMRR(totMrr)}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totClosed > 0 ? `${Math.round((totWon / totClosed) * 100)}%` : "—"}</td>
                      <td style={{ ...TD, textAlign: "right" }} className="num">{totWon > 0 ? fmtMRR(totMrr / totWon) : "—"}</td>
                    </tr>
                  );
                })()}
                {sortedSizeRows.map(r => (
                  <tr key={r.bucket}>
                    <td style={{ ...TD, fontWeight: 500, color: "var(--ink-1)" }}>{r.bucket}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.dealCount}</td>
                    <td style={{ ...TD, textAlign: "right", fontWeight: 600 }} className="num">{fmtMRR(r.mrrWon)}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.winRate != null ? `${Math.round(r.winRate * 100)}%` : "—"}</td>
                    <td style={{ ...TD, textAlign: "right" }} className="num">{r.avgDealSize != null ? fmtMRR(r.avgDealSize) : "—"}</td>
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
