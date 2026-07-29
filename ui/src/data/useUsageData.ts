import { useState, useEffect } from "react";
import { supabase } from "./supabase";

export type UsageDateRange = { from: string; to: string };

export type DauRow = { date: string; count: number };
export type WauRow = { weekStart: string; count: number };
export type MauRow = { month: string; count: number };
export type TopUserRow = { email: string; role: string; actionCount: number; lastActive: string };
export type ResourceRow = { resource: string; users: number; actions: number };
export type HeatmapCell = { dow: number; hour: number; count: number };
export type ActivationData = { totalUsers: number; activatedUsers: number; rate: number };

export type UsageData = {
  dau: DauRow[];
  wau: WauRow[];
  mau: MauRow[];
  topUsers: TopUserRow[];
  byResource: ResourceRow[];
  heatmap: HeatmapCell[];
  activation: ActivationData;
  totalActions: number;
  loading: boolean;
};

const EMPTY_ACTIVATION: ActivationData = { totalUsers: 0, activatedUsers: 0, rate: 0 };

export function useUsageData(range: UsageDateRange, role: string | null): UsageData {
  const [data, setData] = useState<Omit<UsageData, "loading">>({
    dau: [], wau: [], mau: [], topUsers: [], byResource: [],
    heatmap: [], activation: EMPTY_ACTIVATION, totalActions: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const from = range.from;
    const to = range.to;
    const r = role || undefined;

    Promise.all([
      supabase.rpc("usage_dau", { from_date: from, to_date: to, filter_role: r }),
      supabase.rpc("usage_wau", { from_date: from, to_date: to, filter_role: r }),
      supabase.rpc("usage_mau", { from_date: from, to_date: to, filter_role: r }),
      supabase.rpc("usage_top_users", { from_date: from, to_date: to, lim: 20, filter_role: r }),
      supabase.rpc("usage_by_resource", { from_date: from, to_date: to, filter_role: r }),
      supabase.rpc("usage_heatmap", { from_date: from, to_date: to, tz, filter_role: r }),
      supabase.rpc("usage_activation_rate", { from_date: from, to_date: to, filter_role: r }),
    ]).then(([dauRes, wauRes, mauRes, topRes, resRes, heatRes, actRes]) => {
      if (cancelled) return;

      const dau: DauRow[] = (dauRes.data || []).map((r: any) => ({ date: r.date, count: Number(r.count) }));
      const wau: WauRow[] = (wauRes.data || []).map((r: any) => ({ weekStart: r.week_start, count: Number(r.count) }));
      const mau: MauRow[] = (mauRes.data || []).map((r: any) => ({ month: r.month, count: Number(r.count) }));
      const topUsers: TopUserRow[] = (topRes.data || []).map((r: any) => ({
        email: r.email, role: r.role, actionCount: Number(r.action_count), lastActive: r.last_active,
      }));
      const byResource: ResourceRow[] = (resRes.data || []).map((r: any) => ({
        resource: r.resource, users: Number(r.users), actions: Number(r.actions),
      }));
      const heatmap: HeatmapCell[] = (heatRes.data || []).map((r: any) => ({
        dow: Number(r.dow), hour: Number(r.hour), count: Number(r.count),
      }));
      const actRow = (actRes.data || [])[0];
      const activation: ActivationData = actRow
        ? { totalUsers: Number(actRow.total_users), activatedUsers: Number(actRow.activated_users), rate: Number(actRow.rate) }
        : EMPTY_ACTIVATION;
      const totalActions = byResource.reduce((s, r) => s + r.actions, 0);

      setData({ dau, wau, mau, topUsers, byResource, heatmap, activation, totalActions });
      setLoading(false);
    }).catch(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [range.from, range.to, role]);

  return { ...data, loading };
}
