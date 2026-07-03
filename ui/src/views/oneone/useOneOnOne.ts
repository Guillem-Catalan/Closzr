import { useState, useEffect, useCallback, useRef } from "react";
import { supabase } from "../../data/supabase";

const OO_COLS = "deal_id,hs_deal_id,company_name,deal_name_full,stage,macro_stage,pae,pbd,team,mrr,close_probability,close_date_hs,estimated_close_date,is_stale,stale_days,deal_assessment,forecast_reasoning,forecast_confidence,deal_momentum,last_contact_label,deal_age_days,action_headline,deal_summary";

export type OODeal = {
  deal_id: string;
  hs_deal_id: string | null;
  company_name: string | null;
  deal_name_full: string | null;
  stage: string | null;
  macro_stage: string | null;
  pae: string | null;
  pbd: string | null;
  team: string | null;
  mrr: number | null;
  close_probability: number | null;
  close_date_hs: string | null;
  estimated_close_date: string | null;
  is_stale: boolean | null;
  stale_days: number | null;
  deal_assessment: string | null;
  forecast_reasoning: string | null;
  forecast_confidence: string | null;
  deal_momentum: string | null;
  last_contact_label: string | null;
  deal_age_days: number | null;
  action_headline: string | null;
  deal_summary: string | null;
};

export type OOEntry = {
  deal_id: string;
  deal_name: string;
  section: string;
  type: "change" | "note" | "commitment";
  field?: string;
  old_val?: string;
  new_val?: string;
  note?: string;
  at: string;
};

export type OOSession = {
  id: string;
  tl_email: string;
  rep_name: string;
  team: string | null;
  week_type: number;
  session_date: string;
  checks: Record<string, boolean>;
  entries: OOEntry[];
};

function monthKey(offset: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() + offset);
  return d.toISOString().slice(0, 7);
}

function inMonth(date: string | null, ym: string): boolean {
  return !!date && date.startsWith(ym);
}

export function useOneOnOne(repName: string, weekType: number, tlEmail: string, monday: string) {
  const [deals, setDeals] = useState<OODeal[]>([]);
  const [reps, setReps] = useState<string[]>([]);
  const [session, setSession] = useState<OOSession | null>(null);
  const [history, setHistory] = useState<OOSession[]>([]);
  const [loading, setLoading] = useState(true);
  const sessionRef = useRef(session);
  sessionRef.current = session;

  useEffect(() => {
    supabase.from("deal_ui").select("pae").not("macro_stage", "in", "(closed,excluded)").not("pae", "is", null)
      .then(({ data }) => {
        const names = [...new Set((data || []).map((d: any) => d.pae as string).filter(Boolean))].sort();
        setReps(names);
      });
  }, []);

  useEffect(() => {
    if (!repName) { setDeals([]); setLoading(false); return; }
    setLoading(true);
    supabase.from("deal_ui").select(OO_COLS).eq("pae", repName).not("macro_stage", "in", "(closed,excluded)")
      .then(({ data }) => {
        setDeals((data || []) as OODeal[]);
        setLoading(false);
      });
  }, [repName]);

  useEffect(() => {
    if (!repName || !tlEmail || !monday) { setSession(null); return; }
    supabase.from("oneone_sessions").select("*")
      .eq("tl_email", tlEmail).eq("rep_name", repName).eq("session_date", monday)
      .maybeSingle()
      .then(({ data }) => {
        if (data) {
          setSession(data as OOSession);
        } else {
          setSession({
            id: "", tl_email: tlEmail, rep_name: repName, team: null,
            week_type: weekType, session_date: monday, checks: {}, entries: [],
          });
        }
      });
  }, [repName, tlEmail, weekType, monday]);

  useEffect(() => {
    if (!repName || !tlEmail) { setHistory([]); return; }
    supabase.from("oneone_sessions").select("*")
      .eq("rep_name", repName).order("session_date", { ascending: false }).limit(12)
      .then(({ data }) => setHistory((data || []) as OOSession[]));
  }, [repName, tlEmail]);

  const persist = useCallback(async (updated: OOSession) => {
    const row = {
      tl_email: updated.tl_email, rep_name: updated.rep_name,
      team: updated.team, week_type: updated.week_type,
      session_date: monday, checks: updated.checks, entries: updated.entries,
    };
    const { data } = await supabase.from("oneone_sessions")
      .upsert(row, { onConflict: "tl_email,rep_name,session_date" }).select().single();
    if (data) setSession(data as OOSession);
  }, [monday]);

  const toggleCheck = useCallback((checkId: string) => {
    const s = sessionRef.current;
    if (!s) return;
    const next = { ...s, checks: { ...s.checks, [checkId]: !s.checks[checkId] } };
    setSession(next);
    persist(next);
  }, [persist]);

  const addEntry = useCallback((entry: Omit<OOEntry, "at">) => {
    const s = sessionRef.current;
    if (!s) return;
    const full: OOEntry = { ...entry, at: new Date().toISOString() };
    const next = { ...s, entries: [...s.entries, full] };
    setSession(next);
    persist(next);
  }, [persist]);

  const today = new Date().toISOString().slice(0, 10);
  const m0 = monthKey(0);
  const m1 = monthKey(1);
  const m2 = monthKey(2);

  const getDealsFor = useCallback((query: string): OODeal[] => {
    switch (query) {
      case "past_close":
        return deals.filter(d => d.close_date_hs && d.close_date_hs < today);
      case "same_stage_30d":
        return deals.filter(d => (d.stale_days || 0) >= 30);
      case "stale_7d":
        return deals.filter(d => (d.stale_days || 0) >= 7);
      case "demo_6w":
        return deals.filter(d => d.macro_stage === "demo" && (d.deal_age_days || 0) > 42);
      case "past_close_or_stale":
        return deals.filter(d => (d.close_date_hs && d.close_date_hs < today) || (d.stale_days || 0) >= 7);
      case "m0":
        return deals.filter(d => inMonth(d.close_date_hs, m0) || inMonth(d.estimated_close_date, m0));
      case "m1":
        return deals.filter(d => inMonth(d.close_date_hs, m1) || inMonth(d.estimated_close_date, m1));
      case "m2":
        return deals.filter(d => inMonth(d.close_date_hs, m2) || inMonth(d.estimated_close_date, m2));
      case "m1_m2_pusheable":
        return deals.filter(d => {
          const isM2 = inMonth(d.close_date_hs, m2) || inMonth(d.estimated_close_date, m2);
          const isLateM1 = inMonth(d.close_date_hs, m1) || inMonth(d.estimated_close_date, m1);
          return (isM2 || isLateM1) && (d.deal_momentum === "accelerating" || (d.close_probability || 0) >= 40);
        });
      case "m0_at_risk":
        return deals.filter(d => {
          const isM0 = inMonth(d.close_date_hs, m0) || inMonth(d.estimated_close_date, m0);
          return isM0 && ((d.stale_days || 0) >= 5 || d.deal_momentum === "stalling" || d.deal_momentum === "declining");
        });
      case "m0_closing_soon": {
        const nextWeek = new Date();
        nextWeek.setDate(nextWeek.getDate() + 7);
        const nw = nextWeek.toISOString().slice(0, 10);
        return deals.filter(d => {
          const isM0 = inMonth(d.close_date_hs, m0) || inMonth(d.estimated_close_date, m0);
          return isM0 && d.close_date_hs && d.close_date_hs <= nw;
        });
      }
      default:
        return [];
    }
  }, [deals, today, m0, m1, m2]);

  const getCoverage = useCallback((month: string): { total: number; ratio: number } => {
    const mDeals = deals.filter(d => inMonth(d.estimated_close_date, month));
    const total = mDeals.reduce((s, d) => s + (d.mrr || 0), 0);
    return { total, ratio: 0 };
  }, [deals]);

  return { deals, reps, session, history, loading, getDealsFor, getCoverage, toggleCheck, addEntry };
}
