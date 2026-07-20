/* ============================================================
   CLOSZR — FORECAST v5
   KPI cards: Target | M0 (rep/closzr) | M1 | M2 (rep/closzr + pushable) | Closed (won/lost)
   Deal rows unified with Pipeline style
   ============================================================ */
import { useState, useMemo, useEffect, useRef } from "react";
import { Icon, Chip, ProbBadge, fmtMRR, MultiSelectTeam } from "../components";
import { useData } from "../../data/store";
import type { ForecastDeal, ClosedDeal, LostDeal } from "../../data/store";
import { hubspotDealUrl, CRM_SHORT, CRM_FORECAST_CATEGORIES, ROLE_LABELS, WON_LABEL, LOST_LABEL, WON_DISPLAY_LABEL } from "../../display";
import { normalize, distinctTeams, distinctOwners, distinctPipelines, expandTeams } from "../../data/filters";
import { usePermissions } from "../../permissions";
import { supabase } from "../../data/supabase";

function fmtEur(v: number | null | undefined): string {
  if (v == null || v === 0) return "—";
  return "€" + Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function fmtDate(d: string | null): string {
  if (!d) return "—";
  const s = d.slice(0, 10);
  const [, m, day] = s.split("-");
  return `${day}/${m}`;
}

function closeDateTone(hs: string | null, claudio: string | null): string {
  if (!hs || !claudio) return "var(--ink)";
  const hm = hs.slice(0, 7);
  const cm = claudio.slice(0, 7);
  if (hm === cm) return "var(--green)";
  const hd = new Date(hm + "-01");
  const cd = new Date(cm + "-01");
  const diff = Math.abs((cd.getFullYear() - hd.getFullYear()) * 12 + cd.getMonth() - hd.getMonth());
  if (diff <= 1) return "var(--amber)";
  return "var(--red)";
}

function HsLogo({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" fill="none">
      <path d="M391.8 197.4V133c17.2-8.3 29.1-25.8 29.1-46.1v-1.4c0-28.1-22.8-50.9-50.9-50.9h-1.4c-28.1 0-50.9 22.8-50.9 50.9v1.4c0 20.3 11.9 37.8 29.1 46.1v64.4c-25 5.1-47.9 16-67.2 31.6l-177.7-138.4c1.6-5.5 2.6-11.3 2.6-17.3C104.4 32.8 71.6 0 31.2 0S-42 32.8-42 73.2 57.6 146.4 98 146.4c0 0 0 0 0 0 6 0 11.8-1 17.3-2.6L291.6 280c-17.9 22-28.7 50-28.7 80.5 0 70.4 57.1 127.5 127.5 127.5S518 431 518 360.5 460.9 233 390.5 233c-.3 0-.5 0-.8 0l2.1-35.6zM390.5 425c-35.6 0-64.5-28.9-64.5-64.5s28.9-64.5 64.5-64.5 64.5 28.9 64.5 64.5-28.9 64.5-64.5 64.5z"
        fill="currentColor" transform="translate(42, 0) scale(0.88)" />
    </svg>
  );
}

const MANAGEMENT_ROLES = new Set(["Admin", "Manager", "Director", "TL"]);

type Panel = "m0" | "m1" | "m2" | "closed";

/* ---- Expandable deal row (pipeline-unified) ---- */
function FcRow({ d, open, onToggle, onOpen, showPushChip, dotColor }: { d: ForecastDeal; open: boolean; onToggle: () => void; onOpen: (row: any, tab?: string) => void; showPushChip?: boolean; dotColor?: string }) {
  const cdTone = closeDateTone(d.closeDate, d.claudioCloseDate);
  return (
    <>
      <div className="cz-prow" style={{ cursor: "pointer" }} onClick={onToggle}>
        <div className="cz-pc-deal">
          <span className="cz-pc-name" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {d.deal}
            {showPushChip && d.pushable && (
              <span style={{ fontSize: 9.5, fontWeight: 700, color: "var(--amber-ink)", background: "var(--amber-tint)", padding: "1px 6px", borderRadius: "var(--r-pill)", whiteSpace: "nowrap", flex: "none" }}>Push</span>
            )}
            {d.hsId && (
              <a href={hubspotDealUrl(d.hsId)} target="_blank" rel="noopener noreferrer"
                onClick={e => e.stopPropagation()} style={{ display: "inline-flex", color: "#ff7a59", flex: "none", opacity: 0.7, transition: "opacity .15s" }}
                onMouseEnter={e => (e.currentTarget.style.opacity = "1")} onMouseLeave={e => (e.currentTarget.style.opacity = "0.7")}>
                <HsLogo size={14} />
              </a>
            )}
          </span>
        </div>
        <div className="num" style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "center" }}>
          {dotColor && <span style={{ width: 7, height: 7, borderRadius: "50%", background: dotColor, flex: "none" }} />}
          {fmtMRR(d.mrr)}
        </div>
        <div><Chip tone={d.hsCategory === CRM_FORECAST_CATEGORIES[0] ? "green" : d.hsCategory === CRM_FORECAST_CATEGORIES[1] ? "amber" : "ink"} style={{ fontSize: 10.5 }}>{d.hsCategory || "—"}</Chip></div>
        <div><ProbBadge value={d.prob}/></div>
        <div className="cz-pc-close">
          <span className="num" style={{ flex: 1, textAlign: "right" }}>{fmtDate(d.closeDate)}</span>
          <span style={{ color: "var(--ink-3)", margin: "0 4px", flex: "none" }}>|</span>
          <span className="num" style={{ flex: 1, textAlign: "left", color: cdTone }}>{fmtDate(d.claudioCloseDate)}</span>
        </div>
        <div className="cz-pc-owner">{d.owner !== "—" ? d.owner : <span style={{ color: "var(--ink-4)" }}>—</span>}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button onClick={e => { e.stopPropagation(); onOpen({ id: d.id }, "hist"); }}
            style={{ fontSize: 11, fontWeight: 600, color: "var(--indigo)", background: "var(--indigo-tint)", border: "none", padding: "4px 10px", borderRadius: "var(--r-pill)", cursor: "pointer", whiteSpace: "nowrap" }}>
            Ver deal
          </button>
          <Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .18s" }} />
        </div>
      </div>
      {open && (
        <div style={{ padding: "16px 22px 20px", background: "var(--card-2)", borderBottom: "1px solid var(--line-2)", display: "flex", flexDirection: "column", gap: 12 }}>
          {d.pushable && d.pushAction && (
            <div style={{ padding: "12px 16px", background: "var(--amber-tint)", borderRadius: "var(--r-sm)", fontSize: 13.5, lineHeight: 1.55, color: "var(--amber-ink)" }}>
              <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--amber-ink)" }}>Push action</span>
              {d.pushAction}
            </div>
          )}
          {d.forecastReasoning && (
            <div>
              <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Reasoning</span>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: "var(--ink-2)" }}>{d.forecastReasoning}</p>
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {d.forecastAccelerators && (
              <div style={{ padding: "10px 14px", background: "var(--green-tint)", borderRadius: "var(--r-sm)" }}>
                <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--green-ink)" }}>Accelerators</span>
                <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                  {d.forecastAccelerators.split(/\n|\d+\.\s+/).filter(Boolean).map((b: string, i: number) => (
                    <li key={i} style={{ display: "flex", gap: 8, fontSize: 12.5, lineHeight: 1.5, color: "var(--green-ink)" }}>
                      <span style={{ color: "var(--green)", flex: "none" }}>•</span><span>{b.trim()}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {d.forecastRisks && (
              <div style={{ padding: "10px 14px", background: "var(--red-tint)", borderRadius: "var(--r-sm)" }}>
                <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--red-ink)" }}>Risks</span>
                <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                  {d.forecastRisks.split(/\n|\d+\.\s+/).filter(Boolean).map((b: string, i: number) => (
                    <li key={i} style={{ display: "flex", gap: 8, fontSize: 12.5, lineHeight: 1.5, color: "var(--red-ink)" }}>
                      <span style={{ color: "var(--red)", flex: "none" }}>•</span><span>{b.trim()}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 12, fontSize: 12.5, color: "var(--ink-3)" }}>
            {d.claudioCloseDate && <span>Closzr close: <b className="num">{d.claudioCloseDate}</b></span>}
            {d.closeDate && <span>{CRM_SHORT} close: <b className="num">{d.closeDate}</b></span>}
          </div>
        </div>
      )}
    </>
  );
}

/* ---- Closed Won row ---- */
const closedGrid: React.CSSProperties = { gridTemplateColumns: "minmax(180px,1.4fr) 90px 90px 70px 130px 110px" };

function ClosedRow({ d, open, onToggle, onOpen }: { d: ClosedDeal; open: boolean; onToggle: () => void; onOpen: (row: any, tab?: string) => void }) {
  const allBullets = (d.strengths || "").split("\n").map(s => s.replace(/^[-•]\s*/, "").trim()).filter(Boolean);
  return (
    <>
      <div className="cz-prow" style={{ cursor: "pointer", ...closedGrid }} onClick={onToggle}>
        <div className="cz-pc-deal">
          <span className="cz-pc-name" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {d.deal}
            {d.hsId && (
              <a href={hubspotDealUrl(d.hsId)} target="_blank" rel="noopener noreferrer"
                onClick={e => e.stopPropagation()} style={{ display: "inline-flex", color: "#ff7a59", flex: "none", opacity: 0.7, transition: "opacity .15s" }}
                onMouseEnter={e => (e.currentTarget.style.opacity = "1")} onMouseLeave={e => (e.currentTarget.style.opacity = "0.7")}>
                <HsLogo size={14} />
              </a>
            )}
          </span>
        </div>
        <div className="num">{fmtMRR(d.mrr)}</div>
        <div className="num">{fmtDate(d.last)}</div>
        <div className="num">{d.dealAge ? d.dealAge + "d" : "—"}</div>
        <div className="cz-pc-owner">{d.owner}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button onClick={e => { e.stopPropagation(); onOpen({ id: d.id }, "hist"); }}
            style={{ fontSize: 11, fontWeight: 600, color: "var(--indigo)", background: "var(--indigo-tint)", border: "none", padding: "4px 10px", borderRadius: "var(--r-pill)", cursor: "pointer", whiteSpace: "nowrap" }}>
            Ver deal
          </button>
          <Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .18s" }} />
        </div>
      </div>
      {open && allBullets.length > 0 && (
        <div style={{ padding: "16px 22px 20px", background: "var(--card-2)", borderBottom: "1px solid var(--line-2)" }}>
          <div style={{ padding: "12px 16px", background: "var(--green-tint)", borderRadius: "var(--r-sm)" }}>
            <span className="eyebrow" style={{ display: "block", marginBottom: 8, color: "var(--green-ink)" }}>How it was {WON_LABEL.toLowerCase()}</span>
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
              {allBullets.map((b, i) => (
                <li key={i} style={{ display: "flex", gap: 8, fontSize: 13, lineHeight: 1.55, color: "var(--green-ink)" }}>
                  <span style={{ color: "var(--green)", flex: "none" }}>•</span><span>{b}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}

/* ---- Lost row ---- */
function LostRow({ d, open, onToggle, onOpen }: { d: LostDeal; open: boolean; onToggle: () => void; onOpen: (row: any, tab?: string) => void }) {
  return (
    <>
      <div className="cz-prow" style={{ cursor: "pointer", ...closedGrid }} onClick={onToggle}>
        <div className="cz-pc-deal">
          <span className="cz-pc-name" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {d.deal}
            {d.hsId && (
              <a href={hubspotDealUrl(d.hsId)} target="_blank" rel="noopener noreferrer"
                onClick={e => e.stopPropagation()} style={{ display: "inline-flex", color: "#ff7a59", flex: "none", opacity: 0.7, transition: "opacity .15s" }}
                onMouseEnter={e => (e.currentTarget.style.opacity = "1")} onMouseLeave={e => (e.currentTarget.style.opacity = "0.7")}>
                <HsLogo size={14} />
              </a>
            )}
          </span>
        </div>
        <div className="num">{fmtMRR(d.mrr)}</div>
        <div className="num">{fmtDate(d.closeDate)}</div>
        <div className="num">{d.dealAge ? d.dealAge + "d" : "—"}</div>
        <div className="cz-pc-owner">{d.owner}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button onClick={e => { e.stopPropagation(); onOpen({ id: d.id }, "hist"); }}
            style={{ fontSize: 11, fontWeight: 600, color: "var(--indigo)", background: "var(--indigo-tint)", border: "none", padding: "4px 10px", borderRadius: "var(--r-pill)", cursor: "pointer", whiteSpace: "nowrap" }}>
            Ver deal
          </button>
          <Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .18s" }} />
        </div>
      </div>
      {open && d.lostReason && (
        <div style={{ padding: "16px 22px 20px", background: "var(--card-2)", borderBottom: "1px solid var(--line-2)" }}>
          <div style={{ padding: "12px 16px", background: "var(--red-tint)", borderRadius: "var(--r-sm)" }}>
            <span className="eyebrow" style={{ display: "block", marginBottom: 8, color: "var(--red-ink)" }}>{LOST_LABEL} reason</span>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: "var(--red-ink)" }}>{d.lostReason}</p>
          </div>
        </div>
      )}
    </>
  );
}


/* ---- Editable target ---- */
function EditableTarget({ value, teamFilter, targets, teams, canEdit, fontSize }: { value: number; teamFilter: string; targets: { team: string; month: string; monthly_target: number }[]; teams: string[]; canEdit: boolean; fontSize?: number }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const cm = new Date().toISOString().slice(0, 7);
  const fs = fontSize ?? 30;

  const handleSave = async () => {
    const num = parseInt(draft.replace(/[^\d]/g, ""), 10);
    if (isNaN(num) || num <= 0) { setEditing(false); return; }
    if (teamFilter) {
      await supabase.from("forecast_targets").upsert({ team: teamFilter, month: cm, monthly_target: num }, { onConflict: "team,month" });
    } else {
      const teamTargets = targets.filter(t => t.month === cm);
      if (teamTargets.length === 0 && teams.length > 0) {
        const perTeam = Math.round(num / teams.length);
        for (const team of teams) await supabase.from("forecast_targets").upsert({ team, month: cm, monthly_target: perTeam }, { onConflict: "team,month" });
      } else {
        const ratio = num / (value || 1);
        for (const t of teamTargets) await supabase.from("forecast_targets").upsert({ team: t.team, month: cm, monthly_target: Math.round(t.monthly_target * ratio) }, { onConflict: "team,month" });
      }
    }
    setEditing(false);
    window.location.reload();
  };

  if (editing) {
    return (
      <input autoFocus value={draft} onChange={e => setDraft(e.target.value)}
        onBlur={handleSave} onKeyDown={e => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") setEditing(false); }}
        className="display" style={{ width: 120, border: "none", borderBottom: "2px solid var(--indigo)", background: "transparent", fontSize: fs, fontWeight: 700, padding: 0, outline: "none", textAlign: "center" }} />
    );
  }
  return (
    <span className="display" onClick={() => { if (canEdit) { setDraft(String(value)); setEditing(true); } }}
      style={{ fontSize: fs, fontWeight: 700, letterSpacing: "-.02em", color: "var(--indigo)", cursor: canEdit ? "pointer" : "default" }} title={canEdit ? "Click to edit" : undefined}>
      {fmtEur(value)}
    </span>
  );
}

/* ---- KPI title style ---- */
const kpiTitle: React.CSSProperties = { fontSize: 15, fontWeight: 800, letterSpacing: ".04em", textTransform: "uppercase" as const, textAlign: "center" as const, display: "block" };

/* ============================================================ */
export default function ForecastView({ onOpen }: { onOpen: (row: any, tab?: string) => void }) {
  const D = useData();
  const F = D.forecast;
  const { profile } = usePermissions();
  const [panel, setPanel] = useState<Panel>("m0");
  const [pipelineFilters, setPipelineFilters] = useState<Set<string>>(new Set());
  const [teamFilters, setTeamFilters] = useState<Set<string>>(new Set());
  const [repFilter, setRepFilter] = useState("");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [closedTab, setClosedTab] = useState<"won" | "lost">("won");
  const [viewFilter, setViewFilter] = useState<"all" | "hs" | "closzr" | "shared">("all");
  type SortKey = "" | "mrr-desc" | "mrr-asc" | "prob-desc" | "prob-asc" | "hs-asc" | "hs-desc" | "closzr-asc" | "closzr-desc";
  const [sortKey, setSortKey] = useState<SortKey>("hs-asc");
  const [openMenu, setOpenMenu] = useState<"" | "mrr" | "prob" | "close">("");
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!openMenu) return;
    const h = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpenMenu(""); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [openMenu]);

  const canEditTarget = profile ? MANAGEMENT_ROLES.has(profile.role) : false;
  const pipelines = useMemo(() => distinctPipelines(F.allDeals), [F.allDeals]);
  const teams = useMemo(() => distinctTeams(F.allDeals), [F.allDeals]);
  const reps = useMemo(() => distinctOwners(F.allDeals, teamFilters.size === 1 ? [...teamFilters][0] : undefined), [F.allDeals, teamFilters]);
  const repNorm = repFilter ? normalize(repFilter) : "";

  const teamExpanded = useMemo(() => expandTeams(teamFilters), [teamFilters]);
  const applyFilters = <T extends { team?: string; pipeline?: string; owner: string; deal: string }>(deals: T[]): T[] => {
    let out = deals;
    if (pipelineFilters.size) out = out.filter(d => pipelineFilters.has((d as any).pipeline || ""));
    if (teamExpanded) out = out.filter(d => teamExpanded.has(d.team || ""));
    if (repFilter) out = out.filter(d => { const on = normalize(d.owner || ""); return on === repNorm || on.startsWith(repNorm + " "); });
    if (search.trim()) { const q = search.toLowerCase(); out = out.filter(d => d.deal.toLowerCase().includes(q) || (d.owner || "").toLowerCase().includes(q)); }
    return out;
  };

  const fm0 = useMemo(() => applyFilters(F.m0Deals), [F.m0Deals, pipelineFilters, teamExpanded, repFilter, search]);
  const fm1 = useMemo(() => applyFilters(F.m1Deals), [F.m1Deals, pipelineFilters, teamExpanded, repFilter, search]);
  const fm2 = useMemo(() => applyFilters(F.m2Deals), [F.m2Deals, pipelineFilters, teamExpanded, repFilter, search]);
  const fClosed = useMemo(() => applyFilters(F.closedDeals), [F.closedDeals, pipelineFilters, teamExpanded, repFilter, search]);
  const fLost = useMemo(() => applyFilters(F.lostDeals), [F.lostDeals, pipelineFilters, teamExpanded, repFilter, search]);

  const cm = new Date().toISOString().slice(0, 7);
  const singleTeamFilter = teamFilters.size === 1 ? [...teamFilters][0] : "";
  const target = useMemo(() => {
    if (teamFilters.size === 0) return F.target;
    const exp = expandTeams(teamFilters)!;
    return F.targets.filter(t => exp.has(t.team) && t.month === cm).reduce((s, t) => s + (t.monthly_target || 0), 0);
  }, [F.target, F.targets, teamFilters, cm]);

  const nmKey = (() => { const d = new Date(); d.setMonth(d.getMonth() + 1); return d.toISOString().slice(0, 7); })();
  const m2Key = (() => { const d = new Date(); d.setMonth(d.getMonth() + 2); return d.toISOString().slice(0, 7); })();

  const m0HsTotal = Math.round(fm0.filter(d => d.closeDate?.startsWith(cm)).reduce((s, d) => s + (d.mrr || 0), 0));
  const m0CloszrTotal = Math.round(fm0.filter(d => d.claudioCloseDate?.startsWith(cm)).reduce((s, d) => s + (d.mrr || 0), 0));
  const m1HsTotal = Math.round(fm1.filter(d => d.closeDate?.startsWith(nmKey)).reduce((s, d) => s + (d.mrr || 0), 0));
  const m1CloszrTotal = Math.round(fm1.filter(d => d.claudioCloseDate?.startsWith(nmKey)).reduce((s, d) => s + (d.mrr || 0), 0));
  const m2HsTotal = Math.round(fm2.filter(d => d.closeDate && d.closeDate >= m2Key).reduce((s, d) => s + (d.mrr || 0), 0));
  const m2CloszrTotal = Math.round(fm2.filter(d => d.claudioCloseDate && d.claudioCloseDate >= m2Key).reduce((s, d) => s + (d.mrr || 0), 0));
  const m2PushCount = fm2.filter(d => d.pushable).length;
  const m2PushVal = Math.round(fm2.filter(d => d.pushable).reduce((s, d) => s + (d.mrr || 0), 0));
  const closedTotal = Math.round(fClosed.reduce((s, d) => s + (d.mrr || 0), 0));
  const lostTotal = Math.round(fLost.reduce((s, d) => s + (d.mrr || 0), 0));

  const countSplit = (deals: ForecastDeal[], matchFn: (d: ForecastDeal) => { hs: boolean; cz: boolean }) => {
    let rep = 0, closzr = 0, shared = 0;
    for (const d of deals) {
      const { hs, cz } = matchFn(d);
      if (hs) rep++;
      if (cz) closzr++;
      if (hs && cz) shared++;
    }
    return { rep, closzr, shared };
  };
  const m0Split = countSplit(fm0, d => ({ hs: d.closeDate?.startsWith(cm) ?? false, cz: d.claudioCloseDate?.startsWith(cm) ?? false }));
  const m1Split = countSplit(fm1, d => ({ hs: d.closeDate?.startsWith(nmKey) ?? false, cz: d.claudioCloseDate?.startsWith(nmKey) ?? false }));
  const m2Split = countSplit(fm2, d => ({ hs: d.closeDate ? d.closeDate >= m2Key : false, cz: d.claudioCloseDate ? d.claudioCloseDate >= m2Key : false }));

  const targetM1 = useMemo(() => {
    if (teamFilters.size === 0) return F.targets.filter(t => t.month === nmKey).reduce((s, t) => s + (t.monthly_target || 0), 0);
    const exp = expandTeams(teamFilters)!;
    return F.targets.filter(t => exp.has(t.team) && t.month === nmKey).reduce((s, t) => s + (t.monthly_target || 0), 0);
  }, [F.targets, teamFilters, nmKey]);

  const targetM2 = useMemo(() => {
    if (teamFilters.size === 0) return F.targets.filter(t => t.month === m2Key).reduce((s, t) => s + (t.monthly_target || 0), 0);
    const exp = expandTeams(teamFilters)!;
    return F.targets.filter(t => exp.has(t.team) && t.month === m2Key).reduce((s, t) => s + (t.monthly_target || 0), 0);
  }, [F.targets, teamFilters, m2Key]);

  const pct = (v: number, t: number) => t > 0 ? Math.round(v / t * 100) : 0;
  const pctTone = (p: number) => p >= 70 ? "var(--green)" : p >= 30 ? "var(--amber)" : "var(--red)";
  const toggle = (p: Panel) => { setPanel(p); setExpandedId(null); setViewFilter("all"); };

  const sortDeals = (deals: ForecastDeal[]) => {
    const arr = [...deals];
    const nullsLast = (v: string | null) => v || "9999-12-31";
    switch (sortKey) {
      case "mrr-desc": return arr.sort((a, b) => (b.mrr || 0) - (a.mrr || 0));
      case "mrr-asc":  return arr.sort((a, b) => (a.mrr || 0) - (b.mrr || 0));
      case "prob-desc": return arr.sort((a, b) => (b.prob || 0) - (a.prob || 0));
      case "prob-asc":  return arr.sort((a, b) => (a.prob || 0) - (b.prob || 0));
      case "hs-asc":    return arr.sort((a, b) => nullsLast(a.closeDate).localeCompare(nullsLast(b.closeDate)));
      case "hs-desc":   return arr.sort((a, b) => nullsLast(b.closeDate).localeCompare(nullsLast(a.closeDate)));
      case "closzr-asc":  return arr.sort((a, b) => nullsLast(a.claudioCloseDate).localeCompare(nullsLast(b.claudioCloseDate)));
      case "closzr-desc": return arr.sort((a, b) => nullsLast(b.claudioCloseDate).localeCompare(nullsLast(a.claudioCloseDate)));
      default: return arr;
    }
  };

  const dropStyle: React.CSSProperties = { position: "absolute", top: "100%", left: "50%", transform: "translateX(-50%)", marginTop: 4, background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,.12)", zIndex: 20, minWidth: 170, padding: "4px 0" };
  const optStyle = (active: boolean): React.CSSProperties => ({ padding: "8px 14px", fontSize: 13, cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", fontWeight: active ? 600 : 400, color: active ? "var(--indigo)" : "var(--ink)", background: "transparent" });
  const colActive = (prefix: string) => sortKey.startsWith(prefix);

  const SortDrop = ({ col, options }: { col: "mrr" | "prob" | "close"; options: { key: SortKey; label: string }[] }) => (
    openMenu === col ? (
      <div ref={menuRef} style={dropStyle}>
        {options.map(o => (
          <div key={o.key} style={optStyle(sortKey === o.key)}
            onMouseEnter={e => (e.currentTarget.style.background = "var(--paper-2)")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            onClick={e => { e.stopPropagation(); setSortKey(sortKey === o.key ? "hs-asc" : o.key); setOpenMenu(""); }}>
            <span>{o.label}</span>
            {sortKey === o.key && <span style={{ color: "var(--indigo)", fontWeight: 700 }}>✓</span>}
          </div>
        ))}
      </div>
    ) : null
  );

  const fcTableHeader = (
    <div className="cz-pthead">
      <div>Deal</div>
      <div style={{ position: "relative", cursor: "pointer", color: colActive("mrr") ? "var(--indigo)" : undefined }} onClick={() => setOpenMenu(openMenu === "mrr" ? "" : "mrr")}>
        MRR <span style={{ fontSize: 10, marginLeft: 4, color: colActive("mrr") ? "var(--indigo)" : "var(--ink-3)" }}>▼</span>
        <SortDrop col="mrr" options={[{ key: "mrr-desc", label: "High → Low" }, { key: "mrr-asc", label: "Low → High" }]} />
      </div>
      <div>{CRM_SHORT} Cat.</div>
      <div style={{ position: "relative", cursor: "pointer", color: colActive("prob") ? "var(--indigo)" : undefined }} onClick={() => setOpenMenu(openMenu === "prob" ? "" : "prob")}>
        Prob <span style={{ fontSize: 10, marginLeft: 4, color: colActive("prob") ? "var(--indigo)" : "var(--ink-3)" }}>▼</span>
        <SortDrop col="prob" options={[{ key: "prob-desc", label: "High → Low" }, { key: "prob-asc", label: "Low → High" }]} />
      </div>
      <div style={{ position: "relative", cursor: "pointer", color: colActive("hs") || colActive("closzr") ? "var(--indigo)" : undefined }} onClick={() => setOpenMenu(openMenu === "close" ? "" : "close")}>
        {CRM_SHORT} | Closzr <span style={{ fontSize: 10, marginLeft: 4, color: colActive("hs") || colActive("closzr") ? "var(--indigo)" : "var(--ink-3)" }}>▼</span>
        <SortDrop col="close" options={[{ key: "hs-asc", label: `${CRM_SHORT} Earliest` }, { key: "hs-desc", label: `${CRM_SHORT} Latest` }, { key: "closzr-asc", label: "Closzr Earliest" }, { key: "closzr-desc", label: "Closzr Latest" }]} />
      </div>
      <div>Owner</div>
      <div></div>
    </div>
  );

  const viewMonthKey = (p: Panel) => p === "m0" ? cm : p === "m1" ? nmKey : m2Key;
  const matchHs = (d: ForecastDeal, mk: string) => mk === m2Key ? (d.closeDate ? d.closeDate >= mk : false) : (d.closeDate?.startsWith(mk) ?? false);
  const matchCz = (d: ForecastDeal, mk: string) => mk === m2Key ? (d.claudioCloseDate ? d.claudioCloseDate >= mk : false) : (d.claudioCloseDate?.startsWith(mk) ?? false);

  const applyView = (deals: ForecastDeal[]) => {
    if (viewFilter === "all") return deals;
    const mk = viewMonthKey(panel);
    if (viewFilter === "hs") return deals.filter(d => matchHs(d, mk));
    if (viewFilter === "closzr") return deals.filter(d => matchCz(d, mk));
    return deals.filter(d => matchHs(d, mk) && matchCz(d, mk));
  };

  const viewCounts = (deals: ForecastDeal[]) => {
    const mk = viewMonthKey(panel);
    let hs = 0, cz = 0, shared = 0;
    for (const d of deals) {
      const h = matchHs(d, mk), c = matchCz(d, mk);
      if (h) hs++;
      if (c) cz++;
      if (h && c) shared++;
    }
    return { all: deals.length, hs, cz, shared };
  };

  const dealDotColor = (d: ForecastDeal) => {
    const mk = viewMonthKey(panel);
    const h = matchHs(d, mk), c = matchCz(d, mk);
    if (h && c) return "var(--green)";
    if (c) return "var(--indigo)";
    if (h) return "var(--ink-2)";
    return undefined;
  };

  const renderDealRows = (deals: ForecastDeal[], showPush = false) =>
    sortDeals(applyView(deals)).map(d => (
      <FcRow key={d.id} d={d} open={expandedId === d.id} showPushChip={showPush}
        dotColor={dealDotColor(d)}
        onToggle={() => setExpandedId(expandedId === d.id ? null : d.id || null)} onOpen={onOpen} />
    ));

  const monthLabel = (offset: number) => {
    const d = new Date();
    d.setMonth(d.getMonth() + offset);
    return d.toLocaleString("en", { month: "short" });
  };

  return (
    <div className="cz-fc">
      {/* Toolbar */}
      <div className="cz-toolbar" style={{ marginBottom: 4 }}>
        <div className="cz-tb-title"><h2 className="display">Forecast</h2></div>
        <div style={{ flex: 1 }} />
        <MultiSelectTeam teams={pipelines} selected={pipelineFilters} onChange={v => { setPipelineFilters(v); setTeamFilters(new Set()); setRepFilter(""); }} allLabel="All Pipelines" />
        <MultiSelectTeam teams={teams} selected={teamFilters} onChange={v => { setTeamFilters(v); setRepFilter(""); }} />
        <select className="cz-native-select" value={repFilter} onChange={e => setRepFilter(e.target.value)}>
          <option value="">All {ROLE_LABELS.PAE}/{ROLE_LABELS.PBD}s</option>
          {reps.map((r: string) => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="cz-search">
          <Icon name="search" size={16} style={{ color: "var(--ink-3)" }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search deals…" />
        </label>
      </div>

      {/* KPI Cards */}
      <div className="cz-fc-kpis" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
        {/* Target */}
        <div className="cz-fc-kpi" style={{ textAlign: "center", justifyContent: "center" }}>
          <span style={{ ...kpiTitle, color: "var(--ink-2)" }}>Target</span>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 6 }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "center", gap: 6 }}>
              <span style={{ fontSize: 10, color: "var(--indigo)", fontWeight: 800, textTransform: "uppercase", letterSpacing: ".04em" }}>M0</span>
              <EditableTarget value={target} teamFilter={singleTeamFilter} targets={F.targets} teams={teams} canEdit={canEditTarget && teamFilters.size <= 1} fontSize={20} />
            </div>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "center", gap: 6 }}>
              <span style={{ fontSize: 10, color: "var(--ink-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em" }}>M1</span>
              <span className="display" style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-3)" }}>{fmtEur(targetM1)}</span>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "center", gap: 6 }}>
              <span style={{ fontSize: 10, color: "var(--ink-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em" }}>M2</span>
              <span className="display" style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-3)" }}>{fmtEur(targetM2)}</span>
            </div>
          </div>
        </div>

        {/* M0 */}
        <button className={"cz-fc-kpi clickable" + (panel === "m0" ? " sel" : "")} onClick={() => toggle("m0")} style={{ textAlign: "center" }}>
          <span style={{ ...kpiTitle, color: "var(--indigo)" }}>M0 · {monthLabel(0)}</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div className="cz-fc-kpi-v display" style={{ fontSize: 18 }}>{fmtEur(m0HsTotal)}</div>
              <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{m0Split.rep} deals</span>
            </div>
            <span style={{ color: "var(--ink-4)" }}>|</span>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div className="cz-fc-kpi-v display" style={{ fontSize: 18, color: "var(--indigo)" }}>{fmtEur(m0CloszrTotal)}</div>
              <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{m0Split.closzr} deals</span>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
            <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
            <span style={{ fontSize: 10.5, fontWeight: 700, color: "var(--ink-3)", whiteSpace: "nowrap" }}>{m0Split.shared} shared</span>
            <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
          </div>
          {target > 0 && (
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 2 }}>
              <div style={{ flex: 1, textAlign: "center" }}>
                <span className="display" style={{ fontSize: 18, fontWeight: 700, color: pctTone(pct(m0HsTotal, target)) }}>{pct(m0HsTotal, target)}%</span>
              </div>
              <span style={{ color: "var(--ink-4)" }}>|</span>
              <div style={{ flex: 1, textAlign: "center" }}>
                <span className="display" style={{ fontSize: 18, fontWeight: 700, color: pctTone(pct(m0CloszrTotal, target)) }}>{pct(m0CloszrTotal, target)}%</span>
              </div>
            </div>
          )}
        </button>

        {/* M1 */}
        <button className={"cz-fc-kpi clickable" + (panel === "m1" ? " sel" : "")} onClick={() => toggle("m1")} style={{ textAlign: "center" }}>
          <span style={{ ...kpiTitle, color: "var(--ink-2)" }}>M1 · {monthLabel(1)}</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div className="cz-fc-kpi-v display" style={{ fontSize: 18 }}>{fmtEur(m1HsTotal)}</div>
              <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{m1Split.rep} deals</span>
            </div>
            <span style={{ color: "var(--ink-4)" }}>|</span>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div className="cz-fc-kpi-v display" style={{ fontSize: 18, color: "var(--indigo)" }}>{fmtEur(m1CloszrTotal)}</div>
              <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{m1Split.closzr} deals</span>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
            <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
            <span style={{ fontSize: 10.5, fontWeight: 700, color: "var(--ink-3)", whiteSpace: "nowrap" }}>{m1Split.shared} shared</span>
            <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
          </div>
          {targetM1 > 0 && (
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 2 }}>
              <div style={{ flex: 1, textAlign: "center" }}>
                <span className="display" style={{ fontSize: 18, fontWeight: 700, color: pctTone(pct(m1HsTotal, targetM1)) }}>{pct(m1HsTotal, targetM1)}%</span>
              </div>
              <span style={{ color: "var(--ink-4)" }}>|</span>
              <div style={{ flex: 1, textAlign: "center" }}>
                <span className="display" style={{ fontSize: 18, fontWeight: 700, color: pctTone(pct(m1CloszrTotal, targetM1)) }}>{pct(m1CloszrTotal, targetM1)}%</span>
              </div>
            </div>
          )}
        </button>

        {/* M2 / Pushable */}
        <button className={"cz-fc-kpi clickable" + (panel === "m2" ? " sel amber" : "")} onClick={() => toggle("m2")} style={{ textAlign: "center" }}>
          <span style={{ ...kpiTitle, color: "var(--ink-2)" }}>M2 · {monthLabel(2)}</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div className="cz-fc-kpi-v display" style={{ fontSize: 18 }}>{fmtEur(m2HsTotal)}</div>
              <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{m2Split.rep} deals</span>
            </div>
            <span style={{ color: "var(--ink-4)" }}>|</span>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div className="cz-fc-kpi-v display" style={{ fontSize: 18, color: "var(--indigo)" }}>{fmtEur(m2CloszrTotal)}</div>
              <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{m2Split.closzr} deals</span>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
            <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
            <span style={{ fontSize: 10.5, fontWeight: 700, color: "var(--ink-3)", whiteSpace: "nowrap" }}>{m2Split.shared} shared</span>
            <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
          </div>
          {m2PushCount > 0 && (
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--amber-ink)", background: "var(--amber-tint)", padding: "3px 10px", borderRadius: "var(--r-pill)", alignSelf: "center", marginTop: 4 }}>
              {m2PushCount} deals M2 → M1 · {fmtEur(m2PushVal)}
            </div>
          )}
        </button>

        {/* Closed */}
        <button className={"cz-fc-kpi clickable" + (panel === "closed" ? " sel green" : "")} onClick={() => toggle("closed")} style={{ textAlign: "center" }}>
          <span style={{ ...kpiTitle, color: "var(--ink-2)" }}>Closed · {monthLabel(0)}</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div className="cz-fc-kpi-v display" style={{ fontSize: 18, color: "var(--green)" }}>{fmtEur(closedTotal)}</div>
              <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{fClosed.length} {WON_LABEL.toLowerCase()}</span>
            </div>
            <span style={{ color: "var(--ink-4)" }}>|</span>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div className="cz-fc-kpi-v display" style={{ fontSize: 18, color: "var(--red)" }}>{fmtEur(lostTotal)}</div>
              <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{fLost.length} {LOST_LABEL.toLowerCase()}</span>
            </div>
          </div>
          {target > 0 && (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
              </div>
              <div style={{ position: "relative", height: 6, background: "var(--card-2)", borderRadius: 3, overflow: "hidden", marginTop: 4 }}>
                <div style={{ height: "100%", width: `${Math.min(pct(closedTotal, target), 100)}%`, background: "var(--green)", borderRadius: 3, transition: "width .4s ease" }} />
              </div>
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--green)", marginTop: 2 }}>
                {fmtEur(closedTotal)} / {fmtEur(target)} · {pct(closedTotal, target)}%
              </span>
            </>
          )}
        </button>
      </div>

      {/* Deal list */}
      <div className="cz-card cz-fctablecard">
        {panel === "closed" ? (
          <div className="cz-ptable">
            {/* Won/Lost tab switcher */}
            <div style={{ display: "flex", gap: 0, borderBottom: "2px solid var(--line)" }}>
              <button onClick={() => { setClosedTab("won"); setExpandedId(null); }} style={{
                flex: 1, padding: "12px 20px", fontSize: 13, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em",
                border: "none", cursor: "pointer", transition: "all .15s",
                background: closedTab === "won" ? "var(--green-tint)" : "var(--card-2)",
                color: closedTab === "won" ? "var(--green)" : "var(--ink-3)",
                borderBottom: closedTab === "won" ? "2px solid var(--green)" : "2px solid transparent",
                marginBottom: -2,
              }}>{WON_LABEL} · {fClosed.length} deals · {fmtEur(closedTotal)}</button>
              <button onClick={() => { setClosedTab("lost"); setExpandedId(null); }} style={{
                flex: 1, padding: "12px 20px", fontSize: 13, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em",
                border: "none", cursor: "pointer", transition: "all .15s",
                background: closedTab === "lost" ? "var(--red-tint)" : "var(--card-2)",
                color: closedTab === "lost" ? "var(--red)" : "var(--ink-3)",
                borderBottom: closedTab === "lost" ? "2px solid var(--red)" : "2px solid transparent",
                marginBottom: -2,
              }}>{LOST_LABEL} · {fLost.length} deals · {fmtEur(lostTotal)}</button>
            </div>
            {closedTab === "won" ? (
              <>
                <div className="cz-pthead" style={{ gridTemplateColumns: "minmax(180px,1.4fr) 90px 90px 70px 130px 110px" }}>
                  <div>Deal</div><div>MRR</div><div>Closed</div><div>Cycle</div><div>Owner</div><div></div>
                </div>
                {fClosed.map((d, i) => (
                  <ClosedRow key={d.id || i} d={d} open={expandedId === d.id} onToggle={() => setExpandedId(expandedId === d.id ? null : d.id || null)} onOpen={onOpen} />
                ))}
                {!fClosed.length && <div className="cz-empty">No {WON_DISPLAY_LABEL.toLowerCase()} deals this month.</div>}
              </>
            ) : (
              <>
                <div className="cz-pthead" style={{ gridTemplateColumns: "minmax(180px,1.4fr) 90px 90px 70px 130px 110px" }}>
                  <div>Deal</div><div>MRR</div><div>Closed</div><div>Cycle</div><div>Owner</div><div></div>
                </div>
                {fLost.map((d, i) => (
                  <LostRow key={d.id || i} d={d} open={expandedId === d.id} onToggle={() => setExpandedId(expandedId === d.id ? null : d.id || null)} onOpen={onOpen} />
                ))}
                {!fLost.length && <div className="cz-empty">No {LOST_LABEL.toLowerCase()} deals this month.</div>}
              </>
            )}
          </div>
        ) : (
          <div className="cz-ptable">
            {/* Intro + view pills */}
            <div style={{ padding: "14px 20px 12px", borderBottom: "1px solid var(--line-2)" }}>
              <div style={{ display: "flex", gap: 20, marginBottom: 10, fontSize: 12.5, color: "var(--ink-3)" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--ink-2)", flex: "none" }} /><b style={{ color: "var(--ink-2)" }}>{CRM_SHORT} Forecast</b> — rep's close date</span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--indigo)", flex: "none" }} /><b style={{ color: "var(--indigo)" }}>Closzr Forecast</b> — AI predicted close date</span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--green)", flex: "none" }} /><b style={{ color: "var(--green)" }}>Shared</b> — both agree on the same month</span>
              </div>
              {(() => {
                const deals = panel === "m0" ? fm0 : panel === "m1" ? fm1 : fm2;
                const c = viewCounts(deals);
                const pills: { key: "all" | "hs" | "closzr" | "shared"; label: string; count: number; color: string }[] = [
                  { key: "all", label: "All", count: c.all, color: "var(--ink)" },
                  { key: "hs", label: `${CRM_SHORT} Forecast`, count: c.hs, color: "var(--ink)" },
                  { key: "closzr", label: "Closzr", count: c.cz, color: "var(--indigo)" },
                  { key: "shared", label: "Shared", count: c.shared, color: "var(--green)" },
                ];
                return (
                  <div className="cz-metric-seg">
                    {pills.map(p => (
                      <button key={p.key} className={viewFilter === p.key ? "on" : ""}
                        onClick={() => { setViewFilter(p.key); setExpandedId(null); }}
                        style={{ border: "none", cursor: "pointer", background: viewFilter === p.key ? "var(--card)" : "transparent", color: viewFilter === p.key ? p.color : "var(--ink-3)", boxShadow: viewFilter === p.key ? "var(--sh-xs)" : "none" }}>
                        {p.label} · {p.count}
                      </button>
                    ))}
                  </div>
                );
              })()}
            </div>
            {fcTableHeader}
            {panel === "m0" && renderDealRows(fm0)}
            {panel === "m1" && renderDealRows(fm1)}
            {panel === "m2" && renderDealRows(fm2, true)}
            {((panel === "m0" && !fm0.length) || (panel === "m1" && !fm1.length) || (panel === "m2" && !fm2.length)) && (
              <div className="cz-empty">No deals for these filters.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
