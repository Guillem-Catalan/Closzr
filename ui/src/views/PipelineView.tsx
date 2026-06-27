/* ============================================================
   CLOSZR — PIPELINE (horizontal sales funnel)
   ============================================================ */
import { useState, useMemo } from "react";
import { Icon, StageChip, ProbBadge, Trend, TONE } from "./components";
import { useData } from "../data/store";
import { hubspotDealUrl, STAGE_DISPLAY } from "../display";
import { distinctTeams, distinctOwners, matchesTeam, matchesRep, repNameToEmail } from "../data/filters";

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
                {metric==="value"?fmtK(st.value):st.count.toLocaleString("es-ES")}
              </span>
            </div>
            <div className="cz-f2-meta">
              <span className="cz-f2-label" style={{color:on?t.fg:"var(--ink-2)"}}>{st.label}</span>
              <span className="cz-f2-sub num">{metric==="value"?st.count.toLocaleString("es-ES")+" deals":fmtK(st.value)}</span>
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

function PipeRow({ row, onOpen }: { row: any; onOpen: (row: any, tab: string) => void }) {
  return (
    <div className={"cz-prow"+(row.stale?" stale":"")} onClick={()=>onOpen(row,"hist")} role="button" tabIndex={0}
      onKeyDown={e=>{if(e.key==="Enter")onOpen(row,"hist");}}>
      <div className="cz-pc-deal">
        {row.stale && <span className="cz-stale-dot" title="Parado"/>}
        <span className="cz-pc-name">{row.deal}</span>
      </div>
      <div className="cz-pc-stage"><ClickableStage stage={row.stage}/></div>
      <div className="cz-pc-mrr num">{fmtMRRp(row.mrr)}</div>
      <div className="cz-pc-prob"><ProbBadge value={row.prob}/></div>
      <div className="cz-pc-last">{row.stale && <Icon name="clock" size={12} stroke={2} style={{color:"var(--red)",marginRight:4,verticalAlign:"-1px"}}/>}{row.last}</div>
      <div className="cz-pc-trend"><Trend value={row.trend}/></div>
      <div className="cz-pc-owner">{row.owner!=="—"?row.owner:<span style={{color:"var(--ink-4)"}}>{"—"}</span>}</div>
      <div className="cz-pc-signal">
        <Icon name="sparkle" size={13} stroke={2} style={{color:"var(--indigo)",flex:"none"}}/>
        <span>{row.signal}</span>
      </div>
      {row.hsId && (
        <a className="cz-pc-hs" href={hubspotDealUrl(row.hsId!)}
          target="_blank" rel="noopener noreferrer" title="Abrir en HubSpot"
          onClick={e => e.stopPropagation()}
          style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 24, height: 24, borderRadius: "var(--r-sm)", color: "var(--ink-3)", transition: "color .12s" }}>
          <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor"><path d="M17.63 13.31a3.3 3.3 0 01-1.63.43 3.37 3.37 0 01-3.37-3.37c0-.6.16-1.17.44-1.66l-2.3-2.3a.99.99 0 01-.15-.17 2.48 2.48 0 01-1.52.53V9.3a1.35 1.35 0 110-2.7V4.06A2.06 2.06 0 007.04 2a2.06 2.06 0 00-2.06 2.06v2.53a2.73 2.73 0 00.88 5.31h.05a2.7 2.7 0 001.79-.68l2.38 2.38a3.34 3.34 0 00-.46 1.69A3.37 3.37 0 0013 18.66a3.3 3.3 0 001.86-.57l2.74 2.74a1.1 1.1 0 001.56-1.56zM13 16.92a1.63 1.63 0 110-3.25 1.63 1.63 0 010 3.25z"/></svg>
        </a>
      )}
      <div className="cz-pc-go"><Icon name="arrowRight" size={15} stroke={2}/></div>
    </div>
  );
}

interface PipelineViewProps {
  onOpen: (row: any, tab: string) => void;
}

function PipelineView({ onOpen }: PipelineViewProps) {
  const D = useData();
  const [metric,setMetric] = useState("count");
  const [sel,setSel] = useState("evaluating");
  const [staleOnly,setStaleOnly] = useState(false);
  const [q,setQ] = useState("");
  const [teamFilter,setTeamFilter] = useState("");
  const [repFilter,setRepFilter] = useState("");

  // Compute available teams and reps from all deals
  const allDeals = useMemo(() => [...D.pipeline, ...D.pipelineAside].flatMap(s => s.rows), [D.pipeline, D.pipelineAside]);
  const teams = useMemo(() => distinctTeams(allDeals), [allDeals]);
  const reps = useMemo(() => distinctOwners(allDeals, teamFilter || undefined), [allDeals, teamFilter]);

  // Filter stages by team/rep
  const repEmail = repFilter ? repNameToEmail(repFilter) : "";
  const repNorm = repFilter ? repFilter.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "") : "";
  const filterRow = (r: any) => {
    if (teamFilter && r.team !== teamFilter) return false;
    if (repFilter) {
      const ownerNorm = (r.owner || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
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
  if (staleOnly) rows = rows.filter(r=>r.stale);
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

        <Funnel stages={filteredPipeline} metric={metric} sel={sel} onSelect={setSel}/>

        <div className="cz-funnel-aside">
          <span className="cz-aside-label">Fuera del funnel</span>
          {filteredAside.map((st: any)=>(
            <button key={st.key} className={"cz-aside-chip"+(sel===st.key?" on":"")} onClick={()=>setSel(st.key)}>
              {st.label} <b className="num">{st.count}</b>
              {st.stale>0 && <span className="cz-aside-stale num">{st.stale} stale</span>}
            </button>
          ))}
        </div>
      </div>

      {/* SELECTED STAGE DEALS */}
      <div className="cz-stage-deals">
        <div className="cz-stage-head">
          <h3 className="display">{cur.label}</h3>
          <span className="cz-tb-meta num">{cur.count.toLocaleString("es-ES")} deals · {fmtK(cur.value)}</span>
          <span style={{flex:1}}/>
          <button className={"cz-stale-toggle"+(staleOnly?" on":"")} onClick={()=>setStaleOnly(s=>!s)}>
            <Icon name="clock" size={14} stroke={2}/> Solo parados ({cur.stale})
          </button>
          <span className="cz-sortby">Ordenado por último contacto</span>
        </div>

        <div className="cz-ptable">
          <div className="cz-pthead">
            <div className="cz-pc-deal">Deal</div>
            <div className="cz-pc-stage">Stage</div>
            <div className="cz-pc-mrr">MRR</div>
            <div className="cz-pc-prob">Prob</div>
            <div className="cz-pc-last">Last contact</div>
            <div className="cz-pc-trend">Trend</div>
            <div className="cz-pc-owner">Owner</div>
            <div className="cz-pc-signal">Acción ahora</div>
            <div className="cz-pc-go"></div>
          </div>
          <div className="cz-prows">
            {rows.map((r,i)=><PipeRow key={i} row={r} onOpen={onOpen}/>)}
            {!rows.length && <div className="cz-empty">Sin deals {staleOnly?"parados ":""}en {cur.label}{q?` para "${q}"`:""}.</div>}
          </div>
          {cur.count>cur.rows.length && !q && !staleOnly && (
            <button className="cz-seeall">Ver los {cur.count.toLocaleString("es-ES")} deals de {cur.label} <Icon name="arrowRight" size={14} stroke={2}/></button>
          )}
        </div>
      </div>
    </div>
  );
}

export default PipelineView;
