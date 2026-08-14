import { useState, useEffect } from "react";
import { supabase } from "./supabase";

export type Period = "weekly" | "monthly" | "quarterly";

export type RepStatRow = {
  key: string;
  value: number | null;
  pattern: string;
  confidence: number;
  sampleSize: number;
  scope: string;
  history: Array<{ date: string; value: number }>;
};

type RawRow = {
  pattern_key: string;
  pattern: string | null;
  value: number | null;
  confidence: number | null;
  sample_size: number | null;
  scope: string | null;
  history: any;
};

const B_SEGMENT_KEYS = new Set([
  "active_deals_count", "pipeline_value", "stale_deals",
  "momentum_distribution", "stage_distribution", "avg_deal_age",
]);

function parseRows(rows: RawRow[], period: Period): Map<string, RepStatRow[]> {
  const prefix = `rep_${period}_`;
  const map = new Map<string, RepStatRow[]>();

  for (const r of rows) {
    const pk = r.pattern_key || "";
    if (!pk.startsWith(prefix)) continue;

    const scope = r.scope || "";
    const email = scope.startsWith("rep:") ? scope.slice(4)
      : scope.startsWith("rep_name:") ? scope.slice(9)
      : scope;

    if (!email) continue;

    const withoutPrefix = pk.slice(prefix.length);
    const slugParts = email.replace(/[@.]/g, "_");
    const suffixIdx = withoutPrefix.lastIndexOf("_" + slugParts.split("_")[0]);
    const statKey = suffixIdx > 0
      ? withoutPrefix.slice(0, withoutPrefix.length - slugParts.length - 1)
      : withoutPrefix;

    let history: Array<{ date: string; value: number }> = [];
    if (r.history) {
      try {
        const h = typeof r.history === "string" ? JSON.parse(r.history) : r.history;
        if (Array.isArray(h)) history = h;
      } catch { /* ignore */ }
    }

    const stat: RepStatRow = {
      key: statKey,
      value: r.value,
      pattern: r.pattern || "",
      confidence: r.confidence ?? 0,
      sampleSize: r.sample_size ?? 0,
      scope,
      history,
    };

    const arr = map.get(email) || [];
    arr.push(stat);
    map.set(email, arr);
  }
  return map;
}

export function useRepStats(period: Period) {
  const [stats, setStats] = useState<Map<string, RepStatRow[]>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      const cols = "pattern_key,pattern,value,confidence,sample_size,scope,history";
      const likePattern = `rep_${period}_%`;

      const { data, error: err } = await supabase
        .from("learned_patterns")
        .select(cols)
        .eq("pattern_type", "rep_stat")
        .like("pattern_key", likePattern);

      if (cancelled) return;

      if (err) {
        setError(err.message);
        setLoading(false);
        return;
      }

      const rows = (data ?? []) as RawRow[];
      let merged = rows;

      if (period !== "weekly") {
        const { data: bData } = await supabase
          .from("learned_patterns")
          .select(cols)
          .eq("pattern_type", "rep_stat")
          .like("pattern_key", "rep_weekly_%");

        if (!cancelled && bData) {
          const bRows = (bData as RawRow[]).filter(r => {
            const pk = r.pattern_key || "";
            const after = pk.slice("rep_weekly_".length);
            return [...B_SEGMENT_KEYS].some(k => after.startsWith(k));
          });
          merged = [...rows, ...bRows];
        }
      }

      if (!cancelled) {
        const mainStats = parseRows(merged, period);

        if (period !== "weekly") {
          const bStats = parseRows(
            merged.filter(r => (r.pattern_key || "").startsWith("rep_weekly_")),
            "weekly"
          );
          for (const [email, bArr] of bStats) {
            const existing = mainStats.get(email) || [];
            for (const s of bArr) {
              if (B_SEGMENT_KEYS.has(s.key) && !existing.some(e => e.key === s.key)) {
                existing.push(s);
              }
            }
            mainStats.set(email, existing);
          }
        }

        setStats(mainStats);
        setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [period]);

  return { stats, loading, error };
}
