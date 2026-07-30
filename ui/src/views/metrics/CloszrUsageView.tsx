/*
 * Closzr Usage Dashboard — admin-only analytics
 *
 * Depends on these tracked events (via track() from data/track.ts):
 *   event_type: "view" | "click" | "action"
 *   resource: module slugs ("pipeline", "forecast", etc.) or interaction ids ("deal-detail", "sort")
 *
 * Server-side RPCs: usage_dau, usage_wau, usage_mau, usage_top_users,
 *   usage_by_resource, usage_heatmap, usage_activation_rate
 */
import { useState, useMemo, useEffect, useCallback } from "react";
import { useUsageData, type UsageDateRange } from "../../data/useUsageData";
import { usePermissions } from "../../permissions";
import { supabase } from "../../data/supabase";
import { Icon, Chip } from "../components";
import { ownerDisplayName } from "../../display";

type PresetKey = "7d" | "30d" | "90d" | "custom";
type GranKey = "dau" | "wau" | "mau";
type UserSortCol = "name" | "role" | "actionCount" | "lastActive";
type SortDir = "asc" | "desc";

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return isoDate(d);
}

function getPresetRange(key: PresetKey): UsageDateRange {
  const to = isoDate(new Date());
  switch (key) {
    case "7d":  return { from: daysAgo(6), to };
    case "30d": return { from: daysAgo(29), to };
    case "90d": return { from: daysAgo(89), to };
    default:    return { from: daysAgo(29), to };
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

const PRESETS: { key: PresetKey; label: string }[] = [
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
  { key: "custom", label: "Custom" },
];

const ROLES = ["All", "Admin", "Manager", "TL", "PAE"];
const DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const CARD: React.CSSProperties = {
  background: "var(--card-2)", borderRadius: 12, padding: "20px 24px", marginBottom: 16,
};
const HEADING: React.CSSProperties = {
  fontSize: 14, fontWeight: 700, color: "var(--ink-1)", marginBottom: 16,
  display: "flex", alignItems: "center", gap: 8,
};
const KPI_LABEL: React.CSSProperties = {
  fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4,
};
const KPI_VAL: React.CSSProperties = { fontSize: 22, fontWeight: 800, color: "var(--ink-1)" };
const TH: React.CSSProperties = {
  padding: "10px 12px", fontWeight: 600, color: "var(--ink-3)", fontSize: 11,
  textTransform: "uppercase", letterSpacing: ".08em", cursor: "pointer",
  userSelect: "none", borderBottom: "1px solid var(--line)", whiteSpace: "nowrap",
};
const TD: React.CSSProperties = { padding: "10px 12px", fontSize: 13 };

function KpiCard({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 20px" }}>
      <div style={KPI_LABEL}>{label}</div>
      <div style={{ ...KPI_VAL, color: tone || "var(--ink-1)" }} className="num">{value}</div>
      {sub && <div style={{ fontSize: 10, color: "var(--ink-4)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function computeYTicks(maxVal: number): number[] {
  if (maxVal <= 0) return [0];
  if (maxVal <= 5) return Array.from({ length: maxVal + 1 }, (_, i) => i);
  const step = Math.ceil(maxVal / 4);
  const ticks: number[] = [];
  for (let v = 0; v <= maxVal; v += step) ticks.push(v);
  if (ticks[ticks.length - 1] < maxVal) ticks.push(maxVal);
  return ticks;
}

function UsageLineChart({ data, height = 180 }: { data: { label: string; value: number }[]; height?: number }) {
  if (data.length === 0) return <p style={{ color: "var(--ink-4)", fontSize: 12, textAlign: "center" }}>No data yet. Activity will appear here once users start using the app.</p>;

  const w = 500, pad = 40, padRight = 10, padBottom = 30, padTop = 10;
  const iw = w - pad - padRight, ih = height - padTop - padBottom;
  const maxVal = Math.max(...data.map(d => d.value), 1);
  const ticks = computeYTicks(maxVal);
  const ceilVal = ticks[ticks.length - 1] || 1;
  const xs = data.map((_, i) => pad + (data.length === 1 ? iw / 2 : iw * i / (data.length - 1)));
  const ys = data.map(d => padTop + ih * (1 - d.value / ceilVal));
  const line = xs.map((x, i) => (i ? "L" : "M") + x.toFixed(1) + " " + ys[i].toFixed(1)).join(" ");
  const area = line + ` L${xs[xs.length - 1].toFixed(1)} ${padTop + ih} L${xs[0].toFixed(1)} ${padTop + ih} Z`;

  const labelStep = Math.max(1, Math.floor(data.length / 6));

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${height}`} style={{ display: "block" }}>
      {ticks.map(v => {
        const y = padTop + ih * (1 - v / ceilVal);
        return <g key={v}>
          <line x1={pad} y1={y} x2={w - padRight} y2={y} stroke="var(--line)" strokeWidth="1" />
          <text x={pad - 6} y={y + 4} fontSize="10" fill="var(--ink-4)" textAnchor="end" fontFamily="var(--font-mono)">{v}</text>
        </g>;
      })}
      <path d={area} fill="rgba(59,75,216,.10)" />
      <path d={line} fill="none" stroke="var(--indigo)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {xs.map((x, i) => <circle key={i} cx={x} cy={ys[i]} r="3" fill="#fff" stroke="var(--indigo)" strokeWidth="2" />)}
      {data.map((d, i) => i % labelStep === 0 ? (
        <text key={i} x={xs[i]} y={height - 4} fontSize="9" fill="var(--ink-4)" textAnchor="middle">{d.label}</text>
      ) : null)}
    </svg>
  );
}

function UsageHeatmap({ data }: { data: { dow: number; hour: number; count: number }[] }) {
  if (data.length === 0) return <p style={{ color: "var(--ink-4)", fontSize: 12, textAlign: "center" }}>No data yet. Activity will appear here once users start using the app.</p>;

  const grid = Array.from({ length: 7 }, () => Array(24).fill(0) as number[]);
  let maxCount = 0;
  for (const c of data) {
    grid[c.dow][c.hour] = c.count;
    if (c.count > maxCount) maxCount = c.count;
  }
  const cellSize = 22;

  return (
    <div style={{ overflowX: "auto" }}>
      <div style={{ display: "inline-grid", gridTemplateColumns: `40px repeat(24, ${cellSize}px)`, gap: 2 }}>
        <div />
        {Array.from({ length: 24 }, (_, h) => (
          <div key={h} style={{ fontSize: 9, color: "var(--ink-4)", textAlign: "center" }}>{h}</div>
        ))}
        {DOW_LABELS.map((day, dow) => (
          <div key={dow} style={{ display: "contents" }}>
            <div style={{ fontSize: 11, color: "var(--ink-3)", display: "flex", alignItems: "center" }}>{day}</div>
            {Array.from({ length: 24 }, (_, h) => {
              const v = grid[dow][h];
              const opacity = maxCount > 0 ? v / maxCount : 0;
              return (
                <div
                  key={`${dow}-${h}`}
                  title={`${day} ${h}:00 — ${v} actions`}
                  style={{
                    width: cellSize, height: cellSize, borderRadius: 3,
                    background: v === 0 ? "var(--card)" : `rgba(30,120,60,${0.15 + opacity * 0.85})`,
                  }}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CloszrUsageView() {
  const { profile } = usePermissions();
  const [preset, setPreset] = useState<PresetKey>("30d");
  const [range, setRange] = useState<UsageDateRange>(() => getPresetRange("30d"));
  const [roleFilter, setRoleFilter] = useState<string | null>(null);
  const [userFilter, setUserFilter] = useState<string | null>(null);
  const [gran, setGran] = useState<GranKey>("dau");
  const [userSort, setUserSort] = useState<UserSortCol>("actionCount");
  const [userSortDir, setUserSortDir] = useState<SortDir>("desc");
  const [expandedUser, setExpandedUser] = useState<string | null>(null);
  const [userEvents, setUserEvents] = useState<any[]>([]);
  const [userEventsLoading, setUserEventsLoading] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const [logData, setLogData] = useState<any[]>([]);
  const [logLoading, setLogLoading] = useState(false);
  const [logPage, setLogPage] = useState(0);
  const [logSearch, setLogSearch] = useState("");
  const [logResource, setLogResource] = useState("");
  const [logHasMore, setLogHasMore] = useState(true);
  const [allUsers, setAllUsers] = useState<{ email: string; name: string }[]>([]);

  useEffect(() => {
    supabase.from("users").select("email,name").order("name").then(({ data }) => {
      setAllUsers((data || []).map((u: any) => ({ email: u.email, name: u.name || u.email.split("@")[0] })));
    });
  }, []);

  const D = useUsageData(range, roleFilter, userFilter);

  if (profile && profile.role !== "Admin") {
    return <p style={{ color: "var(--ink-3)", padding: 32 }}>Admin access required.</p>;
  }

  const applyPreset = (key: PresetKey) => {
    setPreset(key);
    if (key !== "custom") setRange(getPresetRange(key));
  };

  const latestActiveUsers = useMemo(() => {
    if (gran === "dau") return D.dau.length > 0 ? D.dau[D.dau.length - 1].count : 0;
    if (gran === "wau") return D.wau.length > 0 ? D.wau[D.wau.length - 1].count : 0;
    return D.mau.length > 0 ? D.mau[D.mau.length - 1].count : 0;
  }, [D.dau, D.wau, D.mau, gran]);

  const stickinessData = useMemo(() => {
    if (D.dau.length === 0 || D.mau.length === 0) return null;
    const activeDays = D.dau.filter(d => d.count > 0).length;
    const totalDays = D.dau.length;
    const avgDau = D.dau.reduce((s, d) => s + d.count, 0) / totalDays;
    const avgMau = D.mau.reduce((s, d) => s + d.count, 0) / D.mau.length;
    if (avgMau === 0) return null;
    const pct = Math.round((avgDau / avgMau) * 100);
    return { pct, activeDays, totalDays };
  }, [D.dau, D.mau]);

  const stickiness = stickinessData?.pct ?? null;
  const stickinessColor = stickiness === null ? undefined : stickiness > 25 ? "var(--green-ink)" : stickiness >= 15 ? "var(--amber-ink)" : "var(--red-ink)";

  const chartData = useMemo(() => {
    if (gran === "dau") return D.dau.map(d => ({ label: d.date.slice(5), value: d.count }));
    if (gran === "wau") return D.wau.map(d => ({ label: d.weekStart.slice(5), value: d.count }));
    return D.mau.map(d => ({ label: d.month, value: d.count }));
  }, [D.dau, D.wau, D.mau, gran]);

  const sortedUsers = useMemo(() => {
    const rows = [...D.topUsers];
    rows.sort((a, b) => {
      let av: any, bv: any;
      if (userSort === "name") { av = ownerDisplayName(a.email); bv = ownerDisplayName(b.email); }
      else if (userSort === "role") { av = a.role; bv = b.role; }
      else if (userSort === "actionCount") { av = a.actionCount; bv = b.actionCount; }
      else { av = a.lastActive; bv = b.lastActive; }
      if (typeof av === "string") return userSortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return userSortDir === "asc" ? av - bv : bv - av;
    });
    return rows;
  }, [D.topUsers, userSort, userSortDir]);

  const toggleUserSort = (col: UserSortCol) => {
    if (userSort === col) setUserSortDir(d => d === "asc" ? "desc" : "asc");
    else { setUserSort(col); setUserSortDir("desc"); }
  };

  const expandUser = useCallback((email: string) => {
    if (expandedUser === email) { setExpandedUser(null); return; }
    setExpandedUser(email);
    setUserEventsLoading(true);
    supabase.from("usage_events")
      .select("created_at,event_type,resource,user_agent")
      .eq("email", email)
      .gte("created_at", range.from)
      .lte("created_at", range.to + "T23:59:59")
      .order("created_at", { ascending: false })
      .limit(50)
      .then(({ data }) => {
        setUserEvents(data || []);
        setUserEventsLoading(false);
      });
  }, [expandedUser, range]);

  const peaks = useMemo(() => {
    if (D.heatmap.length === 0) return null;
    let maxCell = D.heatmap[0];
    for (const c of D.heatmap) { if (c.count > maxCell.count) maxCell = c; }
    const dayTotals = Array(7).fill(0) as number[];
    for (const c of D.heatmap) dayTotals[c.dow] += c.count;
    const peakDowIdx = dayTotals.indexOf(Math.max(...dayTotals));
    return { peakDay: DOW_LABELS[peakDowIdx], peakHour: `${maxCell.hour}:00` };
  }, [D.heatmap]);

  const resourceBars = useMemo(() => {
    const totalUsers = D.activation.totalUsers || 1;
    return D.byResource.map(r => ({
      ...r,
      adoptionPct: Math.round((r.users / totalUsers) * 100),
    }));
  }, [D.byResource, D.activation.totalUsers]);

  const maxActions = useMemo(() => Math.max(...resourceBars.map(r => r.actions), 1), [resourceBars]);

  useEffect(() => {
    if (!logOpen) return;
    setLogLoading(true);
    const PAGE_SIZE = 50;
    let q = supabase.from("usage_events")
      .select("created_at,email,event_type,resource,user_agent")
      .gte("created_at", range.from)
      .lte("created_at", range.to + "T23:59:59")
      .order("created_at", { ascending: false })
      .range(logPage * PAGE_SIZE, (logPage + 1) * PAGE_SIZE - 1);
    if (userFilter) q = q.eq("email", userFilter);
    if (logResource) q = q.eq("resource", logResource);
    if (logSearch) q = q.or(`email.ilike.%${logSearch}%,resource.ilike.%${logSearch}%`);

    q.then(({ data }) => {
      setLogData(data || []);
      setLogHasMore((data || []).length === PAGE_SIZE);
      setLogLoading(false);
    });
  }, [logOpen, logPage, logSearch, logResource, range, userFilter]);

  const GranToggle = (
    <div style={{ display: "inline-flex", gap: 0, borderRadius: 8, overflow: "hidden", border: "1px solid var(--line)" }}>
      {(["dau", "wau", "mau"] as GranKey[]).map(g => (
        <button key={g} onClick={() => setGran(g)}
          style={{
            padding: "4px 12px", fontSize: 11, fontWeight: 600, border: "none", cursor: "pointer",
            background: gran === g ? "var(--ink-1)" : "var(--card-2)",
            color: gran === g ? "var(--bg)" : "var(--ink-3)",
          }}>{g.toUpperCase()}</button>
      ))}
    </div>
  );

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1100 }}>
      {/* Header + controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 12 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-1)", margin: 0 }}>Closzr Usage</h2>
        <span style={{ flex: 1 }} />
        <select value={userFilter || ""} onChange={e => setUserFilter(e.target.value || null)}
          className="cz-native-select" style={{ fontSize: 12, padding: "4px 10px" }}>
          <option value="">All users</option>
          {allUsers.map(u => <option key={u.email} value={u.email}>{u.name}</option>)}
        </select>
        <select value={roleFilter || "All"} onChange={e => setRoleFilter(e.target.value === "All" ? null : e.target.value)}
          className="cz-native-select" style={{ fontSize: 12, padding: "4px 10px" }}>
          {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {/* Date range presets */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 28, flexWrap: "wrap" }}>
        {PRESETS.map(p => (
          <button key={p.key} onClick={() => applyPreset(p.key)}
            style={{
              padding: "5px 14px", borderRadius: 8, border: "1px solid var(--line)",
              background: preset === p.key ? "var(--ink-1)" : "var(--card-2)",
              color: preset === p.key ? "var(--bg)" : "var(--ink-2)",
              fontSize: 12, fontWeight: 600, cursor: "pointer",
            }}>{p.label}</button>
        ))}
        {preset === "custom" && (
          <>
            <input type="date" value={range.from}
              onChange={e => setRange(r => ({ from: e.target.value, to: e.target.value > r.to ? e.target.value : r.to }))}
              className="cz-native-select" style={{ fontSize: 12, padding: "4px 10px" }} />
            <span style={{ fontSize: 12, color: "var(--ink-3)" }}>to</span>
            <input type="date" value={range.to}
              onChange={e => setRange(r => ({ from: r.from > e.target.value ? e.target.value : r.from, to: e.target.value }))}
              className="cz-native-select" style={{ fontSize: 12, padding: "4px 10px" }} />
          </>
        )}
        {D.loading && <span style={{ fontSize: 11, color: "var(--ink-4)" }}>Loading...</span>}
      </div>

      {/* Row 1: KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16, marginBottom: 24 }}>
        <div style={{ background: "var(--card-2)", borderRadius: 10, padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
            <div style={KPI_LABEL}>Active Users</div>
            {GranToggle}
          </div>
          <div style={KPI_VAL} className="num">{D.loading ? "—" : latestActiveUsers}</div>
          {!D.loading && latestActiveUsers === 0 && <div style={{ fontSize: 10, color: "var(--ink-4)", marginTop: 4 }}>No activity in this period</div>}
        </div>
        <KpiCard
          label="Stickiness (DAU/MAU)"
          value={stickiness === null ? "—" : `${stickiness}%`}
          tone={stickinessColor}
          sub={stickinessData === null ? "No activity in this period" : `${stickinessData.activeDays}/${stickinessData.totalDays} days with activity`}
        />
        <KpiCard label="Total Actions" value={D.loading ? "—" : D.totalActions.toLocaleString()} sub={D.totalActions === 0 && !D.loading ? "No activity in this period" : undefined} />
        <KpiCard
          label="Activation Rate"
          value={D.loading ? "—" : `${Math.round(D.activation.rate * 100)}%`}
          sub={D.loading ? undefined : `${D.activation.activatedUsers}/${D.activation.totalUsers} users used >=2 features`}
          tone={D.activation.rate > 0.5 ? "var(--green-ink)" : D.activation.rate > 0.25 ? "var(--amber-ink)" : undefined}
        />
      </div>

      {/* Row 2: Who */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* Top Users */}
        <section style={CARD}>
          <div style={HEADING}>
            <Icon name="users" size={18} />
            Top Users
          </div>
          {sortedUsers.length === 0 ? (
            <p style={{ color: "var(--ink-3)", fontSize: 13 }}>No user activity recorded in this period.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    {([["name", "User", "left"], ["role", "Role", "left"], ["actionCount", "Actions", "right"], ["lastActive", "Last Active", "right"]] as [UserSortCol, string, string][]).map(([key, label, align]) => (
                      <th key={key} onClick={() => toggleUserSort(key)} style={{ ...TH, textAlign: align as any }}>
                        {label}
                        {userSort === key && <span style={{ marginLeft: 4, fontSize: 9 }}>{userSortDir === "asc" ? "▲" : "▼"}</span>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedUsers.map(u => (
                    <tbody key={u.email}>
                      <tr onClick={() => expandUser(u.email)} style={{ cursor: "pointer" }}
                        onMouseEnter={e => (e.currentTarget.style.background = "var(--card)")}
                        onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                        <td style={{ ...TD, fontWeight: 500, color: "var(--ink-1)" }}>{ownerDisplayName(u.email)}</td>
                        <td style={{ ...TD, color: "var(--ink-3)" }}>{u.role}</td>
                        <td style={{ ...TD, textAlign: "right", fontWeight: 600 }} className="num">{u.actionCount}</td>
                        <td style={{ ...TD, textAlign: "right", color: "var(--ink-3)" }}>{relativeTime(u.lastActive)}</td>
                      </tr>
                      {expandedUser === u.email && (
                        <tr>
                          <td colSpan={4} style={{ padding: "8px 12px", background: "var(--card)" }}>
                            {userEventsLoading ? (
                              <span style={{ fontSize: 12, color: "var(--ink-4)" }}>Loading events...</span>
                            ) : userEvents.length === 0 ? (
                              <span style={{ fontSize: 12, color: "var(--ink-4)" }}>No events found.</span>
                            ) : (
                              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                                <thead>
                                  <tr>
                                    <th style={{ ...TH, fontSize: 10, padding: "6px 8px" }}>Time</th>
                                    <th style={{ ...TH, fontSize: 10, padding: "6px 8px" }}>Type</th>
                                    <th style={{ ...TH, fontSize: 10, padding: "6px 8px" }}>Resource</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {userEvents.map((ev: any, i: number) => (
                                    <tr key={i}>
                                      <td style={{ ...TD, fontSize: 11, padding: "4px 8px" }}>{new Date(ev.created_at).toLocaleString()}</td>
                                      <td style={{ ...TD, fontSize: 11, padding: "4px 8px" }}>{ev.event_type}</td>
                                      <td style={{ ...TD, fontSize: 11, padding: "4px 8px" }}>{ev.resource}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Active Users Over Time */}
        <section style={CARD}>
          <div style={HEADING}>
            <Icon name="trendUp" size={18} />
            Active Users Over Time
            <span style={{ flex: 1 }} />
            {GranToggle}
          </div>
          <UsageLineChart data={chartData} />
        </section>
      </div>

      {/* Row 3: What */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* Feature Adoption */}
        <section style={CARD}>
          <div style={HEADING}>
            <Icon name="barChart" size={18} />
            Feature Adoption
          </div>
          {resourceBars.length === 0 ? (
            <p style={{ color: "var(--ink-4)", fontSize: 12 }}>No data yet. Activity will appear here once users start using the app.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {resourceBars.map(r => (
                <div key={r.resource} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 12, color: "var(--ink-2)", minWidth: 90, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.resource}</span>
                  <div style={{ flex: 1, height: 8, background: "var(--card)", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${r.adoptionPct}%`, background: "var(--indigo)", borderRadius: 4, minWidth: 2 }} />
                  </div>
                  <span className="num" style={{ fontSize: 11, color: "var(--ink-3)", minWidth: 36, textAlign: "right" }}>{r.adoptionPct}%</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Access Volume */}
        <section style={CARD}>
          <div style={HEADING}>
            <Icon name="barChart" size={18} />
            Access Volume
          </div>
          {resourceBars.length === 0 ? (
            <p style={{ color: "var(--ink-4)", fontSize: 12 }}>No data yet. Activity will appear here once users start using the app.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {resourceBars.map(r => (
                <div key={r.resource} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 12, color: "var(--ink-2)", minWidth: 90, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.resource}</span>
                  <div style={{ flex: 1, height: 8, background: "var(--card)", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${Math.round((r.actions / maxActions) * 100)}%`, background: "var(--blue, var(--indigo))", borderRadius: 4, minWidth: 2 }} />
                  </div>
                  <span className="num" style={{ fontSize: 11, color: "var(--ink-3)", minWidth: 36, textAlign: "right" }}>{r.actions}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Row 4: When */}
      <section style={CARD}>
        <div style={HEADING}>
          <Icon name="clock" size={18} />
          Usage Heatmap
          <span style={{ flex: 1 }} />
          {peaks && (
            <div style={{ display: "flex", gap: 8 }}>
              <Chip tone="green">Peak day: {peaks.peakDay}</Chip>
              <Chip tone="indigo">Peak hour: {peaks.peakHour}</Chip>
            </div>
          )}
        </div>
        <UsageHeatmap data={D.heatmap} />
        <div style={{ fontSize: 10, color: "var(--ink-4)", marginTop: 8 }}>
          Event count by day of week and hour (your timezone). Darker = more activity. Hover cells for details.
        </div>
      </section>

      {/* Row 5: Raw Log */}
      <section style={CARD}>
        <div style={{ ...HEADING, cursor: "pointer" }} onClick={() => { setLogOpen(o => !o); setLogPage(0); }}>
          <Icon name="file" size={18} />
          Raw Activity Log
          <Icon name="chevDown" size={14} style={{ transform: logOpen ? "rotate(180deg)" : "none", transition: "transform .2s" }} />
        </div>
        {logOpen && (
          <div>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <input type="text" placeholder="Search user or resource..." value={logSearch}
                onChange={e => { setLogSearch(e.target.value); setLogPage(0); }}
                style={{ flex: 1, padding: "6px 12px", fontSize: 12, borderRadius: 8, border: "1px solid var(--line)", background: "var(--card)", color: "var(--ink-1)", outline: "none" }} />
              <select value={logResource} onChange={e => { setLogResource(e.target.value); setLogPage(0); }}
                className="cz-native-select" style={{ fontSize: 12, padding: "4px 10px" }}>
                <option value="">All resources</option>
                {D.byResource.map(r => <option key={r.resource} value={r.resource}>{r.resource}</option>)}
              </select>
            </div>
            {logLoading ? (
              <p style={{ color: "var(--ink-4)", fontSize: 12 }}>Loading...</p>
            ) : logData.length === 0 ? (
              <p style={{ color: "var(--ink-3)", fontSize: 13 }}>No events found matching your filters.</p>
            ) : (
              <>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th style={TH}>Timestamp</th>
                        <th style={TH}>User</th>
                        <th style={TH}>Type</th>
                        <th style={TH}>Resource</th>
                        <th style={TH}>User Agent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logData.map((ev: any, i: number) => (
                        <tr key={i}>
                          <td style={{ ...TD, whiteSpace: "nowrap" }}>{new Date(ev.created_at).toLocaleString()}</td>
                          <td style={{ ...TD, fontWeight: 500 }}>{ownerDisplayName(ev.email)}</td>
                          <td style={TD}>{ev.event_type}</td>
                          <td style={TD}>{ev.resource}</td>
                          <td style={{ ...TD, fontSize: 11, color: "var(--ink-4)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ev.user_agent}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                  <button onClick={() => setLogPage(p => Math.max(0, p - 1))} disabled={logPage === 0}
                    style={{ padding: "4px 12px", fontSize: 12, borderRadius: 6, border: "1px solid var(--line)", background: "var(--card-2)", cursor: logPage === 0 ? "default" : "pointer", color: logPage === 0 ? "var(--ink-4)" : "var(--ink-2)" }}>
                    Previous
                  </button>
                  <span style={{ fontSize: 12, color: "var(--ink-3)" }}>Page {logPage + 1}</span>
                  <button onClick={() => setLogPage(p => p + 1)} disabled={!logHasMore}
                    style={{ padding: "4px 12px", fontSize: 12, borderRadius: 6, border: "1px solid var(--line)", background: "var(--card-2)", cursor: !logHasMore ? "default" : "pointer", color: !logHasMore ? "var(--ink-4)" : "var(--ink-2)" }}>
                    Next
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
