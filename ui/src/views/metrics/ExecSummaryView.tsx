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

// placeholder — Tasks 2-5 will add sub-components and the main component
export default function ExecSummaryView() {
  return <div style={{ padding: "24px 32px" }}>Loading redesign...</div>;
}
