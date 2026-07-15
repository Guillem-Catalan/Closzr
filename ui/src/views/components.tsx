/* ============================================================
   CLOSZR — shared primitives
   ============================================================ */
import { type CSSProperties, useState, useEffect, useRef } from "react";
import { useData } from "../data/store";

/* ---------- tone -> css vars ---------- */
export const TONE: Record<string, { bg: string; fg: string }> = {
  indigo: { bg:"var(--indigo-tint)",  fg:"var(--indigo-700)" },
  blue:   { bg:"var(--blue-tint)",    fg:"#235fa8" },
  violet: { bg:"var(--violet-tint)",  fg:"#5a3eb0" },
  amber:  { bg:"var(--amber-tint)",   fg:"var(--amber-ink)" },
  green:  { bg:"var(--green-tint)",   fg:"var(--green-ink)" },
  teal:   { bg:"var(--teal-tint)",    fg:"#0f6c6f" },
  red:    { bg:"var(--red-tint)",     fg:"var(--red-ink)" },
  ink:    { bg:"#EEEAE1",             fg:"var(--ink-2)" },
};

/* ---------- Icon (line, 1.75 stroke) ---------- */
export const PATHS: Record<string, string> = {
  x:           "M6 6l12 12M18 6L6 18",
  arrowRight:  "M5 12h14M13 6l6 6-6 6",
  arrowLeft:   "M19 12H5M11 6l-6 6 6 6",
  arrowUpRight:"M7 17L17 7M9 7h8v8",
  building:    "M4 21V5a1 1 0 011-1h9a1 1 0 011 1v16M15 21V9h4a1 1 0 011 1v11M8 8h3M8 12h3M8 16h3",
  target:      "M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0M12 12m-5 0a5 5 0 1010 0 5 5 0 10-10 0M12 12m-1 0a1 1 0 102 0 1 1 0 10-2 0",
  signal:      "M4 18a14 14 0 0114-14M4 18a8 8 0 018-8M5 18h.01",
  alert:       "M12 9v4M12 17h.01M10.3 3.9L2.4 18a2 2 0 001.7 3h15.8a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  clock:       "M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0M12 7v5l3 2",
  calendar:    "M4 7a2 2 0 012-2h12a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2zM4 10h16M8 3v4M16 3v4",
  users:       "M16 19v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2M9 9a3.5 3.5 0 100-7 3.5 3.5 0 000 7M22 19v-2a4 4 0 00-3-3.87M16 2.13A4 4 0 0119 6a4 4 0 01-3 3.87",
  phone:       "M22 16.9v3a2 2 0 01-2.2 2 19.8 19.8 0 01-8.6-3.1 19.5 19.5 0 01-6-6A19.8 19.8 0 012 4.2 2 2 0 014 2h3a2 2 0 012 1.7c.1.9.4 1.8.7 2.6a2 2 0 01-.5 2.1L8.1 9.6a16 16 0 006 6l1.2-1.1a2 2 0 012.1-.5c.8.3 1.7.6 2.6.7A2 2 0 0122 16.9z",
  mail:        "M3 7a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2zM3 7l9 6 9-6",
  calculator:  "M6 3h12a1 1 0 011 1v16a1 1 0 01-1 1H6a1 1 0 01-1-1V4a1 1 0 011-1zM8 7h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15v2",
  presentation:"M3 4h18M4 4v10a1 1 0 001 1h14a1 1 0 001-1V4M12 15v4M9 21h6",
  shield:      "M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z",
  book:        "M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 5v14",
  file:        "M14 3v5h5M7 3h8l5 5v11a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z",
  trendUp:     "M3 17l6-6 4 4 8-8M21 7v5M21 7h-5",
  search:      "M11 11m-7 0a7 7 0 1014 0 7 7 0 10-14 0M21 21l-4-4",
  filter:      "M3 5h18l-7 8v6l-4 2v-8z",
  sparkle:     "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  external:    "M14 4h6v6M20 4l-9 9M18 13v5a1 1 0 01-1 1H6a1 1 0 01-1-1V7a1 1 0 011-1h5",
  plus:        "M12 5v14M5 12h14",
  message:     "M21 11.5a8.5 8.5 0 01-12.2 7.6L3 21l1.9-5.8A8.5 8.5 0 1121 11.5z",
  note:        "M4 4h16v12l-4 4H4zM16 20v-4h4",
  chevDown:    "M6 9l6 6 6-6",
  chevRight:   "M9 6l6 6-6 6",
  layers:      "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5",
  check:       "M5 12l5 5L20 7",
  flag:        "M5 21V4m0 0h11l-1.5 4L16 12H5",
  award:       "M8.21 13.89L7 23l5-3 5 3-1.21-9.12M12 15a7 7 0 100-14 7 7 0 000 14z",
  xCircle:     "M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0M15 9l-6 6M9 9l6 6",
  compass:     "M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0M15.5 8.5l-2 5-5 2 2-5z",
  route:       "M6 19a3 3 0 100-6 3 3 0 000 6zM18 11a3 3 0 100-6 3 3 0 000 6zM18 8h-5a4 4 0 00-4 4v4",
  panelLeft:   "M3 3h18v18H3zM9 3v18",
  settings:    "M12.22 2h-.44a2 2 0 00-2 2v.18a2 2 0 01-1 1.73l-.43.25a2 2 0 01-2 0l-.15-.08a2 2 0 00-2.73.73l-.22.38a2 2 0 00.73 2.73l.15.1a2 2 0 011 1.72v.51a2 2 0 01-1 1.74l-.15.09a2 2 0 00-.73 2.73l.22.38a2 2 0 002.73.73l.15-.08a2 2 0 012 0l.43.25a2 2 0 011 1.73V20a2 2 0 002 2h.44a2 2 0 002-2v-.18a2 2 0 011-1.73l.43-.25a2 2 0 012 0l.15.08a2 2 0 002.73-.73l.22-.39a2 2 0 00-.73-2.73l-.15-.08a2 2 0 01-1-1.74v-.5a2 2 0 011-1.74l.15-.09a2 2 0 00.73-2.73l-.22-.38a2 2 0 00-2.73-.73l-.15.08a2 2 0 01-2 0l-.43-.25a2 2 0 01-1-1.73V4a2 2 0 00-2-2zM12 15a3 3 0 100-6 3 3 0 000 6z",
};

interface IconProps {
  name: string;
  size?: number;
  stroke?: number;
  style?: CSSProperties;
  className?: string;
}

export function Icon({ name, size = 18, stroke = 1.75, style, className }: IconProps) {
  const d = PATHS[name];
  if (!d) return null;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
      style={style} className={className} aria-hidden>
      {d.split("M").filter(Boolean).map((seg, i) => <path key={i} d={"M" + seg} />)}
    </svg>
  );
}

/* ---------- Chip / Pill ---------- */
interface ChipProps {
  tone?: string;
  children: React.ReactNode;
  dot?: boolean;
  style?: CSSProperties;
  soft?: boolean;
}

export function Chip({ tone = "ink", children, dot = false, style, soft = false }: ChipProps) {
  const t = TONE[tone] || TONE.ink;
  return (
    <span className="cz-chip" style={{
      display:"inline-flex", alignItems:"center", gap:6, whiteSpace:"nowrap",
      padding:"3px 9px", borderRadius:"var(--r-pill)", fontSize:12, fontWeight:600,
      background:soft?"transparent":t.bg, color:t.fg, lineHeight:1.4, ...style,
    }}>
      {dot && <span style={{width:6,height:6,borderRadius:99,background:t.fg,flex:"none"}}/>}
      {children}
    </span>
  );
}

/* ---------- StageChip ---------- */
interface StageChipProps {
  stage: string;
}

export function StageChip({ stage }: StageChipProps) {
  const D = useData();
  const tone = (D.STAGE[stage] || { tone: "ink" }).tone;
  return <Chip tone={tone}>{stage}</Chip>;
}

/* ---------- Probability badge ---------- */
interface ProbBadgeProps {
  value: number | null | undefined;
  big?: boolean;
}

export function ProbBadge({ value, big = false }: ProbBadgeProps) {
  if (value == null) return <span style={{color:"var(--ink-4)"}}>—</span>;
  const tone = value >= 50 ? "green" : value >= 25 ? "amber" : "red";
  const t = TONE[tone];
  return (
    <span className="num" style={{
      display:"inline-flex", alignItems:"center", justifyContent:"center",
      minWidth: big ? 54 : 42, padding: big ? "5px 10px" : "3px 8px", borderRadius:"var(--r-pill)",
      fontSize: big ? 15 : 12.5, fontWeight:700, background:t.bg, color:t.fg,
    }}>{value}%</span>
  );
}

/* ---------- Probability mini-bar (forecast style) ---------- */
interface ProbBarProps {
  value: number | null | undefined;
}

export function ProbBar({ value }: ProbBarProps) {
  if (value == null) return <span style={{color:"var(--ink-4)"}}>—</span>;
  const tone = value >= 70 ? "green" : value >= 40 ? "amber" : "red";
  return (
    <span style={{display:"inline-flex",alignItems:"center",gap:10}}>
      <span style={{width:78,height:6,borderRadius:99,background:"#ECE7DD",overflow:"hidden",display:"inline-block"}}>
        <span style={{display:"block",height:"100%",width:value+"%",background:TONE[tone].fg,borderRadius:99}}/>
      </span>
      <span className="num" style={{fontSize:13,fontWeight:700,minWidth:34}}>{value}%</span>
    </span>
  );
}

/* ---------- Trend ---------- */
interface TrendProps {
  value: number | null | undefined;
}

export function Trend({ value }: TrendProps) {
  if (value == null) return <span style={{color:"var(--ink-4)",fontSize:13}}>— new</span>;
  const up = value >= 0;
  return (
    <span className="num" style={{display:"inline-flex",alignItems:"center",gap:4,fontSize:13,fontWeight:600,
      color: up ? "var(--green)" : "var(--red)"}}>
      <span style={{fontSize:10}}>{up ? "▲" : "▼"}</span>{up ? "+" : ""}{value}
    </span>
  );
}

/* ---------- Score ---------- */
interface ScoreProps {
  value: number | null | undefined;
}

export function Score({ value }: ScoreProps) {
  if (value == null) return <span style={{color:"var(--ink-4)"}}>—</span>;
  const tone = value >= 4 ? "green" : value >= 3 ? "amber" : "red";
  return <span className="num" style={{fontWeight:700,color:TONE[tone].fg}}>{value.toFixed(1)}</span>;
}

/* ---------- Avatar ---------- */
const AV_COLORS = ["#3B4BD8","#1F8E91","#D8892A","#7C5BD8","#1F8A5B","#D8442F","#2E78D8"];

interface AvatarProps {
  initials: string;
  size?: number;
  name?: string;
}

export function Avatar({ initials, size = 30, name }: AvatarProps) {
  const idx = (initials || "?").charCodeAt(0) % AV_COLORS.length;
  const c = AV_COLORS[idx];
  return (
    <span title={name} style={{
      width:size, height:size, flex:"none", borderRadius:99, display:"inline-flex",
      alignItems:"center", justifyContent:"center", fontSize:size*0.36, fontWeight:700,
      background:c+"1E", color:c, letterSpacing:".01em",
    }}>{initials}</span>
  );
}

/* ---------- Section label with letter badge ---------- */
interface SectionLabelProps {
  letter?: string;
  tone?: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}

export function SectionLabel({ letter, tone = "indigo", children, right }: SectionLabelProps) {
  const t = TONE[tone] || TONE.indigo;
  return (
    <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:14}}>
      {letter && <span style={{width:22,height:22,borderRadius:6,background:t.bg,color:t.fg,
        display:"inline-flex",alignItems:"center",justifyContent:"center",fontSize:12,fontWeight:800}}>{letter}</span>}
      <span className="eyebrow" style={{letterSpacing:".1em"}}>{children}</span>
      <span style={{flex:1}}/>
      {right}
    </div>
  );
}

/* =========================================================
   MEDDIC Radar -- hexagonal radar chart (M E DC DP I C)
   ========================================================= */
export const MEDDIC_AXES = [
  { key:"M",    label:"M",    full:"Metrics",          color:"#7C5BD8" },
  { key:"E",    label:"E",    full:"Economic Buyer",   color:"#2E78D8" },
  { key:"DC",   label:"DC",   full:"Decision Criteria",color:"#D8892A" },
  { key:"DP",   label:"DP",   full:"Decision Process", color:"#D8442F" },
  { key:"I",    label:"I",    full:"Identify Pain",    color:"#1F8A5B" },
  { key:"C",    label:"C",    full:"Champion",         color:"#3B4BD8" },
  { key:"Comp", label:"CP", full:"Competition",      color:"#D8442F" },
];

interface MeddicRadarProps {
  scores: Record<string, number>;
  size?: number;
  max?: number;
}

export function MeddicRadar({ scores, size = 240, max = 5 }: MeddicRadarProps) {
  const cx = size/2, cy = size/2, R = size*0.36;
  const n = MEDDIC_AXES.length;
  const ang = (i: number) => (Math.PI*2*i/n) - Math.PI/2;
  const pt = (i: number, r: number): [number, number] => [cx + Math.cos(ang(i))*r, cy + Math.sin(ang(i))*r];
  const ringPath = (f: number) => MEDDIC_AXES.map((_, i) => { const [x, y] = pt(i, R*f); return (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1); }).join(" ") + "Z";
  const dataPath = MEDDIC_AXES.map((a, i) => { const [x, y] = pt(i, R*(scores[a.key]/max)); return (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1); }).join(" ") + "Z";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{display:"block"}}>
      {[0.2, 0.4, 0.6, 0.8, 1].map(f => (
        <path key={f} d={ringPath(f)} fill="none" stroke="var(--line)" strokeWidth="1"/>
      ))}
      {MEDDIC_AXES.map((_, i) => { const [x, y] = pt(i, R); return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--line)" strokeWidth="1"/>; })}
      <path d={dataPath} fill="rgba(59,75,216,.13)" stroke="var(--indigo)" strokeWidth="2" strokeLinejoin="round"/>
      {MEDDIC_AXES.map((a, i) => { const [x, y] = pt(i, R*(scores[a.key]/max)); return <circle key={i} cx={x} cy={y} r="4.5" fill={a.color} stroke="#fff" strokeWidth="2"/>; })}
      {MEDDIC_AXES.map((a, i) => { const [x, y] = pt(i, R+18); return (
        <text key={i} x={x} y={y} fontSize="13" fontWeight="700" fill={a.color}
          textAnchor="middle" dominantBaseline="middle" fontFamily="var(--font-display)">{a.label}</text>
      ); })}
    </svg>
  );
}

/* ---------- Sparkline / area line ---------- */
interface AreaLineProps {
  points: number[];
  w?: number;
  h?: number;
  min?: number;
  max?: number;
}

export function AreaLine({ points: rawPoints, w = 320, h = 120, min = 0, max = 100 }: AreaLineProps) {
  const points = (rawPoints || []).filter(p => p != null && !isNaN(p));
  if (points.length === 0) return null;
  const pad = 6, iw = w-pad*2, ih = h-pad*2;
  const range = max - min || 1;
  const xs = points.map((_, i) => pad + (points.length === 1 ? iw/2 : iw*i/(points.length-1)));
  const ys = points.map(p => pad + ih*(1-(p-min)/range));
  const line = xs.map((x, i) => (i ? "L" : "M") + x.toFixed(1) + " " + ys[i].toFixed(1)).join(" ");
  const area = line + ` L${xs[xs.length-1].toFixed(1)} ${(pad+ih)} L${xs[0].toFixed(1)} ${(pad+ih)} Z`;
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{display:"block",overflow:"visible"}}>
      <defs><linearGradient id="czarea" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="rgba(59,75,216,.22)"/><stop offset="100%" stopColor="rgba(59,75,216,0)"/>
      </linearGradient></defs>
      <path d={area} fill="url(#czarea)"/>
      <path d={line} fill="none" stroke="var(--indigo)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      {xs.map((x, i) => <circle key={i} cx={x} cy={ys[i]} r="4" fill="#fff" stroke="var(--indigo)" strokeWidth="2.5"/>)}
    </svg>
  );
}

/* ---------- fmtMRR helper (used by DealsTable, PipelineView) ---------- */
export function getInitials(name: string): string {
  return (name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
}

export function fmtMRR(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1000) return "€" + (v / 1000).toFixed(1) + "K";
  return "€" + Math.round(v);
}

/* ---------- MultiSelectTeam dropdown ---------- */
interface MultiSelectTeamProps {
  teams: string[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  allLabel?: string;
}

export function MultiSelectTeam({ teams, selected, onChange, allLabel = "All Teams" }: MultiSelectTeamProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  const label = selected.size === 0 ? allLabel
    : selected.size === 1 ? [...selected][0]
    : `${selected.size} teams`;

  const toggle = (t: string) => {
    const next = new Set(selected);
    if (next.has(t)) next.delete(t); else next.add(t);
    onChange(next);
  };

  const optStyle: CSSProperties = { padding: "7px 14px", fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", gap: 8 };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="cz-native-select" onClick={() => setOpen(!open)}
        style={{ display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}>
        {label}
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, marginTop: 4,
          background: "var(--card)", border: "1px solid var(--line)",
          borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,.12)",
          zIndex: 30, minWidth: 180, padding: "4px 0", maxHeight: 360, overflowY: "auto",
        }}>
          <div style={{ ...optStyle, fontWeight: selected.size === 0 ? 600 : 400 }}
            onMouseEnter={e => (e.currentTarget.style.background = "var(--paper-2)")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            onClick={() => onChange(new Set())}>
            <span style={{ width: 16, textAlign: "center", color: "var(--indigo)", fontWeight: 700 }}>{selected.size === 0 ? "✓" : ""}</span>
            {allLabel}
          </div>
          {teams.map(t => (
            <div key={t} style={{ ...optStyle, fontWeight: selected.has(t) ? 600 : 400 }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--paper-2)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              onClick={() => toggle(t)}>
              <span style={{ width: 16, textAlign: "center", color: "var(--indigo)", fontWeight: 700 }}>{selected.has(t) ? "✓" : ""}</span>
              {t}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
