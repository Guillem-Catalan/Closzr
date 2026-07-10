/* ============================================================
   CLOSZR — PIPELINE (horizontal sales funnel)
   ============================================================ */
import { useState, useMemo } from "react";
import { Icon, StageChip, ProbBadge, Chip, TONE } from "../components";
import { useData } from "../../data/store";
import { STAGE_DISPLAY } from "../../display";
import { normalize, distinctTeams, distinctOwners, repNameToEmail } from "../../data/filters";

function fmtK(v: number | null | undefined){
  if (v==null) return "—";
  if (v>=1000) return "€"+(v/1000).toFixed(1)+"K";
  return "€"+Math.round(v);
}
function fmtMRRp(v: number | null | string | undefined){
  if (v==null || v==="—") return "—";
  if ((v as number)>=1000) return "€"+((v as number)/1000).toFixed(1)+"K";
  return "€"+Math.round(v as number);
}

/* recency: most recently contacted first */
function recency(r: any){
  const last = (r.last||"").toLowerCase();
  if (last==="hoy") return 0;
  const m = last.match(/(\d+)\s*d/);
  if (m) return +m[1];
  return 9999;
}

/* Continuous funnel ribbon — each segment connects to the next (right edge
   height = next stage's left edge height), forming a single flowing silhouette.
   Each segment stays individually clickable. */
function Funnel({ stages, metric, sel, onSelect }: { stages: any[]; metric: string; sel: string; onSelect: (k: string) => void }) {
  const PLOT = 130, PAD = 18, MINH = 26;
  const vals = stages.map(s => metric==="value" ? s.value : s.count);
  const maxV = Math.max(...vals);
  const hOf = (v: number) => MINH + (v/maxV)*(PLOT - PAD*2 - MINH);
  const heights = vals.map(hOf);

  return (
    <div className="cz-funnel2">
      {stages.map((st,i)=>{
        const t = TONE[st.tone] || TONE.ink;
        const hL = heights[i];
        const hR = heights[i+1] != null ? heights[i+1] : hL*0.72;
        const topL = (PLOT-hL)/2, topR = (PLOT-hR)/2;
        const on = sel===st.key;
        const stalePct = st.count ? st.stale/st.count : 0;
        // stale band sits at the bottom of the segment
        const sTopL = topL+hL-hL*stalePct, sTopR = topR+hR-hR*stalePct;
        return (
          <button key={st.key} className={"cz-f2"+(on?" on":"")} onClick={()=>onSelect(st.key)}>
            <div className="cz-f2-plot">
              <svg viewBox={`0 0 100 ${PLOT}`} preserveAspectRatio="none" width="100%" height={PLOT}>
                <polygon points={`0,${topL} 100,${topR} 100,${topR+hR} 0,${topL+hL}`}
                  fill={t.fg} fillOpacity={on?0.95:0.16} style={{transition:"fill-opacity .2s"}}/>
                <polygon points={`0,${topL} 100,${topR}`} fill="none" stroke={t.fg} strokeOpacity={on?1:0.5} strokeWidth="2.5" vectorEffect="non-scaling-stroke"/>
                {st.stale>0 && (
                  <polygon points={`0,${sTopL} 100,${sTopR} 100,${topR+hR} 0,${topL+hL}`}
                    fill="var(--red)" fillOpacity={on?0.55:0.22}/>
                )}
              </svg>
              <span className="cz-f2-count num" style={{color:on?"#fff":"var(--ink)"}}>
                {metric==="value"?fmtK(st.value):(st.count>=1000?(st.count/1000).toFixed(1)+"K":st.count.toLocaleString("es-ES"))}
              </span>
            </div>
            <div className="cz-f2-meta">
              <span className="cz-f2-label" style={{color:on?t.fg:"var(--ink-2)"}}>{st.label}</span>
              <span className="cz-f2-sub num">{metric==="value"?(st.count>=1000?(st.count/1000).toFixed(1)+"K":st.count)+" deals":fmtK(st.value)}</span>
              {st.stale>0 && <span className="cz-f2-stale num"><i/>{st.stale} parados</span>}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function abbrToFull(abbr: string): string {
  for (const [stage, info] of Object.entries(STAGE_DISPLAY)) {
    if (info.abbr === abbr || info.short === abbr) return stage;
  }
  return abbr;
}

function ClickableStage({ stage }: { stage: string }) {
  const [open, setOpen] = useState(false);
  const full = abbrToFull(stage);
  return (
    <span style={{ position: "relative", cursor: "pointer" }} onClick={e => { e.stopPropagation(); setOpen(!open); }} onBlur={() => setOpen(false)} tabIndex={0}>
      <StageChip stage={stage}/>
      {open && full !== stage && (
        <span style={{ position: "absolute", top: "100%", left: 0, marginTop: 4, padding: "4px 10px", background: "var(--ink)", color: "white", borderRadius: "var(--r-sm)", fontSize: 11, fontWeight: 600, whiteSpace: "nowrap", zIndex: 10, boxShadow: "var(--sh-md)" }}>{full}</span>
      )}
    </span>
  );
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

function PipeRow({ row, onOpen }: { row: any; onOpen: (row: any, tab: string) => void }) {
  const cdTone = closeDateTone(row.closeDateHs, row.closeDateClaudio);
  return (
    <div className={"cz-prow"+(row.stale?" stale":"")} onClick={()=>onOpen(row,"hist")} role="button" tabIndex={0}
      onKeyDown={e=>{if(e.key==="Enter")onOpen(row,"hist");}}>
      <div className="cz-pc-deal">
        {row.stale && <span className="cz-stale-dot" title="Parado"/>}
        <span className="cz-pc-name">{row.deal}</span>
      </div>
      <div className="cz-pc-stage"><ClickableStage stage={row.stage}/></div>
      <div className="num">{fmtMRRp(row.mrr)}</div>
      <div><ProbBadge value={row.prob}/></div>
      <div>{row.stale && <Icon name="clock" size={12} stroke={2} style={{color:"var(--red)",marginRight:4}}/>}{row.last}</div>
      <div className="cz-pc-close">
        <span className="num" style={{flex:1,textAlign:"right"}}>{fmtDate(row.closeDateHs)}</span>
        <span style={{color:"var(--ink-3)",margin:"0 4px",flex:"none"}}>|</span>
        <span className="num" style={{flex:1,textAlign:"left",color:cdTone}}>{fmtDate(row.closeDateClaudio)}</span>
      </div>
      <div className="cz-pc-owner">{row.owner!=="—"?row.owner:<span style={{color:"var(--ink-4)"}}>{"—"}</span>}</div>
      <div className="cz-pc-signal"><span>{row.signal}</span></div>
    </div>
  );
}

interface PipelineViewProps {
  onOpen: (row: any, tab: string) => void;
}

const OVERVIEW_STAGES = ["closing", "evaluating", "demo"];
const STAGE_TONE: Record<string, string> = { closing: "indigo", evaluating: "violet", demo: "teal" };

type HygieneKey = "stale" | "hsOverdue" | "closzrOverdue" | "hs10d" | "closzr10d" | "silent7d";
const HYGIENE_FILTERS: { key: HygieneKey; label: string }[] = [
  { key: "stale", label: "Stale" },
  { key: "hsOverdue", label: "HS overdue" },
  { key: "closzrOverdue", label: "Closzr overdue" },
  { key: "hs10d", label: "HS < 10d" },
  { key: "closzr10d", label: "Closzr < 10d" },
  { key: "silent7d", label: "+7d silent" },
];

const _today = () => new Date().toISOString().slice(0, 10);
const _in10d = () => new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10);

function hygieneMatch(key: HygieneKey, r: any): boolean {
  const today = _today();
  switch (key) {
    case "stale": return !!r.stale;
    case "hsOverdue": return !!(r.closeDateHs && r.closeDateHs.slice(0, 10) < today);
    case "closzrOverdue": return !!(r.closeDateClaudio && r.closeDateClaudio.slice(0, 10) < today);
    case "hs10d": { const d = r.closeDateHs?.slice(0, 10); return !!(d && d >= today && d <= _in10d()); }
    case "closzr10d": { const d = r.closeDateClaudio?.slice(0, 10); return !!(d && d >= today && d <= _in10d()); }
    case "silent7d": return (r._raw?.stale_days ?? 0) >= 7;
  }
}

function HygieneBar({ active, onToggle, rows }: { active: Set<HygieneKey>; onToggle: (k: HygieneKey) => void; rows: any[] }) {
  return (
    <div className="cz-hygiene">
      <span className="cz-hygiene-label">Hygiene</span>
      {HYGIENE_FILTERS.map(f => {
        const count = rows.filter(r => hygieneMatch(f.key, r)).length;
        const on = active.has(f.key);
        return (
          <button key={f.key} className={"cz-hygiene-pill" + (on ? " on" : "")} onClick={() => onToggle(f.key)}>
            {f.label}
            <span className="cz-hygiene-count num">{count}</span>
          </button>
        );
      })}
    </div>
  );
}

function StageSectionHeader({ label, count, mrr, tone, active, onClick }: { label: string; count: number; mrr: number; tone: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 10, width: "100%", padding: "10px 20px",
      background: active ? `var(--${tone}-tint)` : "var(--card-3)",
      border: "none", borderBottom: "1px solid var(--line-2)", cursor: "pointer", textAlign: "left",
    }}>
      <span style={{ fontWeight: 700, fontSize: 13, color: active ? `var(--${tone})` : "var(--ink-2)" }}>{label}</span>
      <Chip tone={tone as any} style={{ fontSize: 10 }}>{count} deals</Chip>
      <span className="num" style={{ fontSize: 12.5, fontWeight: 600, color: `var(--${tone})`, marginLeft: "auto" }}>{fmtK(mrr)}</span>
      <Icon name="chevDown" size={12} style={{ color: "var(--ink-3)", transform: active ? "none" : "rotate(-90deg)", transition: "transform .18s" }} />
    </button>
  );
}

function PipelineView({ onOpen }: PipelineViewProps) {
  const D = useData();
  const [metric,setMetric] = useState("count");
  const [sel,setSel] = useState("");
  const [q,setQ] = useState("");
  const [teamFilter,setTeamFilter] = useState("");
  const [repFilter,setRepFilter] = useState("");
  const [openSections,setOpenSections] = useState<Record<string,boolean>>({closing:true,evaluating:true,demo:true});
  const [hygiene,setHygiene] = useState<Set<HygieneKey>>(new Set());
  const toggleHygiene = (k: HygieneKey) => setHygiene(prev => { const n = new Set(prev); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const applyHygiene = (rows: any[]) => {
    if (!hygiene.size) return rows;
    return rows.filter(r => [...hygiene].every(k => hygieneMatch(k, r)));
  };

  // Compute available teams and reps from all deals
  const allDeals = useMemo(() => [...D.pipeline, ...D.pipelineAside].flatMap(s => s.rows), [D.pipeline, D.pipelineAside]);
  const teams = useMemo(() => distinctTeams(allDeals), [allDeals]);
  const reps = useMemo(() => distinctOwners(allDeals, teamFilter || undefined), [allDeals, teamFilter]);

  // Filter stages by team/rep
  const repEmail = repFilter ? repNameToEmail(repFilter) : "";
  const repNorm = repFilter ? normalize(repFilter) : "";
  const filterRow = (r: any) => {
    if (teamFilter && r.team !== teamFilter) return false;
    if (repFilter) {
      const ownerNorm = normalize(r.owner || "");
      const isOwner = ownerNorm === repNorm || ownerNorm.startsWith(repNorm + " ");
      const isAttendee = r.meetingPaes?.includes(repEmail);
      if (!isOwner && !isAttendee) return false;
    }
    return true;
  };

  const filteredPipeline = useMemo(() => D.pipeline.map(s => {
    const rows = s.rows.filter(filterRow);
    return { ...s, rows, count: rows.length, value: rows.reduce((a: number, r: any) => a + (r.mrr || 0), 0), stale: rows.filter((r: any) => r.stale).length };
  }), [D.pipeline, teamFilter, repFilter]);

  const filteredAside = useMemo(() => D.pipelineAside.map(s => {
    const rows = s.rows.filter(filterRow);
    return { ...s, rows, count: rows.length, value: rows.reduce((a: number, r: any) => a + (r.mrr || 0), 0), stale: rows.filter((r: any) => r.stale).length };
  }), [D.pipelineAside, teamFilter, repFilter]);

  const allStages = [...filteredPipeline, ...filteredAside];
  const totalDeals = allStages.reduce((a,s)=>a+s.count,0);
  const totalValue = allStages.reduce((a,s)=>a+s.value,0);
  const totalStale = allStages.reduce((a,s)=>a+s.stale,0);

  const cur = allStages.find(s=>s.key===sel) || filteredPipeline[0];
  let rows = cur ? [...cur.rows].sort((a,b)=>recency(a)-recency(b)) : [];
  rows = applyHygiene(rows);
  if (q.trim()){ const t=q.toLowerCase(); rows = rows.filter(r=>r.deal.toLowerCase().includes(t)||(r.owner||"").toLowerCase().includes(t)||(r.signal||"").toLowerCase().includes(t)); }

  return (
    <div className="cz-pipe">
      {/* toolbar */}
      <div className="cz-toolbar">
        <div className="cz-tb-title">
          <h2 className="display">Pipeline</h2>
          <span className="cz-tb-meta num">{totalDeals.toLocaleString("es-ES")} deals · {fmtK(totalValue)} pipeline</span>
        </div>
        <div style={{flex:1}}/>
        <label className="cz-search">
          <Icon name="search" size={16} style={{color:"var(--ink-3)"}}/>
          <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar en este stage…"/>
        </label>
        <div className="cz-filters">
          <select className="cz-native-select" value={teamFilter} onChange={e=>{setTeamFilter(e.target.value);setRepFilter("");}}>
            <option value="">All Teams</option>
            {teams.map((t: string)=><option key={t} value={t}>{t}</option>)}
          </select>
          <select className="cz-native-select" value={repFilter} onChange={e=>setRepFilter(e.target.value)}>
            <option value="">All PAEs/PBDs</option>
            {reps.map((r: string)=><option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </div>

      {/* FUNNEL */}
      <div className="cz-funnel-card">
        <div className="cz-funnel-head">
          <span className="eyebrow">Funnel de ventas</span>
          <span className="cz-funnel-hint">Selecciona un stage para ver sus deals</span>
          <span style={{flex:1}}/>
          <span className="cz-stale-total"><Icon name="clock" size={13} stroke={2}/> {totalStale.toLocaleString("es-ES")} parados</span>
          <div className="cz-metric-seg">
            <button className={metric==="count"?"on":""} onClick={()=>setMetric("count")}>Nº deals</button>
            <button className={metric==="value"?"on":""} onClick={()=>setMetric("value")}>Valor €</button>
          </div>
        </div>

        <Funnel stages={filteredPipeline} metric={metric} sel={sel} onSelect={k => setSel(sel === k ? "" : k)}/>

        <div className="cz-funnel-aside">
          <span className="cz-aside-label">Fuera del funnel</span>
          {filteredAside.map((st: any)=>(
            <button key={st.key} className={"cz-aside-chip"+(sel===st.key?" on":"")} onClick={()=>setSel(sel===st.key?"":st.key)}>
              {st.label} <b className="num">{st.count}</b>
              {st.stale>0 && <span className="cz-aside-stale num">{st.stale} stale</span>}
            </button>
          ))}
        </div>
      </div>

      {/* DEALS */}
      {sel ? (
        <div className="cz-stage-deals">
          <div className="cz-stage-head">
            <h3 className="display">{cur.label}</h3>
            <span className="cz-tb-meta num">{cur.count.toLocaleString("es-ES")} deals · {fmtK(cur.value)}</span>
          </div>
          <HygieneBar active={hygiene} onToggle={toggleHygiene} rows={cur.rows}/>

          <div className="cz-ptable">
            <div className="cz-pthead">
              <div>Deal</div>
              <div>Stage</div>
              <div>MRR</div>
              <div>Prob</div>
              <div>Last contacted</div>
              <div>HS | Closzr</div>
              <div>Owner</div>
              <div>Next Step</div>
            </div>
            <div className="cz-prows">
              {rows.map((r,i)=><PipeRow key={i} row={r} onOpen={onOpen}/>)}
              {!rows.length && <div className="cz-empty">Sin deals{hygiene.size?" con estos filtros":""} en {cur.label}{q?` para "${q}"`:""}.</div>}
            </div>
          </div>
        </div>
      ) : (
        <div className="cz-stage-deals">
          <div className="cz-stage-head">
            <h3 className="display">Overview</h3>
            <span className="cz-tb-meta num">Closing · Evaluating · Demo</span>
          </div>
          <HygieneBar active={hygiene} onToggle={toggleHygiene} rows={OVERVIEW_STAGES.flatMap(k => (allStages.find(s => s.key === k)?.rows || []))}/>
          <div className="cz-ptable">
            <div className="cz-pthead">
              <div>Deal</div>
              <div>Stage</div>
              <div>MRR</div>
              <div>Prob</div>
              <div>Last contacted</div>
              <div>HS | Closzr</div>
              <div>Owner</div>
              <div>Next Step</div>
            </div>
            {OVERVIEW_STAGES.map(stKey => {
              const st = allStages.find(s => s.key === stKey);
              if (!st || !st.count) return null;
              const sectionOpen = openSections[stKey] ?? true;
              let sRows = applyHygiene([...st.rows].sort((a,b) => recency(a) - recency(b)));
              if (q.trim()){ const t=q.toLowerCase(); sRows = sRows.filter(r=>r.deal.toLowerCase().includes(t)||(r.owner||"").toLowerCase().includes(t)||(r.signal||"").toLowerCase().includes(t)); }
              return (
                <div key={stKey}>
                  <StageSectionHeader
                    label={st.label} count={sRows.length} mrr={sRows.reduce((a,r) => a + (r.mrr || 0), 0)}
                    tone={STAGE_TONE[stKey] || "ink"} active={sectionOpen}
                    onClick={() => setOpenSections(p => ({...p, [stKey]: !p[stKey]}))}
                  />
                  {sectionOpen && (
                    <div className="cz-prows">
                      {sRows.map((r,i) => <PipeRow key={i} row={r} onOpen={onOpen}/>)}
                      {!sRows.length && <div className="cz-empty">Sin deals{hygiene.size?" con estos filtros":""} en {st.label}.</div>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default PipelineView;
