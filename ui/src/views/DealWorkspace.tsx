/* ============================================================
   CLOSZR — Deal Workspace shell + HISTÓRICO view
   ============================================================ */
import { useState, useEffect } from "react";
import { Icon, StageChip, ProbBadge, Chip, Avatar, AreaLine, MEDDIC_AXES } from "./components";
import { AtlasView, NextView } from "./DealViews";
import { hubspotDealUrl } from "../display";

/* ---- persistent KPI pulse strip ---- */
function PulseStrip({ d }: { d: any }) {
  const items = [
    { k:"MRR", v:<span className="num">€{d.mrr}</span> },
    { k:"Close prob.", v:<ProbBadge value={d.prob} big/> },
    { k:"Close date", v:<span className="num">{d.closeDate}</span> },
    { k:"Forecast", v:<span className="num">{d.forecast}</span> },
    { k:"Empleados", v:<span className="num">{d.employees}</span> },
  ];
  return (
    <div className="cz-pulse">
      {items.map((it,i)=>(
        <div className="cz-pulse-item" key={i}>
          <span className="cz-pulse-k">{it.k}</span>
          <span className="cz-pulse-v display">{it.v}</span>
        </div>
      ))}
    </div>
  );
}

/* ---- Product section ---- */
const ACTION_TYPE_STYLE: Record<string, { label: string; tone: string }> = {
  pitch_from_pain: { label: "Pain detectado", tone: "green" },
  fix_pitch: { label: "Corregir pitch", tone: "red" },
  explore: { label: "Explorar", tone: "blue" },
  upsell: { label: "Upsell", tone: "amber" },
  bundle: { label: "Bundle", tone: "violet" },
  deepen: { label: "Profundizar", tone: "indigo" },
};

function ProductSection({ product }: { product: any }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const [assessmentOpen, setAssessmentOpen] = useState(false);
  const { products, assessment, expansion } = product;
  const allActions = [...(product.upsells || []).map((u: any) => ({ ...u, type: "upsell" })), ...(product.actions || [])];

  return (
    <section className="cz-card cmp">
      <div className="cz-ovh">
        <span className="eyebrow">Producto</span>
        <Chip tone="indigo">{products.length} módulo{products.length !== 1 ? "s" : ""}</Chip>
      </div>

      {/* Products discussed — chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
        {products.map((p: string) => (
          <Chip key={p} tone="ink" style={{ fontSize: 12, padding: "3px 10px" }}>{p}</Chip>
        ))}
      </div>

      {/* Expansion vs benchmark */}
      {expansion && (
        <div style={{ padding: "10px 14px", background: "var(--indigo-tint)", borderRadius: "var(--r-sm)", fontSize: 13, lineHeight: 1.55, color: "var(--indigo-700)", marginBottom: 14 }}>
          <span className="eyebrow" style={{ display: "block", marginBottom: 4, color: "var(--indigo)" }}>Expansión vs benchmark</span>
          {expansion}
        </div>
      )}

      {/* All actions as collapsible tags */}
      {allActions.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {allActions.map((a: any, i: number) => {
            const s = ACTION_TYPE_STYLE[a.type] || { label: a.type, tone: "ink" };
            const open = openIdx === i;
            return (
              <div key={i}>
                <button onClick={() => setOpenIdx(open ? null : i)} style={{
                  display: "flex", alignItems: "center", gap: 8, width: "100%",
                  padding: "8px 12px", background: open ? `var(--${s.tone}-tint)` : "var(--card-2)",
                  border: "none", borderRadius: "var(--r-sm)", cursor: "pointer",
                  borderLeft: `3px solid var(--${s.tone})`, transition: "background .15s",
                }}>
                  <Chip tone={s.tone} style={{ fontSize: 10, padding: "1px 7px", flex: "none" }}>{s.label}</Chip>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", textAlign: "left" }}>{a.product}</span>
                  <span style={{ flex: 1 }}/>
                  <Icon name="chevDown" size={13} style={{ color: "var(--ink-3)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .18s", flex: "none" }}/>
                </button>
                {open && (
                  <div style={{ padding: "10px 14px 12px 18px", fontSize: 12.5, lineHeight: 1.6, color: "var(--ink-2)" }}>
                    {a.text}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Assessment — collapsible */}
      {assessment && (
        <>
          <button onClick={() => setAssessmentOpen(!assessmentOpen)} style={{
            display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "10px 0 0",
            background: "none", border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600,
            color: "var(--ink-2)", borderTop: allActions.length ? "1px solid var(--line-2)" : "none", marginTop: allActions.length ? 10 : 0,
          }}>
            <Icon name="chevDown" size={13} style={{ color: "var(--ink-3)", transform: assessmentOpen ? "none" : "rotate(-90deg)", transition: "transform .18s" }}/>
            Evaluación completa
          </button>
          {assessmentOpen && (
            <p style={{ margin: "8px 0 0", fontSize: 13, lineHeight: 1.65, color: "var(--ink-2)", whiteSpace: "pre-line" }}>{assessment}</p>
          )}
        </>
      )}
    </section>
  );
}

/* =========================================================
   HISTÓRICO  (the hub) — reading order: summary first
   ========================================================= */
function HistView({ d, goTo }: { d: any; goTo: (tab: string) => void }) {
  const [openM,setOpenM] = useState<string | null>(null);
  const [openB,setOpenB] = useState<string | null>(null);
  const meddic = d.meddic || {};
  const atlas = d.atlas || {};
  const signal = d.signal || { kind: "PREP", text: "Sin acción pendiente", due: "—" };
  const howto = d.howto || { context: "—", text: "—" };
  const blockers = d.blockers || [];
  const signals = d.signals || [];
  const bant = d.bant || { overall: "Sin datos", items: [] };
  const timeline = (d.timeline || []).filter((t: any) => t && t.prob != null);
  const roadmap = d.roadmap || [];
  const nextSteps = d.nextSteps || [];
  const contacts = atlas.contacts || [];
  const meddicTotal = Object.values(meddic).reduce((a: number, b: any) => a + ((b as any)?.score || 0), 0);
  const lostDeal = (atlas.deals || []).find((x: any) => x.status === "PERDIDO");
  const sigIcon: Record<string, string> = { CALL:"phone", EMAIL:"mail", PREP:"presentation", ROI:"calculator", ESCALAR:"flag", FOLLOWUP:"mail" };
  const mddTone = meddicTotal >= 40 ? "green" : meddicTotal >= 24 ? "amber" : "red";

  const timelineProbs = timeline.map((t: any) => t.prob);
  const timelineMax = timelineProbs.length ? Math.max(40, ...timelineProbs) + 6 : 100;

  return (
    <div className="cz-ov" style={{animation:"cz-fade-up .3s var(--ease) both"}}>

      {/* ===== ACTION ZONE ===== */}
      <section className="cz-action">
        <div className="cz-action-now">
          <div className="cz-action-icon"><Icon name={sigIcon[signal.kind]||"sparkle"} size={20}/></div>
          <div className="cz-action-body">
            <div className="cz-action-eyebrow">Acción ahora <span className="cz-action-due">{signal.due}</span></div>
            <p className="cz-action-text">{signal.text}</p>
          </div>
          <button className="cz-btn-primary cz-action-btn" onClick={()=>goTo("next")}>
            Next steps · {nextSteps.length} <Icon name="arrowRight" size={15} stroke={2}/>
          </button>
        </div>
        <div className="cz-action-how">
          <span className="cz-how-label"><Icon name="compass" size={13} stroke={2}/> Cómo enfocarlo · {howto.context}</span>
          <p>{howto.text}</p>
        </div>
      </section>

      {/* ===== DIAGNOSTIC GRID ===== */}
      <div className="cz-ov-grid">

        {/* COL A — narrative */}
        <div className="cz-col">
          <section className="cz-card cmp">
            <div className="cz-ovh"><span className="eyebrow">Resumen del deal</span><span className="cz-ovh-by"><Icon name="sparkle" size={12}/> Closzr</span></div>
            <p className="cz-summary">{d.summary || "Sin resumen disponible."}</p>
          </section>

          {blockers.length > 0 && (
            <section className="cz-card cmp">
              <div className="cz-ovh"><span className="eyebrow">Qué bloquea el deal</span><Chip tone="red">{blockers.length}</Chip></div>
              <ul className="cz-flist">
                {blockers.map((b: any, i: number)=>(
                  <li key={i} className="cz-fitem blocker">
                    <span className="cz-fdot" style={{background: b.sev==="alto"?"var(--red)":"var(--amber)"}}/>
                    <span className="cz-ftext">{b.text}</span>
                  </li>
                ))}
              </ul>
              <button className="cz-atlas-hook" onClick={()=>goTo("atlas")}>
                <Icon name="book" size={16}/>
                <div><b>{lostDeal ? "Aprende del deal perdido anterior" : "Ver historial de la empresa"}</b><span>{lostDeal ? "Repasa por qué se perdió para no repetir el error" : "Contexto, contactos y deals anteriores en Atlas"}</span></div>
                <Icon name="arrowRight" size={15} stroke={2}/>
              </button>
            </section>
          )}

          {signals.length > 0 && (
            <section className="cz-card cmp">
              <div className="cz-ovh"><span className="eyebrow">Señales de compra</span><Chip tone="green">{signals.length}</Chip></div>
              <ul className="cz-flist">
                {signals.map((s: any, i: number)=>(
                  <li key={i} className="cz-fitem signal">
                    <span className="cz-fdot" style={{background:"var(--green)"}}/>
                    <span className="cz-ftext">{s.text}</span>
                    <Chip tone={s.strength==="Fuerte"?"green":"amber"} style={{flex:"none",fontSize:10,padding:"1px 7px"}}>{s.strength}</Chip>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        {/* COL B — qualification */}
        <div className="cz-col">
          <section className="cz-card cmp">
            <div className="cz-ovh"><span className="eyebrow">MEDDICC</span><Chip tone={mddTone}>{meddicTotal} / 70</Chip></div>
            <div className="cz-md-list">
              {MEDDIC_AXES.map(a=>{
                const md = meddic[a.key] || { score: 0, text: "Sin datos" };
                const sc = md.score || 0;
                const open = openM===a.key;
                return (
                  <div key={a.key} className={"cz-md"+(open?" open":"")}>
                    <button className="cz-md-row" onClick={()=>setOpenM(open?null:a.key)}>
                      <span className="cz-md-badge" style={{background:a.color}}>{a.label}</span>
                      <span className="cz-md-name">{a.full}</span>
                      <span className="cz-md-bar"><span style={{width:(sc*10)+"%",background:a.color}}/></span>
                      <span className="cz-md-score num">{sc}<small>/10</small></span>
                      <Icon name="chevDown" size={13} style={{color:"var(--ink-3)",transform:open?"none":"rotate(-90deg)",transition:"transform .18s"}}/>
                    </button>
                    {open && <p className="cz-md-text">{md.text}</p>}
                  </div>
                );
              })}
            </div>
          </section>

          {d.product && d.product.products.length > 0 && (
            <ProductSection product={d.product}/>
          )}

          {bant.items.length > 0 && (
            <section className="cz-card cmp">
              <div className="cz-ovh"><span className="eyebrow">BANT</span></div>
              <p className="cz-bant-overall">{bant.overall}</p>
              <div className="cz-md-list">
                {bant.items.map((it: any)=>{
                  const open=openB===it.key;
                  const bantColor: Record<string, string> = {B:"#2E78D8",A:"#7C5BD8",N:"#1F8A5B",T:"#D8892A"};
                  return (
                    <div key={it.key} className={"cz-md"+(open?" open":"")}>
                      <button className="cz-md-row bant" onClick={()=>setOpenB(open?null:it.key)}>
                        <span className="cz-md-badge" style={{background:bantColor[it.key]||"var(--ink-2)"}}>{it.key}</span>
                        <span className="cz-md-name">{it.label}</span>
                        <Chip tone={it.tone} style={{flex:"none"}}>{it.status}</Chip>
                        <Icon name="chevDown" size={13} style={{color:"var(--ink-3)",transform:open?"none":"rotate(-90deg)",transition:"transform .18s"}}/>
                      </button>
                      {open && <p className="cz-md-text">{it.text}</p>}
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>

        {/* COL C — trajectory + context */}
        <div className="cz-col">
          <section className="cz-card cmp">
            <div className="cz-ovh"><span className="eyebrow">Probabilidad real</span><span className="cz-prob-now num">{d.prob != null ? d.prob + "%" : "—"}</span></div>
            {timelineProbs.length > 0 && (
              <>
                <AreaLine points={timelineProbs} h={72} min={0} max={timelineMax}/>
                <div className="cz-tl-dates num">{timeline.map((t: any, i: number)=><span key={i}>{(t.date||"").slice(5)}</span>)}</div>
              </>
            )}
          </section>

          {roadmap.length > 0 && (
            <section className="cz-card cmp">
              <div className="cz-ovh"><span className="eyebrow">Stage roadmap</span></div>
              <ol className="cz-roadmap">
                {roadmap.map((r: any, i: number)=>(
                  <li key={i} className={"cz-rm-step"+(r.current?" current":"")+(r.done?" done":"")}>
                    <span className="cz-rm-dot"/>
                    <div className="cz-rm-body"><span className="cz-rm-stage">{r.stage}</span><span className="cz-rm-meta num">{r.range} · {r.dur}</span></div>
                  </li>
                ))}
              </ol>
            </section>
          )}

          <button className="cz-card cmp cz-company-link" onClick={()=>goTo("atlas")}>
            <div className="cz-company-icon"><Icon name="building" size={17}/></div>
            <div style={{textAlign:"left",flex:1,minWidth:0}}>
              <span className="eyebrow">Empresa · Atlas</span>
              <div className="cz-company-name" style={{fontSize:16}}>{atlas.company || d.name || "—"}</div>
            </div>
            <Icon name="arrowRight" size={15} stroke={2} style={{color:"var(--ink-3)"}}/>
          </button>

          {contacts.length > 0 && (
            <section className="cz-card cmp">
              <div className="cz-ovh"><span className="eyebrow">Contactos vivos</span><Chip tone="ink">{contacts.length}</Chip></div>
              <div className="cz-contact-list cmp">
                {contacts.slice(0,4).map((c: any, i: number)=>(
                  <div className={"cz-contact"+(c.risk?" risk":"")} key={i}>
                    <Avatar initials={c.initials || "?"} size={28} name={c.name}/>
                    <div style={{flex:1,minWidth:0}}>
                      <div className="cz-contact-name" style={{fontSize:12.5}}>{c.name}</div>
                      <div className="cz-contact-role">{c.role}</div>
                    </div>
                    {c.risk && <Chip tone="red" style={{fontSize:9.5,padding:"1px 6px",flex:"none"}}>Riesgo</Chip>}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   WORKSPACE SHELL
   ========================================================= */
interface DealWorkspaceProps {
  detail: any;
  initialTab?: string;
  onClose: () => void;
}

function DealWorkspace({ detail, initialTab="hist", onClose }: DealWorkspaceProps) {
  const [tab,setTab] = useState(initialTab);
  useEffect(()=>{ setTab(initialTab); },[detail, initialTab]);

  // esc to close
  useEffect(()=>{
    const h = (e: KeyboardEvent) => { if(e.key==="Escape") onClose(); };
    window.addEventListener("keydown",h); return ()=>window.removeEventListener("keydown",h);
  },[onClose]);

  // tabs definition removed (unused in current render path)

  const d = detail;
  return (
    <div className="cz-overlay" onMouseDown={e=>{ if(e.target===e.currentTarget) onClose(); }}>
      <div className="cz-panel" style={{animation:"cz-scale-in .3s var(--ease) both"}}>
        {/* spine header */}
        <header className="cz-spine">
          <button className="cz-iconbtn" onClick={onClose} title="Cerrar (Esc)"><Icon name="x" size={18}/></button>
          <div className="cz-spine-id">
            <div className="cz-spine-title-row">
              <h1 className="display">{d.name}</h1>
              <StageChip stage={d.stage}/>
            </div>
            <div className="cz-spine-meta">
              <span>PAE: <b>{d.pae}</b></span><span className="cz-dot">·</span>
              <span>PBD: <b>{d.pbd}</b></span><span className="cz-dot">·</span>
              <span>Last contact: <b className="num">{d.lastContact}</b></span>
              {d.hsId ? (
                <a className="cz-hs" href={hubspotDealUrl(d.hsId!)} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", color: "inherit" }}>
                  <Icon name="external" size={13}/> HubSpot
                </a>
              ) : (
                <span className="cz-hs"><Icon name="route" size={13}/> {d.atlas.crm}</span>
              )}
            </div>
          </div>
          <PulseStrip d={d}/>
        </header>

        {/* deal nav — only a back bar inside Atlas / Next steps.
            On the deal overview there's no nav row: Atlas & Next are reached
            contextually (action-zone button, company card, atlas hook). */}
        {tab!=="hist" && (
          <nav className="cz-dealnav">
            <button className="cz-backbtn" onClick={()=>setTab("hist")}><Icon name="arrowLeft" size={16} stroke={2}/> Volver al deal</button>
            <span className="cz-dealnav-current">{tab==="atlas"?"Atlas — empresa y deals anteriores":"Next steps — acciones y herramientas"}</span>
          </nav>
        )}

        {/* body */}
        <div className="cz-body" key={tab}>
          {tab==="hist"  && <HistView d={d} goTo={setTab}/>}
          {tab==="atlas" && <AtlasView d={d} goTo={setTab}/>}
          {tab==="next"  && <NextView d={d} goTo={setTab}/>}
        </div>
      </div>
    </div>
  );
}

export default DealWorkspace;
