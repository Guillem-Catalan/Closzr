import { useState, useEffect } from "react";
import { supabase } from "./supabase";

export function useOrgchartMap() {
  const [emailToTeam, setEmailToTeam] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const { data } = await supabase
        .from("orgchart")
        .select("email, team_name, is_active")
        .eq("is_active", true);

      if (cancelled) return;

      const map = new Map<string, string>();
      for (const r of data ?? []) {
        if (r.email && r.team_name) map.set(r.email, r.team_name);
      }
      setEmailToTeam(map);
      setLoading(false);
    })();

    return () => { cancelled = true; };
  }, []);

  return { emailToTeam, loading };
}
