import { useState, useEffect } from "react";
import { supabase } from "./supabase";
import type { Period } from "./useRepStats";

export type TeamStatRow = {
  key: string;
  value: number | null;
  pattern: string;
  scope: string;
  history: Array<{ date: string; value: number }>;
};

type RawRow = {
  pattern_key: string;
  pattern: string | null;
  value: number | null;
  scope: string | null;
  history: any;
};

function parseRows(rows: RawRow[], period: Period): Map<string, TeamStatRow[]> {
  const prefix = `team_${period}_`;
  const map = new Map<string, TeamStatRow[]>();

  for (const r of rows) {
    const pk = r.pattern_key || "";
    if (!pk.startsWith(prefix)) continue;

    const scope = r.scope || "";
    const team = scope.startsWith("team:") ? scope.slice(5) : "";
    if (!team) continue;

    const afterPrefix = pk.slice(prefix.length);
    // Key format: {stat_key}_{aggregate}_{team_slug}
    // We combine stat_key + aggregate as the key for lookup
    // E.g. "win_rate_avg_telefonica" -> key = "win_rate_avg"
    // We strip the team slug by finding the scope-derived slug
    const teamSlug = team
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "");
    const suffix = `_${teamSlug}`;
    const statKey = afterPrefix.endsWith(suffix)
      ? afterPrefix.slice(0, -suffix.length)
      : afterPrefix;

    let history: Array<{ date: string; value: number }> = [];
    if (r.history) {
      try {
        const h = typeof r.history === "string" ? JSON.parse(r.history) : r.history;
        if (Array.isArray(h)) history = h;
      } catch { /* ignore */ }
    }

    const stat: TeamStatRow = {
      key: statKey,
      value: r.value,
      pattern: r.pattern || "",
      scope,
      history,
    };

    const arr = map.get(team) || [];
    arr.push(stat);
    map.set(team, arr);
  }
  return map;
}

export function useTeamStats(period: Period) {
  const [stats, setStats] = useState<Map<string, TeamStatRow[]>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      const cols = "pattern_key,pattern,value,scope,history";
      const likePattern = `team_${period}_%`;

      const { data, error: err } = await supabase
        .from("learned_patterns")
        .select(cols)
        .eq("pattern_type", "team_stat")
        .like("pattern_key", likePattern);

      if (cancelled) return;

      if (err) {
        setError(err.message);
        setLoading(false);
        return;
      }

      if (!cancelled) {
        setStats(parseRows((data ?? []) as RawRow[], period));
        setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [period]);

  return { stats, loading, error };
}
