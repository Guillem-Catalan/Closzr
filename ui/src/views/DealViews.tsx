/* ============================================================
   CLOSZR — ATLAS (company) + NEXT STEPS views
   ============================================================ */
import { useState, useEffect } from "react";
import { Icon, SectionLabel, Chip, Avatar, TONE } from "./components";

/* =========================================================
   ATLAS  — company / account intelligence
   ========================================================= */
function AtlasView({ d, goTo: _goTo }: { d: any; goTo: (tab: string) => void }) {
  const a = d.atlas || {};
  const [lostOpen,setLostOpen] = useState<string|null>(null);

  const isDomain = (t: string) => /^[^\s]+\.[^\s]+$/.test(t);
  const company = a.company || d.name || "—";
  const crm = a.crm || "HubSpot";
  const description = a.description || "Sin información de empresa.";
  const historyNote = a.historyNote || "";
  const tags = a.tags || [];
  const facts = a.facts || [];
  const warnings = a.warnings || [];
  const contacts = a.contacts || [];
  const deals = a.deals || [];
  const fit = a.fit || { level: "—", text: "—" };
  const lostReasons = a.lostReasons || null;
  const patterns = a.patterns || [];
  const activeDeals = deals.filter((x: any)=>x.status==="ACTIVO");
  const lostDeals = deals.filter((x: any)=>x.status!=="ACTIVO");
  const liveContacts = contacts.filter((c: any)=>c.inDeal || c.risk);
  const otherContacts = contacts.filter((c: any)=>!c.inDeal && !c.risk);

  const ContactCard = (c: any, i: number) => (
    <div className={"cz-contact"+(c.inDeal?" indeal":"")+(c.risk?" risk":"")} key={i}>
      <Avatar initials={c.initials} size={34} name={c.name}/>
      <div style={{flex:1,minWidth:0}}>
        <div className="cz-contact-name">{c.name}
          {c.inDeal && <Chip tone="green" style={{fontSize:10,padding:"1px 7px"}}>En deal</Chip>}
          {c.risk && <Chip tone="red" style={{fontSize:10,padding:"1px 7px"}}>Riesgo</Chip>}
        </div>
        <div className="cz-contact-role">{c.role}</div>
      </div>
    </div>
  );

  const signalsList = a._signals?.length ? a._signals : d.signals;
  const blockersList = a._blockers?.length ? a._blockers : d.blockers;

  const factsFiltered = facts.filter((f: any) => f.v && f.v !== "—" && f.v !== "null");

  return (
    <div className="cz-atlas" style={{animation:"cz-fade-up .35s var(--ease) both"}}>
      {/* company hero */}
      <div className="cz-atlas-hero">
        <div className="cz-atlas-mark">{company.slice(0,1)}</div>
        <div className="cz-atlas-id">
          <h2 className="display">{company}</h2>
          <div className="cz-atlas-meta">
            {tags.map((t: string, i: number)=>(
              <span key={i} className={"cz-ameta"+(isDomain(t)?" dom":"")}>{isDomain(t)?t.toUpperCase():t}</span>
            ))}
            <span className="cz-ameta crm"><Icon name="route" size={13}/> {crm}</span>
          </div>
        </div>
      </div>

      {/* 2x2 GRID — 50/50 */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"var(--gap)",alignItems:"start"}}>

        {/* TOP-LEFT: Empresa */}
        <div className="cz-card cz-pad" style={{minWidth:0}}>
          <SectionLabel letter="E" tone="violet">Empresa</SectionLabel>
          <p className="cz-summary" style={{marginBottom:14}}>{description}</p>
          {fit.level !== "—" && (fit.text || "").replace(/^—\s*/,"") !== "" && (
            <div className="cz-atlas-fit" style={{marginBottom:16,maxWidth:"none"}}>
              <span className="cz-fit-level"><span className="cz-fit-dot"/>{fit.level}</span>
              <span className="cz-fit-note">{(fit.text || "").replace(/^—\s*/,"")}</span>
            </div>
          )}
          {factsFiltered.length > 0 && (
            <div className="cz-facts">
              {factsFiltered.map((f: any, i: number)=>(
                <div className="cz-fact" key={i}>
                  <span className="eyebrow">{f.k}</span>
                  <span className="cz-fact-v">{f.v}</span>
                </div>
              ))}
            </div>
          )}
          {historyNote && (
            <div className="cz-historynote">
              <Icon name="clock" size={14} style={{color:"var(--ink-3)"}}/> {historyNote}
            </div>
          )}
          {warnings.map((w: string, i: number)=>(
            <div className="cz-warn" key={i}>
              <span className="cz-warn-ic"><Icon name="alert" size={14} stroke={2}/></span>
              <span>{w}</span>
            </div>
          ))}
        </div>

        {/* TOP-RIGHT: Señales + Blockers + Patrones */}
        <div className="cz-card cz-pad" style={{minWidth:0}}>
          <SectionLabel letter="A" tone="green">Señales, blockers & patrones</SectionLabel>
          {signalsList.length > 0 && (
            <>
              <span className="eyebrow" style={{display:"block",marginBottom:8}}>Buying signals</span>
              <ul className="cz-signal-list">
                {signalsList.map((s: any, i: number)=>(
                  <li key={i} className="cz-signal">
                    <span className="cz-sig-dot" style={{background:"var(--green)"}}/>
                    <div><span>{s.text}</span>
                      <Chip tone={s.strength==="Fuerte"?"green":"amber"} style={{marginLeft:8,verticalAlign:"middle",fontSize:10.5,padding:"2px 7px"}}>{s.strength}</Chip>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
          {blockersList.length > 0 && (
            <>
              <span className="eyebrow" style={{display:"block",margin:"16px 0 8px"}}>Blockers</span>
              <ul className="cz-signal-list">
                {blockersList.map((b: any, i: number)=>(
                  <li key={i} className="cz-blocker">
                    <span className="cz-sig-dot" style={{background: b.sev==="alto"?"var(--red)":"var(--amber)"}}/>
                    <span>{b.text}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {patterns.length > 0 && (
            <>
              <span className="eyebrow" style={{display:"block",margin:"16px 0 8px"}}>Patrones detectados</span>
              <div className="cz-pattern-panel">
                {patterns.map((p: string, i: number)=>(
                  <div key={i} className="cz-pat-row"><span className="cz-pat-i num">{i+1}</span><span>{p}</span></div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* BOTTOM-LEFT: Deals (always open, click lost → reason) */}
        <div className="cz-card cz-pad" style={{minWidth:0}}>
          <SectionLabel letter="D" tone="blue" right={
            <span style={{display:"flex",gap:6}}>
              <Chip tone="blue">{activeDeals.length} activos</Chip>
              {lostDeals.length>0 && <Chip tone="red">{lostDeals.length} perdidos</Chip>}
            </span>
          }>Historial de deals</SectionLabel>
          {activeDeals.length > 0 && (
            <>
              <span className="eyebrow" style={{display:"block",marginBottom:8}}>Activos</span>
              <div className="cz-deal-list">
                {activeDeals.map((dl: any, i: number)=>(
                  <div className="cz-deal-item active" key={i}>
                    <span className="cz-deal-pulse"/>
                    <div style={{flex:1,minWidth:0}}>
                      <div className="cz-deal-item-name">{dl.name}</div>
                      <div className="cz-deal-item-sub">{dl.owner}</div>
                    </div>
                    <Chip tone="blue" style={{fontSize:10.5,flex:"none"}}>ACTIVO</Chip>
                  </div>
                ))}
              </div>
            </>
          )}
          {lostDeals.length > 0 && (
            <>
              <span className="eyebrow" style={{display:"block",margin:"14px 0 8px"}}>Perdidos</span>
              <div className="cz-deal-list">
                {lostDeals.map((dl: any, i: number)=>{
                  const dlKey = dl.name + i;
                  const isOpen = lostOpen === dlKey;
                  const reason = lostReasons?.find((lr: any) => {
                    const dn = Array.isArray(lr.deals) ? lr.deals : typeof lr.deals === "string" ? lr.deals.split(",").map((s: string) => s.trim()) : [];
                    return dn.some((n: string) => dl.name.includes(n) || n.includes(dl.name));
                  });
                  return (
                    <div key={i}>
                      <button className="cz-deal-item lost" style={{width:"100%",cursor:"pointer"}} onClick={()=>setLostOpen(isOpen?null:dlKey)}>
                        <Chip tone="red" style={{fontSize:10.5,flex:"none"}}>PERDIDO</Chip>
                        <div style={{flex:1,minWidth:0,textAlign:"left"}}>
                          <div className="cz-deal-item-name">{dl.name}</div>
                          <div className="cz-deal-item-sub">{dl.owner}</div>
                        </div>
                        {dl.date && <span className="cz-deal-item-date num">{dl.date}</span>}
                        <Icon name="chevDown" size={13} style={{color:"var(--ink-3)",transform:isOpen?"none":"rotate(-90deg)",transition:"transform .18s",flex:"none"}}/>
                      </button>
                      {isOpen && (
                        <div style={{padding:"10px 14px",margin:"0 0 8px",background: reason ? "var(--red-tint)" : "var(--card-2)",borderRadius:"var(--r-sm)",fontSize:13,lineHeight:1.5,color: reason ? "var(--red-ink)" : "var(--ink-3)"}}>
                          {reason ? <><Icon name="alert" size={13} stroke={2} style={{verticalAlign:"-2px",marginRight:6}}/>{reason.reason}</> : "Sin análisis de pérdida disponible."}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
          {!deals.length && <p style={{color:"var(--ink-4)",fontSize:13}}>Sin deals registrados.</p>}
        </div>

        {/* BOTTOM-RIGHT: Contactos */}
        <div className="cz-card cz-pad" style={{minWidth:0}}>
          <SectionLabel letter="C" tone="teal" right={
            <Chip tone="ink">{contacts.length} total</Chip>
          }>Contactos</SectionLabel>
          {liveContacts.length>0 && (
            <>
              <span className="eyebrow" style={{display:"block",marginBottom:8}}>Vivos en el deal</span>
              <div className="cz-contact-grid">
                {liveContacts.map(ContactCard)}
              </div>
            </>
          )}
          {otherContacts.length>0 && (
            <>
              <span className="eyebrow" style={{display:"block",margin:"14px 0 8px"}}>Otros contactos</span>
              <div className="cz-contact-grid">
                {otherContacts.map(ContactCard)}
              </div>
            </>
          )}
          {!contacts.length && <p style={{color:"var(--ink-4)",fontSize:13}}>Sin contactos registrados.</p>}
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   NEXT STEPS — actions + tools + email + notes
   ========================================================= */
const STEP_TONE: Record<string, string> = { CALL:"blue", ROI:"green", EMAIL:"violet", ESCALAR:"red", SLIDES:"amber" };
const STEP_ICON: Record<string, string> = { CALL:"phone", ROI:"calculator", EMAIL:"mail", ESCALAR:"flag", SLIDES:"presentation" };

function NextView({ d, goTo: _goTo }: { d: any; goTo: (tab: string) => void }) {
  const [done,setDone] = useState<Record<number, boolean>>({});
  const [note,setNote] = useState("");
  const [comment,setComment] = useState("");
  const [emailOpen,setEmailOpen] = useState(false);
  const em = d.email;

  const toolIcon: Record<string, string> = { ROI:"calculator", Slides:"presentation", Battlecard:"shield", Briefing:"book" };

  return (
    <div className="cz-next" style={{animation:"cz-fade-up .35s var(--ease) both"}}>
      <div className="cz-next-grid">
        {/* LEFT — steps */}
        <div className="cz-col">
          <div className="cz-card">
            <SectionLabel letter="→" tone="indigo" right={
              <span className="num" style={{fontSize:12,color:"var(--ink-3)"}}>{Object.values(done).filter(Boolean).length}/{d.nextSteps.length} hechas</span>
            }>Next steps</SectionLabel>
            <ol className="cz-steps">
              {d.nextSteps.map((s: any, i: number)=>(
                <li key={i} className={"cz-step"+(done[i]?" done":"")}>
                  <button className="cz-step-check" onClick={()=>setDone(p=>({...p,[i]:!p[i]}))} aria-label="toggle">
                    {done[i] ? <Icon name="check" size={14} stroke={2.4}/> : <span className="cz-step-num">{i+1}</span>}
                  </button>
                  <div className="cz-step-body">
                    <div className="cz-step-top">
                      <Chip tone={STEP_TONE[s.kind]||"ink"} style={{fontSize:10.5}}>
                        <Icon name={STEP_ICON[s.kind]||"route"} size={11} stroke={2}/>{s.kind}
                      </Chip>
                      <span className="cz-step-who">{s.who}</span>
                      <span className="cz-step-when num">{s.when}</span>
                    </div>
                    <p className="cz-step-text">{s.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          {/* Notes + comments */}
          <div className="cz-twocol">
            <div className="cz-card">
              <SectionLabel letter="N" tone="amber" right={<span className="cz-mini-meta"><Icon name="route" size={12}/> se creará en HubSpot</span>}>Notas</SectionLabel>
              <textarea className="cz-textarea" rows={4} value={note} onChange={e=>setNote(e.target.value)} placeholder="Escribe una nota sobre este deal…"/>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginTop:10}}>
                <span style={{fontSize:12,color:"var(--amber-ink)"}}>Requiere login</span>
                <button className="cz-btn-soft" disabled={!note.trim()}>Crear nota</button>
              </div>
            </div>
            <div className="cz-card">
              <SectionLabel letter="C" tone="violet" right={<span className="cz-mini-meta"><Icon name="message" size={12}/> feedback interno + Slack</span>}>Comentarios</SectionLabel>
              <div className="cz-comment-empty">Sin comentarios</div>
              <textarea className="cz-textarea" rows={2} value={comment} onChange={e=>setComment(e.target.value)} placeholder="Escribe un comentario o problema que hayas encontrado…"/>
              <div style={{display:"flex",justifyContent:"flex-end",marginTop:10}}>
                <button className="cz-btn-primary" disabled={!comment.trim()}>Enviar</button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT — tools + email */}
        <div className="cz-col">
          <div className="cz-card">
            <SectionLabel letter="H" tone="teal">Herramientas</SectionLabel>
            <div className="cz-tools">
              {d.tools.map((t: any, i: number)=>(
                <button key={i} className={"cz-tool"+(t.active?" active":"")}>
                  <span className="cz-tool-ic" style={{background:TONE[t.tone].bg,color:TONE[t.tone].fg}}>
                    <Icon name={toolIcon[t.name]||"file"} size={18}/>
                  </span>
                  <div style={{textAlign:"left"}}>
                    <div className="cz-tool-name">{t.name}</div>
                    <div className="cz-tool-sub">{t.sub}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {em && (
            <div className="cz-card">
              <SectionLabel letter="@" tone="indigo" right={
                <button className="cz-link" onClick={()=>setEmailOpen(true)}>Ampliar <Icon name="external" size={13} stroke={2}/></button>
              }>Email de follow up</SectionLabel>
              <div className="cz-email-meta">
                <div><span>Para:</span><b>{em.to} · {em.toAddr}</b></div>
                <div><span>Cuándo:</span><b>{em.when}</b></div>
                <div><span>Motivo:</span><b>{em.reason}</b></div>
              </div>
              <button className="cz-email-preview" onClick={()=>setEmailOpen(true)}>
                <div className="cz-email-prev-subject">{em.subject}</div>
                <p className="cz-email-prev-body">{em.body?.[1]}</p>
                <span className="cz-email-prev-cta"><Icon name="mail" size={13} stroke={2}/> Ver email completo</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {emailOpen && em && <EmailModal em={em} onClose={()=>setEmailOpen(false)}/>}
    </div>
  );
}

/* ===== Email preview framed like a real mail client ===== */
function EmailModal({ em, onClose }: { em: any; onClose: () => void }) {
  useEffect(()=>{
    const h = (e: KeyboardEvent) => { if(e.key==="Escape"){ e.stopPropagation(); onClose(); } };
    window.addEventListener("keydown",h,true); return ()=>window.removeEventListener("keydown",h,true);
  },[onClose]);
  const [sent,setSent] = useState(false);
  return (
    <div className="cz-email-scrim" onMouseDown={e=>{ if(e.target===e.currentTarget) onClose(); }}>
      <div className="cz-mail" style={{animation:"cz-scale-in .26s var(--ease) both"}}>
        {/* client chrome */}
        <div className="cz-mail-chrome">
          <div className="cz-mail-dots"><span/><span/><span/></div>
          <div className="cz-mail-chrome-title"><Icon name="mail" size={14} stroke={2}/> Nuevo mensaje</div>
          <button className="cz-iconbtn sm" onClick={onClose} title="Cerrar (Esc)"><Icon name="x" size={16}/></button>
        </div>

        {/* toolbar */}
        <div className="cz-mail-toolbar">
          <span className="cz-mail-tag"><Icon name="sparkle" size={12}/> Borrador generado por Closzr</span>
          <span style={{flex:1}}/>
          <button className="cz-mail-tbtn" title="Editar"><Icon name="note" size={15}/></button>
          <button className="cz-mail-tbtn" title="Copiar"><Icon name="file" size={15}/></button>
        </div>

        {/* headers */}
        <div className="cz-mail-head">
          <div className="cz-mail-subject">{em.subject}</div>
          <div className="cz-mail-row">
            <Avatar initials={em.fromInit} size={40} name={em.from}/>
            <div className="cz-mail-fromto">
              <div className="cz-mail-from"><b>{em.from}</b> <span>&lt;{em.fromAddr}&gt;</span></div>
              <div className="cz-mail-to">para <b>{em.to}</b> &lt;{em.toAddr}&gt;</div>
            </div>
            <div className="cz-mail-when num">Programado · hoy</div>
          </div>
        </div>

        {/* body */}
        <div className="cz-mail-body">
          {em.body.map((p: string, i: number)=><p key={i}>{p}</p>)}
          <p className="cz-mail-sig">{em.signoff.split("\n").map((l: string, i: number)=><span key={i}>{l}<br/></span>)}</p>
        </div>

        {/* footer actions */}
        <div className="cz-mail-foot">
          <button className={"cz-btn-primary"+(sent?" is-sent":"")} onClick={()=>setSent(true)} disabled={sent}>
            {sent ? <><Icon name="check" size={15} stroke={2.4}/> Programado</> : <><Icon name="mail" size={15} stroke={2}/> Programar envío</>}
          </button>
          <button className="cz-btn-soft" onClick={onClose}>Editar borrador</button>
          <span style={{flex:1}}/>
          <span className="cz-mail-note"><Icon name="route" size={13}/> Se registrará en HubSpot</span>
        </div>
      </div>
    </div>
  );
}

export { AtlasView, NextView };
