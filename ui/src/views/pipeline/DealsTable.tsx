/* ============================================================
   CLOSZR — Deals table (Hoy)
   ============================================================ */
import { useState, useMemo } from "react";
import { Icon, StageChip, ProbBadge, Trend, Chip, fmtMRR } from "../components";
import { useData } from "../../data/store";
import { distinctTeams, distinctOwners, matchesTeam, matchesRep, matchesSearch } from "../../data/filters";

function RowJump({ onOpen }: { onOpen: (tab: string) => void }) {
  return (
    <div className="cz-rowjump">
      <button className="cz-jumpbtn primary" onClick={(e)=>{e.stopPropagation(); onOpen("hist");}}>
        Ver deal <Icon name="arrowRight" size={13} stroke={2}/>
      </button>
    </div>
  );
}

function DealRow({ row, onOpen }: { row: any; onOpen: (row: any, tab: string) => void }) {
  return (
    <div className="cz-drow" onClick={()=>onOpen(row, "hist")} role="button" tabIndex={0}
      onKeyDown={e=>{if(e.key==="Enter")onOpen(row,"hist");}}>
      <div className="cz-c-deal">
        <span className="cz-deal-name">{row.deal}</span>
        {row.sub && <span className="cz-deal-sub">{row.sub}</span>}
      </div>
      <div className="cz-c-stage"><StageChip stage={row.stage}/></div>
      <div className="cz-c-mrr num">{fmtMRR(row.mrr)}</div>
      <div className="cz-c-prob"><ProbBadge value={row.prob}/></div>
      <div className="cz-c-last">{row.last}</div>
      <div className="cz-c-trend"><Trend value={row.trend}/></div>
      <div className="cz-c-owner">{row.owner!=="—" ? row.owner : <span style={{color:"var(--ink-4)"}}>—</span>}</div>
      <div className="cz-c-hora num">{row.hora}</div>
      <RowJump onOpen={(tab)=>onOpen(row, tab)} />
    </div>
  );
}

function StageLegend() {
  const [open,setOpen] = useState(false);
  const D = useData();
  const stages = Object.keys(D.STAGE);
  return (
    <div className="cz-legend">
      <button className="cz-legend-head" onClick={()=>setOpen(o=>!o)}>
        <Icon name="chevDown" size={15} style={{transform:open?"none":"rotate(-90deg)",transition:"transform .18s"}}/>
        Leyenda de stages ({stages.length})
      </button>
      {open && (
        <div className="cz-legend-body">
          {stages.map(s=><Chip key={s} tone={(D.STAGE[s]||{}).tone}>{s}</Chip>)}
        </div>
      )}
    </div>
  );
}

interface DealsTableProps {
  onOpen: (row: any, tab: string) => void;
  view: string;
  setView: (v: string) => void;
}

function DealsTable({ onOpen, view, setView }: DealsTableProps) {
  const D = useData();
  const [q,setQ] = useState("");
  const [teamFilter,setTeamFilter] = useState("");
  const [repFilter,setRepFilter] = useState("");

  const allRows = useMemo(() => D.groups.flatMap(g => g.rows), [D.groups]);
  const teams = useMemo(() => distinctTeams(allRows), [allRows]);
  const reps = useMemo(() => distinctOwners(allRows, teamFilter || undefined), [allRows, teamFilter]);

  const groups = useMemo(()=>{
    let gs = D.groups.map(g => {
      let rows = g.rows;
      if (teamFilter) rows = rows.filter(r => matchesTeam(r, teamFilter));
      if (repFilter) rows = rows.filter(r => matchesRep(r.owner, repFilter, r.meetingPaes));
      if (q.trim()) rows = rows.filter(r => matchesSearch(q, r.deal, r.owner));
      return { ...g, rows, meta: `${rows.length} deals` };
    });
    return gs.filter(g => g.rows.length);
  },[q, D.groups, teamFilter, repFilter]);

  const totalDeals = groups.reduce((s, g) => s + g.rows.length, 0);
  const totalMrr = groups.reduce((s, g) => s + g.rows.reduce((s2, r) => s2 + (r.mrr || 0), 0), 0);

  return (
    <div className="cz-table-wrap">
      <div className="cz-toolbar">
        <div className="cz-tb-title">
          <h2 className="display">Deals</h2>
          <span className="cz-tb-meta num">{totalDeals} deals · {fmtMRR(totalMrr)} pipeline</span>
        </div>
        <div className="cz-seg">
          <button className={view==="hoy"?"on":""} onClick={()=>setView("hoy")}>Hoy</button>
          <button className={view==="pipeline"?"on":""} onClick={()=>setView("pipeline")}>Pipeline</button>
        </div>
        <div style={{flex:1}}/>
        <label className="cz-search">
          <Icon name="search" size={16} style={{color:"var(--ink-3)"}}/>
          <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar deals…"/>
        </label>
        <div className="cz-filters">
          <select className="cz-native-select" value={teamFilter} onChange={e=>{setTeamFilter(e.target.value);setRepFilter("");}}>
            <option value="">All Teams</option>
            {teams.map(t=><option key={t} value={t}>{t}</option>)}
          </select>
          <select className="cz-native-select" value={repFilter} onChange={e=>setRepFilter(e.target.value)}>
            <option value="">All PAEs/PBDs</option>
            {reps.map(r=><option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </div>

      <StageLegend/>

      <div className="cz-groups">
        {groups.map(g=>(
          <section key={g.id} className="cz-group">
            <header className={"cz-group-head tint-"+g.tint}>
              <span className="cz-group-title">{g.title}</span>
              <span className="cz-group-meta num">{g.meta}</span>
            </header>
            <div className="cz-thead">
              <div className="cz-c-deal">Deal</div>
              <div className="cz-c-stage">Stage</div>
              <div className="cz-c-mrr">MRR</div>
              <div className="cz-c-prob">Prob</div>
              <div className="cz-c-last">Last contact</div>
              <div className="cz-c-trend">Trend</div>
              <div className="cz-c-owner">Owner</div>
              <div className="cz-c-hora">Hora</div>
            </div>
            <div className="cz-rows">
              {g.rows.map(r=><DealRow key={r.id || r.deal} row={r} onOpen={onOpen}/>)}
            </div>
          </section>
        ))}
        {!groups.length && <div className="cz-empty">{q ? `Sin resultados para "${q}".` : "Sin meetings hoy."}</div>}
      </div>
    </div>
  );
}

export default DealsTable;
