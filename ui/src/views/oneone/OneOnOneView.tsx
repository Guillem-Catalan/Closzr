/* ============================================================
   CLOSZR — 1:1 REVIEW (TL + PAE coaching)
   ============================================================ */
import { useState } from "react";
import { Icon, Chip, StageChip, ProbBadge, Avatar, TONE } from "../components";
import { useData } from "../../data/store";

function fmtK1(v: number | null | undefined){
  if (v==null) return "—";
  if (v>=1000) return "€"+(v/1000).toFixed(v%1000===0?0:1)+"K";
  return "€"+v;
}

function MeddicBar({ label, score, base: _base }: { label: string; score: number; base: number }) {
  const tone = score>=4 ? "green" : score>=2.5 ? "amber" : "red";
  const c = TONE[tone].fg;
  return (
    <div className="cz-mh-row">
      <div className="cz-mh-top">
        <span className="cz-mh-label">{label}</span>
        <span className="cz-mh-score num" style={{color:c}}>{score.toFixed(1)}<small>/5</small></span>
      </div>
      <div className="cz-mh-track"><div style={{width:(score/5*100)+"%",background:c}}/></div>
    </div>
  );
}

interface OneOnOneViewProps {
  onOpen: (row: any, tab: string) => void;
}

function OneOnOneView({ onOpen }: OneOnOneViewProps) {
  const D = useData();
  const O = D.oneOnOne;
  const [rep,setRep] = useState(O.rep);
  const [sortBy,setSortBy] = useState("mrr");
  const [hygieneOpen,setHygieneOpen] = useState<string|null>(null);

  const initials = (n: string) => n.split(" ").map(w=>w[0]).slice(0,2).join("").toUpperCase();
  const top10 = [...O.top10].sort((a: any, b: any)=> sortBy==="mrr" ? (b.mrr-a.mrr) : (b.prob-a.prob));
  const openDeal = (r: any)=> onOpen({ id:r.id, deal:r.deal, stage:r.stage, mrr:r.mrr, prob:r.prob, score:r.score||2.8, last:"Hace 3d", trend:r.prob||0, owner:rep, hora:"—" }, "hist");
  void Math.max(...O.weakness.map((w: any)=>w.count));

  return (
    <div className="cz-oo">
      {/* toolbar */}
      <div className="cz-toolbar">
        <div className="cz-tb-title">
          <h2 className="display">1:1 Review</h2>
        </div>
        <label className="cz-rep-select">
          <Avatar initials={initials(rep)} size={26} name={rep}/>
          <select value={rep} onChange={e=>setRep(e.target.value)}>
            {O.reps.map((r: string)=><option key={r}>{r}</option>)}
          </select>
          <Icon name="chevDown" size={15} style={{color:"var(--ink-3)"}}/>
        </label>
        <span className="cz-tb-meta num">{O.activeDeals} deals activos · {fmtK1(O.pipeline)} pipeline</span>
      </div>

      <div className="cz-oo-grid">
        {/* LEFT */}
        <div className="cz-col">
          {/* Top 10 */}
          <div className="cz-card cz-pad">
            <div className="cz-ovh">
              <span className="eyebrow">Top 10 deals del rep</span>
              <div className="cz-metric-seg" style={{marginLeft:"auto"}}>
                <button className={sortBy==="mrr"?"on":""} onClick={()=>setSortBy("mrr")}>Por MRR</button>
                <button className={sortBy==="prob"?"on":""} onClick={()=>setSortBy("prob")}>Por prob.</button>
              </div>
            </div>
            <div className="cz-top10">
              {top10.map((r: any, i: number)=>(
                <button key={r.id} className="cz-t10" onClick={()=>openDeal(r)}>
                  <span className="cz-t10-rank num">{i+1}</span>
                  <span className="cz-t10-name">{r.deal}</span>
                  <StageChip stage={r.stage}/>
                  <span style={{flex:1}}/>
                  <span className="cz-t10-mrr num">{fmtK1(r.mrr)}</span>
                  <ProbBadge value={r.prob}/>
                  <Icon name="arrowRight" size={14} stroke={2} style={{color:"var(--ink-4)"}}/>
                </button>
              ))}
            </div>
          </div>

          {/* TL action */}
          <div className="cz-card cz-pad">
            <div className="cz-ovh">
              <span className="eyebrow">Acciones del TL</span>
              <Chip tone="red" style={{marginLeft:"auto"}}>{O.tlActions.length} a revisar</Chip>
            </div>
            <p className="cz-oo-hint">Dónde el TL puede desbloquear o ayudar al rep en esta sesión.</p>
            <div className="cz-tlactions">
              {O.tlActions.map((a: any, i: number)=>(
                <button key={i} className="cz-tla" onClick={()=>openDeal(a)}>
                  <span className={"cz-tla-ic "+(a.sev==="alto"?"hi":"")}><Icon name="alert" size={14} stroke={2}/></span>
                  <div className="cz-tla-body">
                    <div className="cz-tla-top">
                      <span className="cz-tla-deal">{a.deal}</span>
                      <Chip tone={a.sev==="alto"?"red":"amber"} style={{fontSize:10.5}}>{a.flag}</Chip>
                      <span style={{flex:1}}/>
                      <StageChip stage={a.stage}/>
                      <span className="cz-tla-mrr num">{fmtK1(a.mrr)}</span>
                    </div>
                    <p className="cz-tla-text">{a.text}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Methodology */}
          <div className="cz-card cz-pad">
            <div className="cz-ovh">
              <span className="eyebrow">Higiene de pipeline</span>
              <span className="cz-tb-meta num" style={{marginLeft:"auto"}}>{O.methodologyOpen} deals abiertos</span>
            </div>
            <div className="cz-method">
              {O.methodology.map((m: any, i: number)=>{
                const isOpen = hygieneOpen === m.key;
                return (
                  <div key={i}>
                    <button className="cz-method-row" onClick={()=>setHygieneOpen(isOpen?null:m.key)}>
                      <span className={"cz-method-n num "+m.tone}>{m.n}</span>
                      <span className="cz-method-label">{m.label}</span>
                      <Icon name="chevDown" size={15} style={{color:"var(--ink-4)",transform:isOpen?"none":"rotate(-90deg)",transition:"transform .18s"}}/>
                    </button>
                    {isOpen && m.deals && (
                      <div style={{padding:"8px 6px 12px",display:"flex",flexDirection:"column",gap:4}}>
                        {m.deals.slice(0,15).map((d: any, j: number)=>(
                          <button key={j} className="cz-t10" onClick={()=>openDeal(d)} style={{padding:"6px"}}>
                            <span className="cz-t10-name" style={{maxWidth:200}}>{d.deal}</span>
                            <span style={{flex:1}}/>
                            <span className="cz-t10-mrr num">{fmtK1(d.mrr)}</span>
                            <StageChip stage={d.stage}/>
                          </button>
                        ))}
                        {m.deals.length>15 && <span style={{fontSize:12,color:"var(--ink-3)",paddingLeft:6}}>+{m.deals.length-15} más</span>}
                      </div>
                    )}
                  </div>
                );
              })}
              {!O.methodology.length && <p className="cz-oo-hint">Sin problemas de higiene detectados.</p>}
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="cz-col">
          {/* MEDDIC heatmap */}
          <div className="cz-card cz-pad">
            <div className="cz-ovh">
              <span className="eyebrow">Perfil MEDDIC del rep</span>
            </div>
            <p className="cz-oo-hint">Media en {O.meddicBase} deals post-MEDDPICC</p>
            <div className="cz-mh">
              {O.meddic.map((m: any, i: number)=><MeddicBar key={i} label={m.key} score={m.score} base={O.meddicBase}/>)}
            </div>
            <div className="cz-coach">
              <span className="cz-coach-ic"><Icon name="sparkle" size={15}/></span>
              <div>
                <span className="eyebrow" style={{color:"var(--amber-ink)"}}>Patrón de debilidad</span>
                <p>{O.meddicNote}</p>
              </div>
            </div>
          </div>

          {/* Weakness patterns */}
          <div className="cz-card cz-pad">
            <div className="cz-ovh">
              <span className="eyebrow">Dónde fallan los deals</span>
            </div>
            <p className="cz-oo-hint">Deals con score &lt;4 sobre {O.meddicBase} post-MEDDPICC</p>
            <div className="cz-weak">
              {O.weakness.map((w: any, i: number)=>{
                const pct = Math.round(w.count/O.meddicBase*100);
                const tone = pct>=70?"red":pct>=40?"amber":"green";
                return (
                  <div className="cz-weak-row" key={i}>
                    <span className="cz-weak-label">{w.label}</span>
                    <div className="cz-weak-track"><div style={{width:pct+"%",background:TONE[tone].fg}}/></div>
                    <span className="cz-weak-count num"><b>{w.count}</b>/{O.meddicBase}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OneOnOneView;
