/* ============================================================
   CLOSZR — BENCHMARK
   Historical archive of all won/lost deals with post-mortem analysis
   ============================================================ */
import { useState, useEffect, useMemo } from "react";
import { Icon, Avatar, TONE, fmtMRR } from "../components";
import { useData } from "../../data/store";
import type { BenchmarkDeal } from "../../data/store";
import { hubspotDealUrl } from "../../display";
import { normalize, expandTeams, distinctPipelines } from "../../data/filters";
import { MultiSelectTeam } from "../components";

function fmtEur(v: number | null | undefined): string {
  if (v == null || v === 0) return "—";
  return "€" + Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function fmtDate(d: string | null): string {
  if (!d) return "—";
  const s = d.slice(0, 10);
  const [y, m, day] = s.split("-");
  return `${day}/${m}/${y.slice(2)}`;
}

function HsLogo({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" fill="none">
      <path d="M391.8 197.4V133c17.2-8.3 29.1-25.8 29.1-46.1v-1.4c0-28.1-22.8-50.9-50.9-50.9h-1.4c-28.1 0-50.9 22.8-50.9 50.9v1.4c0 20.3 11.9 37.8 29.1 46.1v64.4c-25 5.1-47.9 16-67.2 31.6l-177.7-138.4c1.6-5.5 2.6-11.3 2.6-17.3C104.4 32.8 71.6 0 31.2 0S-42 32.8-42 73.2 57.6 146.4 98 146.4c0 0 0 0 0 0 6 0 11.8-1 17.3-2.6L291.6 280c-17.9 22-28.7 50-28.7 80.5 0 70.4 57.1 127.5 127.5 127.5S518 431 518 360.5 460.9 233 390.5 233c-.3 0-.5 0-.8 0l2.1-35.6zM390.5 425c-35.6 0-64.5-28.9-64.5-64.5s28.9-64.5 64.5-64.5 64.5 28.9 64.5 64.5-28.9 64.5-64.5 64.5z"
        fill="currentColor" transform="translate(42, 0) scale(0.88)" />
    </svg>
  );
}

/* ---- MEDDIC mini bar ---- */
function MeddicBar({ meddic }: { meddic: BenchmarkDeal["meddic"] }) {
  const scores = [meddic.m, meddic.e, meddic.dc, meddic.dp, meddic.i, meddic.c];
  const avg = scores.reduce((a, b) => a + b, 0) / 6;
  const pct = Math.round((avg / 10) * 100);
  const tone = pct >= 70 ? "var(--green)" : pct >= 40 ? "var(--amber)" : "var(--red)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 80 }}>
      <div style={{ flex: 1, height: 6, background: "var(--card-2)", borderRadius: 3, overflow: "hidden", minWidth: 50 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: tone, borderRadius: 3 }} />
      </div>
      <span className="num" style={{ fontSize: 11, color: "var(--ink-3)", minWidth: 28 }}>{pct}%</span>
    </div>
  );
}

/* ---- Bullet list helper ---- */
function BulletList({ items, tone }: { items: string[]; tone: "green" | "red" | "ink" }) {
  const color = tone === "green" ? "var(--green-ink)" : tone === "red" ? "var(--red-ink)" : "var(--ink-2)";
  const dot = tone === "green" ? "var(--green)" : tone === "red" ? "var(--red)" : "var(--ink-3)";
  return (
    <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 5 }}>
      {items.filter(Boolean).map((b, i) => (
        <li key={i} style={{ display: "flex", gap: 8, fontSize: 12.5, lineHeight: 1.5, color }}>
          <span style={{ color: dot, flex: "none" }}>•</span><span>{b.replace(/^[-•]\s*/, "").trim()}</span>
        </li>
      ))}
    </ul>
  );
}

/* ============================================================
   POST-MORTEM OVERLAY — per design handoff
   ============================================================ */
const MEDDIC_LABELS: Record<string, string> = { m: "Metrics", e: "Economic Buyer", dc: "Decision Criteria", dp: "Decision Process", i: "Identify Pain", c: "Champion" };
const MEDDIC_EMOJI: Record<string, string> = { m: "📊", e: "💰", dc: "📋", dp: "🔄", i: "🎯", c: "🤝" };

function PostMortem({ d, onClose }: { d: BenchmarkDeal; onClose: () => void }) {
  const won = d.outcome === "won";
  const [openPh, setOpenPh] = useState<number | null>(null);
  const [openMd, setOpenMd] = useState<string | null>(null);
  const [narrativeOpen, setNarrativeOpen] = useState(false);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const mddScores: Record<string, number> = { m: d.meddic.m, e: d.meddic.e, dc: d.meddic.dc, dp: d.meddic.dp, i: d.meddic.i, c: d.meddic.c };
  const meddicTotal = Object.values(mddScores).reduce((a, b) => a + b, 0);
  const hasMeddic = meddicTotal > 0;

  const inter = d.interactions;
  const calls = inter?.modjo_calls || inter?.total_calls || 0;
  const emails = inter?.total_emails || 0;
  const interStr = [calls && `${calls} calls`, emails && `${emails} emails`].filter(Boolean).join(" · ") || "—";

  const realPitched = d.productsPitched.filter(p => p.product && p.product !== "—");
  const realMissed = d.productsMissed.filter(p => p.product && p.product !== "—");
  const hasProducts = realPitched.length > 0 || realMissed.length > 0 || !!d.productAssessment;

  const initials = (name: string) => (name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();

  const timeline = d.timeline.map(ev => ({
    phase: (ev as any).phase || ev.event || "—",
    range: (ev as any).dates || (ev.date ? fmtDate(ev.date) : "—"),
    dur: (ev as any).duration_days ? `${(ev as any).duration_days}d` : "—",
    text: (ev as any).what_happened || ev.detail || "",
  }));

  return (
    <div className="cz-overlay" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={"cz-panel cz-pm " + (won ? "won" : "lost")} style={{ animation: "cz-scale-in .3s var(--ease) both" }}>

        {/* SPINE — header */}
        <header className="cz-pm-spine">
          <button className="cz-iconbtn" onClick={onClose} title="Cerrar (Esc)"><Icon name="x" size={18} /></button>
          <div className="cz-pm-id">
            <div className="cz-pm-title-row">
              <span className={"cz-oc big " + d.outcome}>
                <Icon name={won ? "award" : "xCircle"} size={14} stroke={2.2} />{won ? "Won" : "Lost"}
              </span>
              <h1 className="display">{d.deal}</h1>
            </div>
            <div className="cz-pm-meta">
              <span>PAE: <b>{d.owner}</b></span><span className="cz-dot">·</span>
              <span>Team: <b>{d.team || "—"}</b></span><span className="cz-dot">·</span>
              <span>{interStr}</span>
              {d.employees && <><span className="cz-dot">·</span><span>{d.employees} emp</span></>}
              {d.hsId && (
                <a className="cz-hs" href={hubspotDealUrl(d.hsId)} target="_blank" rel="noopener noreferrer"
                  style={{ textDecoration: "none", color: "inherit", marginLeft: 4, display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <Icon name="external" size={12} /> HS
                </a>
              )}
            </div>
          </div>
          <div className="cz-pulse">
            <div className="cz-pulse-item"><span className="cz-pulse-k">MRR</span><span className="cz-pulse-v display num">{fmtEur(d.mrr)}</span></div>
            <div className="cz-pulse-item"><span className="cz-pulse-k">Close</span><span className="cz-pulse-v display num">{fmtDate(d.closeDate)}</span></div>
            {d.dealAge != null && d.dealAge > 0 && <div className="cz-pulse-item"><span className="cz-pulse-k">Cycle</span><span className="cz-pulse-v display num">{d.dealAge}d</span></div>}
            {hasMeddic && <div className="cz-pulse-item"><span className="cz-pulse-k">MEDDIC</span><span className="cz-pulse-v display num">{meddicTotal}/60</span></div>}
          </div>
        </header>

        <div className="cz-body">

          {/* HERO — turning point */}
          {d.keyTurningPoint && (
            <section className={"cz-pm-hero " + d.outcome}>
              <div className="cz-pm-hero-mark"><Icon name={won ? "award" : "xCircle"} size={22} /></div>
              <div>
                <span className="eyebrow" style={{ color: won ? "var(--green-ink)" : "var(--red-ink)" }}>
                  {won ? "⚡ Turning point" : "⚡ Where it was lost"}
                </span>
                <p className="cz-pm-turning">{d.keyTurningPoint}</p>
              </div>
            </section>
          )}

          {/* OUTCOME SUMMARY */}
          {d.outcomeSummary && (
            <section className="cz-card cmp" style={{ marginBottom: "var(--gap)" }}>
              <div className="cz-ovh"><span className="eyebrow">📝 Outcome summary</span><span className="cz-ovh-by"><Icon name="sparkle" size={12} /> Closzr</span></div>
              <p className="cz-summary">{d.outcomeSummary}</p>
            </section>
          )}

          {/* WHAT WORKED / FAILED */}
          {(d.whatWorked.length > 0 || d.whatFailed.length > 0) && (
            <div className="cz-pm-grid2">
              {d.whatWorked.length > 0 && (
                <section className="cz-card cmp">
                  <div className="cz-ovh">
                    <span className="eyebrow" style={{ color: "var(--green-ink)" }}>✅ What worked</span>
                    <span style={{ marginLeft: "auto", background: "var(--green-tint)", color: "var(--green-ink)", fontWeight: 700, fontSize: 12, padding: "3px 9px", borderRadius: 999 }}>{d.whatWorked.length}</span>
                  </div>
                  <ul className="cz-pm-list good">
                    {d.whatWorked.map((w, i) => (
                      <li key={i}><span className="cz-pm-num good">{i + 1}</span><span>{w.replace(/^[-•]\s*/, "").trim()}</span></li>
                    ))}
                  </ul>
                </section>
              )}
              {d.whatFailed.length > 0 && (
                <section className="cz-card cmp">
                  <div className="cz-ovh">
                    <span className="eyebrow" style={{ color: "var(--red-ink)" }}>⚠️ What failed</span>
                    <span style={{ marginLeft: "auto", background: "var(--red-tint)", color: "var(--red-ink)", fontWeight: 700, fontSize: 12, padding: "3px 9px", borderRadius: 999 }}>{d.whatFailed.length}</span>
                  </div>
                  <ul className="cz-pm-list bad">
                    {d.whatFailed.map((w, i) => (
                      <li key={i}><span className="cz-pm-num bad">{i + 1}</span><span>{w.replace(/^[-•]\s*/, "").trim()}</span></li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}

          {/* TIMELINE */}
          {timeline.length > 0 && (
            <section className="cz-card cmp" style={{ marginTop: "var(--gap)" }}>
              <div className="cz-ovh"><span className="eyebrow">🗺️ Deal timeline</span><span className="cz-tb-meta" style={{ marginLeft: "auto", fontSize: 11.5 }}>{timeline.length} phases</span></div>
              <div className="cz-md-tiles" style={{ gridTemplateColumns: `repeat(${Math.min(timeline.length, 4)}, 1fr)` }}>
                {timeline.map((t, i) => {
                  const hasText = !!t.text;
                  return (
                    <button className={"cz-md-tile" + (hasText ? " clk" : "") + (openPh === i ? " open" : "")} key={i}
                      style={{ background: "var(--card-2)", cursor: hasText ? "pointer" : "default" }}
                      onClick={() => hasText && setOpenPh(openPh === i ? null : i)}>
                      <div className="cz-md-tile-top">
                        <span className="cz-pm-phase-n num">{i + 1}</span>
                      </div>
                      <span className="cz-md-tile-label" style={{ color: "var(--ink)" }}>{t.phase}</span>
                      <span className="cz-pm-phase-range num">{t.range} · {t.dur}</span>
                    </button>
                  );
                })}
              </div>
              {openPh != null && timeline[openPh]?.text && (
                <div className="cz-md-expl" style={{ animation: "cz-fade .2s ease both" }}>
                  <span className="cz-md-expl-k">Phase {openPh + 1} · {timeline[openPh].phase} · {timeline[openPh].dur}</span>
                  <p>{timeline[openPh].text}</p>
                </div>
              )}
            </section>
          )}

          {/* ASSESSMENT + COULD CHANGE */}
          {(d.repAssessment || d.couldHaveChanged) && (
            <div className="cz-pm-grid2" style={{ marginTop: "var(--gap)" }}>
              {d.repAssessment && (
                <section className="cz-card cmp">
                  <div className="cz-ovh">
                    <span className="eyebrow">🧭 Rep assessment</span>
                    <span className="cz-pm-avatar"><Avatar initials={initials(d.owner)} size={24} name={d.owner} />{d.owner}</span>
                  </div>
                  <p className="cz-summary">{d.repAssessment}</p>
                </section>
              )}
              {d.couldHaveChanged && (
                <section className="cz-card cmp cz-pm-coach">
                  <div className="cz-ovh"><span className="eyebrow" style={{ color: "var(--amber-ink)" }}>🔧 What to change</span></div>
                  <p className="cz-summary">{d.couldHaveChanged}</p>
                </section>
              )}
            </div>
          )}

          {/* MEDDIC TILES */}
          {hasMeddic && (
            <section className="cz-card cmp" style={{ marginTop: "var(--gap)" }}>
              <div className="cz-ovh"><span className="eyebrow">🎯 MEDDIC final</span><span className="cz-pm-total num" style={{ marginLeft: "auto" }}>{meddicTotal}<small>/60</small></span></div>
              <div className="cz-md-tiles">
                {Object.entries(mddScores).map(([k, sc]) => {
                  const tone = sc >= 7 ? "green" : sc >= 4 ? "amber" : "red";
                  const c = TONE[tone];
                  const txt = d.meddicText[k as keyof typeof d.meddicText];
                  const hasText = !!txt;
                  const isOpen = openMd === k;
                  return (
                    <button className={"cz-md-tile" + (hasText ? " clk" : "") + (isOpen ? " open" : "")} key={k}
                      style={{ background: c.bg, cursor: hasText ? "pointer" : "default" }}
                      onClick={() => hasText && setOpenMd(isOpen ? null : k)}>
                      <div className="cz-md-tile-top"><span className="cz-md-tile-emoji">{MEDDIC_EMOJI[k]}</span><span className="cz-md-tile-v num" style={{ color: c.fg }}>{sc}<small>/10</small></span></div>
                      <span className="cz-md-tile-label" style={{ color: c.fg }}>{MEDDIC_LABELS[k]}</span>
                      <span className="cz-md-tile-bar"><span style={{ width: (sc * 10) + "%", background: c.fg }} /></span>
                    </button>
                  );
                })}
              </div>
              {openMd && d.meddicText[openMd as keyof typeof d.meddicText] && (
                <div className="cz-md-expl" style={{ animation: "cz-fade .2s ease both" }}>
                  <span className="cz-md-expl-k">{MEDDIC_EMOJI[openMd]} {MEDDIC_LABELS[openMd]} · {mddScores[openMd]}/10</span>
                  <p>{d.meddicText[openMd as keyof typeof d.meddicText]}</p>
                </div>
              )}
            </section>
          )}

          {/* PRODUCT + PEOPLE */}
          {(hasProducts || d.keyPeople.length > 0) && (
            <div className="cz-pm-grid2" style={{ marginTop: "var(--gap)" }}>
              {hasProducts && (
                <section className="cz-card cmp">
                  <div className="cz-ovh"><span className="eyebrow">📦 Product</span></div>
                  {realPitched.length > 0 && (
                    <>
                      <span className="cz-pm-sub">✅ Pitched</span>
                      <div className="cz-pm-chips" style={{ marginBottom: realMissed.length > 0 ? 14 : 0 }}>
                        {realPitched.map((p, i) => <span key={i} className="cz-pm-prod good">{p.product}</span>)}
                      </div>
                    </>
                  )}
                  {realMissed.length > 0 && (
                    <>
                      <span className="cz-pm-sub">🕳️ Missed opportunity</span>
                      <div className="cz-pm-missed">
                        {realMissed.map((m, i) => (
                          <div className="cz-pm-miss" key={i}><b>{m.product}</b>{m.reason && <span>{m.reason}</span>}</div>
                        ))}
                      </div>
                    </>
                  )}
                  {d.productAssessment && (
                    <p className="cz-pm-passess"><Icon name="sparkle" size={12} stroke={2} style={{ color: "var(--indigo)", verticalAlign: "-1px", marginRight: 4 }} />{d.productAssessment}</p>
                  )}
                </section>
              )}
              {d.keyPeople.length > 0 && (
                <section className="cz-card cmp">
                  <div className="cz-ovh">
                    <span className="eyebrow">👥 Key people</span>
                    <span style={{ marginLeft: "auto", background: "#EEEAE1", color: "var(--ink-2)", fontWeight: 700, fontSize: 12, padding: "3px 9px", borderRadius: 999 }}>{d.keyPeople.length}</span>
                  </div>
                  <div className="cz-pm-people">
                    {d.keyPeople.map((p, i) => (
                      <div className="cz-pm-person" key={i}>
                        <Avatar initials={initials(p.name || "?")} size={32} name={p.name || "?"} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div className="cz-pm-person-name">{p.name || "Unknown"}</div>
                          <div className="cz-pm-person-role">{p.role || "—"}</div>
                        </div>
                        {p.influence && <span style={{ fontSize: 11, color: "var(--ink-3)", fontWeight: 600 }}>{p.influence}</span>}
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}

          {/* FULL NARRATIVE — collapsible */}
          {d.fullNarrative && (
            <section className="cz-card cmp" style={{ marginTop: "var(--gap)" }}>
              <button onClick={() => setNarrativeOpen(!narrativeOpen)} style={{
                display: "flex", alignItems: "center", gap: 8, width: "100%", padding: 0,
                background: "none", border: "none", cursor: "pointer",
              }}>
                <Icon name="chevDown" size={13} style={{ color: "var(--ink-3)", transform: narrativeOpen ? "none" : "rotate(-90deg)", transition: "transform .18s" }} />
                <span className="eyebrow">📖 Full narrative</span>
                <span className="cz-ovh-by" style={{ marginLeft: "auto" }}><Icon name="sparkle" size={12} /> Closzr</span>
              </button>
              {narrativeOpen && <p className="cz-summary" style={{ whiteSpace: "pre-line", marginTop: 12 }}>{d.fullNarrative}</p>}
            </section>
          )}

          {/* LESSONS — dark block */}
          {d.lessons.filter(Boolean).length > 0 && (
            <section className="cz-pm-lessons" style={{ marginTop: "var(--gap)" }}>
              <div className="cz-pm-lessons-head"><Icon name="sparkle" size={16} /><span className="eyebrow" style={{ color: "#fff", letterSpacing: ".1em" }}>💡 Lessons for the team</span></div>
              <ol className="cz-pm-lessons-list">
                {d.lessons.filter(Boolean).map((l, i) => <li key={i}><span className="num">{i + 1}</span><span>{l}</span></li>)}
              </ol>
            </section>
          )}

          {/* LOST REASON — only for lost deals without turning point */}
          {!won && d.lostReason && !d.keyTurningPoint && (
            <section className="cz-card cmp" style={{ marginTop: "var(--gap)", background: "var(--red-tint)", borderColor: "var(--red)" }}>
              <div className="cz-ovh"><span className="eyebrow" style={{ color: "var(--red-ink)" }}>❌ Lost Reason</span></div>
              <p className="cz-summary" style={{ color: "var(--red-ink)" }}>{d.lostReason}</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---- Row grid ---- */
const rowGrid: React.CSSProperties = { gridTemplateColumns: "minmax(180px,1.4fr) 90px 90px 70px 100px 130px 110px" };

/* ---- Deal Row (quick-glance expandable) ---- */
function BenchRow({ d, open, onToggle, onOpen, onAnalysis }: { d: BenchmarkDeal; open: boolean; onToggle: () => void; onOpen: (row: any, tab?: string) => void; onAnalysis: () => void }) {
  const isWon = d.outcome === "won";
  const inter = d.interactions;
  const interParts: string[] = [];
  if (inter?.total_calls) interParts.push(`${inter.total_calls} calls`);
  if (inter?.total_emails) interParts.push(`${inter.total_emails} emails`);
  if (inter?.hs_meetings) interParts.push(`${inter.hs_meetings} meetings`);

  const hasAnalysis = !!(d.fullNarrative || d.whatWorked.length || d.whatFailed.length || d.lessons.length || d.keyTurningPoint);

  return (
    <>
      <div className="cz-prow" style={{ cursor: "pointer", ...rowGrid }} onClick={onToggle}>
        <div className="cz-pc-deal">
          <span className="cz-pc-name" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: isWon ? "var(--green)" : "var(--red)", flex: "none" }} />
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
        <MeddicBar meddic={d.meddic} />
        <div className="cz-pc-owner">{d.owner}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button onClick={e => { e.stopPropagation(); onOpen({ id: d.id }, "hist"); }}
            style={{ fontSize: 11, fontWeight: 600, color: "var(--indigo)", background: "var(--indigo-tint)", border: "none", padding: "4px 10px", borderRadius: "var(--r-pill)", cursor: "pointer", whiteSpace: "nowrap" }}>
            Ver deal
          </button>
          <Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: open ? "none" : "rotate(-90deg)", transition: "transform .18s" }} />
        </div>
      </div>
      {open && (
        <div style={{ padding: "16px 22px 18px", background: "var(--card-2)", borderBottom: "1px solid var(--line-2)", display: "flex", flexDirection: "column", gap: 12 }}>

          {/* Key Turning Point */}
          {d.keyTurningPoint && (
            <div style={{ padding: "10px 14px", background: "var(--indigo-tint)", borderRadius: "var(--r-sm)", borderLeft: "3px solid var(--indigo)" }}>
              <span className="eyebrow" style={{ display: "block", marginBottom: 4, color: "var(--indigo)" }}>Key Turning Point</span>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: "var(--ink)", fontStyle: "italic" }}>"{d.keyTurningPoint}"</p>
            </div>
          )}

          {/* What Worked / What Failed */}
          {(d.whatWorked.length > 0 || d.whatFailed.length > 0) && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {d.whatWorked.length > 0 && (
                <div style={{ padding: "10px 14px", background: "var(--green-tint)", borderRadius: "var(--r-sm)" }}>
                  <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--green-ink)" }}>What Worked</span>
                  <BulletList items={d.whatWorked.slice(0, 3)} tone="green" />
                </div>
              )}
              {d.whatFailed.length > 0 && (
                <div style={{ padding: "10px 14px", background: "var(--red-tint)", borderRadius: "var(--r-sm)" }}>
                  <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: "var(--red-ink)" }}>What Failed</span>
                  <BulletList items={d.whatFailed.slice(0, 3)} tone="red" />
                </div>
              )}
            </div>
          )}

          {/* Fallback: outcome summary if no worked/failed */}
          {d.whatWorked.length === 0 && d.whatFailed.length === 0 && d.outcomeSummary && (
            <div style={{ padding: "10px 14px", background: isWon ? "var(--green-tint)" : "var(--red-tint)", borderRadius: "var(--r-sm)" }}>
              <span className="eyebrow" style={{ display: "block", marginBottom: 6, color: isWon ? "var(--green-ink)" : "var(--red-ink)" }}>
                {isWon ? "How it was won" : "Lost reason"}
              </span>
              <BulletList items={d.outcomeSummary.split("\n")} tone={isWon ? "green" : "red"} />
            </div>
          )}

          {/* Lessons (max 2) */}
          {d.lessons.length > 0 && (
            <div>
              <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Lessons</span>
              {d.lessons.slice(0, 2).filter(Boolean).map((l, i) => (
                <p key={i} style={{ margin: "0 0 3px", fontSize: 12.5, lineHeight: 1.5, color: "var(--ink-2)" }}>
                  <span className="num" style={{ fontWeight: 700, color: "var(--ink-3)", marginRight: 6 }}>{i + 1}.</span>{l}
                </p>
              ))}
            </div>
          )}

          {/* Footer: interactions + View Analysis */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
              {interParts.length > 0 ? interParts.join(" · ") : ""}
            </span>
            {hasAnalysis && (
              <button onClick={e => { e.stopPropagation(); onAnalysis(); }}
                style={{ fontSize: 11, fontWeight: 700, color: "var(--indigo)", background: "var(--indigo-tint)", border: "1.5px solid var(--indigo)", padding: "5px 14px", borderRadius: "var(--r-pill)", cursor: "pointer", whiteSpace: "nowrap" }}>
                View Analysis →
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}

/* ============================================================ */
export default function BenchmarkView({ onOpen }: { onOpen: (row: any, tab?: string) => void }) {
  const D = useData();
  const B = D.benchmark;
  const allDeals = useMemo(() => [...B.won, ...B.lost], [B.won, B.lost]);

  const [outcomeFilter, setOutcomeFilter] = useState<"all" | "won" | "lost">("all");
  const [monthFilter, setMonthFilter] = useState("");
  const [pipelineFilters, setPipelineFilters] = useState<Set<string>>(new Set());
  const [teamFilters, setTeamFilters] = useState<Set<string>>(new Set());
  const [repFilter, setRepFilter] = useState("");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  type SortKey = "mrr-desc" | "mrr-asc" | "date-desc" | "date-asc" | "cycle-desc" | "cycle-asc" | "meddic-desc" | "meddic-asc";
  const [sortKey, setSortKey] = useState<SortKey>("date-desc");
  const PAGE_SIZE = 50;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const availableMonths = useMemo(() => {
    const s = new Set<string>();
    for (const d of allDeals) if (d.closeDate && d.closeDate >= "2026") s.add(d.closeDate.slice(0, 7));
    return [...s].sort().reverse();
  }, [allDeals]);

  const pipelines = useMemo(() => distinctPipelines(allDeals), [allDeals]);
  const teams = useMemo(() => { const s = new Set<string>(); for (const d of allDeals) if (d.team) s.add(d.team); return [...s].sort(); }, [allDeals]);
  const teamExpanded = useMemo(() => expandTeams(teamFilters), [teamFilters]);
  const reps = useMemo(() => { const s = new Set<string>(); for (const d of allDeals) { if (teamExpanded && !teamExpanded.has(d.team)) continue; if (d.owner && d.owner !== "—") s.add(d.owner); } return [...s].sort(); }, [allDeals, teamExpanded]);
  const repNorm = repFilter ? normalize(repFilter) : "";

  const fmtMonth = (m: string) => { const [y, mm] = m.split("-"); return `${MONTH_LABELS[parseInt(mm, 10) - 1]} ${y}`; };

  const filtered = useMemo(() => {
    setVisibleCount(PAGE_SIZE);
    let out = allDeals;
    if (pipelineFilters.size) out = out.filter(d => pipelineFilters.has(d.pipeline || ""));
    if (monthFilter) out = out.filter(d => d.closeDate && d.closeDate.startsWith(monthFilter));
    if (outcomeFilter !== "all") out = out.filter(d => d.outcome === outcomeFilter);
    if (teamExpanded) out = out.filter(d => teamExpanded.has(d.team));
    if (repFilter) out = out.filter(d => { const on = normalize(d.owner); return on === repNorm || on.startsWith(repNorm + " "); });
    if (search.trim()) { const q = search.toLowerCase(); out = out.filter(d => d.deal.toLowerCase().includes(q) || d.owner.toLowerCase().includes(q)); }
    return out;
  }, [allDeals, pipelineFilters, monthFilter, outcomeFilter, teamExpanded, repFilter, repNorm, search]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    const meddicAvg = (d: BenchmarkDeal) => (d.meddic.m + d.meddic.e + d.meddic.dc + d.meddic.dp + d.meddic.i + d.meddic.c) / 6;
    const nullsLast = (v: string | null) => v || "0000-00-00";
    switch (sortKey) {
      case "mrr-desc": return arr.sort((a, b) => (b.mrr || 0) - (a.mrr || 0));
      case "mrr-asc":  return arr.sort((a, b) => (a.mrr || 0) - (b.mrr || 0));
      case "date-desc": return arr.sort((a, b) => nullsLast(b.closeDate).localeCompare(nullsLast(a.closeDate)));
      case "date-asc":  return arr.sort((a, b) => nullsLast(a.closeDate).localeCompare(nullsLast(b.closeDate)));
      case "cycle-desc": return arr.sort((a, b) => (b.dealAge || 0) - (a.dealAge || 0));
      case "cycle-asc":  return arr.sort((a, b) => (a.dealAge || 0) - (b.dealAge || 0));
      case "meddic-desc": return arr.sort((a, b) => meddicAvg(b) - meddicAvg(a));
      case "meddic-asc":  return arr.sort((a, b) => meddicAvg(a) - meddicAvg(b));
      default: return arr;
    }
  }, [filtered, sortKey]);

  // Stats from base-filtered deals (month/team/rep/search) — NOT affected by outcome filter
  const baseFiltered = useMemo(() => {
    let out = allDeals;
    if (pipelineFilters.size) out = out.filter(d => pipelineFilters.has(d.pipeline || ""));
    if (monthFilter) out = out.filter(d => d.closeDate && d.closeDate.startsWith(monthFilter));
    if (teamExpanded) out = out.filter(d => teamExpanded.has(d.team));
    if (repFilter) out = out.filter(d => { const on = normalize(d.owner); return on === repNorm || on.startsWith(repNorm + " "); });
    if (search.trim()) { const q = search.toLowerCase(); out = out.filter(d => d.deal.toLowerCase().includes(q) || d.owner.toLowerCase().includes(q)); }
    return out;
  }, [allDeals, pipelineFilters, monthFilter, teamExpanded, repFilter, repNorm, search]);
  const allWon = baseFiltered.filter(d => d.outcome === "won");
  const allLost = baseFiltered.filter(d => d.outcome === "lost");
  const winRate = allWon.length + allLost.length > 0 ? Math.round(allWon.length / (allWon.length + allLost.length) * 100) : 0;
  const totalWonMrr = allWon.reduce((s, d) => s + (d.mrr || 0), 0);
  const totalLostMrr = allLost.reduce((s, d) => s + (d.mrr || 0), 0);

  const sortCol = (prefix: string) => sortKey.startsWith(prefix);
  const headClick = (desc: SortKey, asc: SortKey) => () => setSortKey(sortKey === desc ? asc : desc);

  const analysisDeal = analysisId ? allDeals.find(d => d.id === analysisId) : null;

  return (
    <div className="cz-fc">
      {/* Toolbar */}
      <div className="cz-toolbar" style={{ marginBottom: 12 }}>
        <div className="cz-tb-title"><h2 className="display">Closed</h2></div>
        <div style={{ flex: 1 }} />
        <div className="cz-seg">
          <button className={outcomeFilter === "all" ? "on" : ""} onClick={() => { setOutcomeFilter("all"); setExpandedId(null); }}>All ({allWon.length + allLost.length})</button>
          <button className={outcomeFilter === "won" ? "on" : ""} onClick={() => { setOutcomeFilter("won"); setExpandedId(null); }}>Won ({allWon.length})</button>
          <button className={outcomeFilter === "lost" ? "on" : ""} onClick={() => { setOutcomeFilter("lost"); setExpandedId(null); }}>Lost ({allLost.length})</button>
        </div>
        <select className="cz-native-select" value={monthFilter} onChange={e => setMonthFilter(e.target.value)}>
          <option value="">All Months</option>
          {availableMonths.map(m => <option key={m} value={m}>{fmtMonth(m)}</option>)}
        </select>
        <MultiSelectTeam teams={pipelines} selected={pipelineFilters} onChange={v => { setPipelineFilters(v); setTeamFilters(new Set()); setRepFilter(""); }} allLabel="All Pipelines" />
        <MultiSelectTeam teams={teams} selected={teamFilters} onChange={v => { setTeamFilters(v); setRepFilter(""); }} />
        <select className="cz-native-select" value={repFilter} onChange={e => setRepFilter(e.target.value)}>
          <option value="">All Reps</option>
          {reps.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="cz-search">
          <Icon name="search" size={16} style={{ color: "var(--ink-3)" }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search deals..." />
        </label>
      </div>

      {/* Stat cards — always show totals, not affected by outcome filter */}
      <div className="cz-cl-stats" style={{ marginBottom: 16 }}>
        <div className="cz-cl-stat won">
          <span className="cz-cl-stat-k"><Icon name="award" size={15} stroke={2} /> Won</span>
          <span className="cz-cl-stat-v display num">{allWon.length}</span>
          <span className="cz-cl-stat-sub num">{fmtEur(totalWonMrr)} MRR</span>
        </div>
        <div className="cz-cl-stat lost">
          <span className="cz-cl-stat-k"><Icon name="xCircle" size={15} stroke={2} /> Lost</span>
          <span className="cz-cl-stat-v display num">{allLost.length}</span>
          <span className="cz-cl-stat-sub num">{fmtEur(totalLostMrr)} MRR lost</span>
        </div>
        <div className="cz-cl-stat rate">
          <span className="cz-cl-stat-k"><Icon name="target" size={15} stroke={2} /> Win Rate</span>
          <span className="cz-cl-stat-v display num">{winRate}%</span>
          <span className="cz-cl-stat-sub">{allWon.length} of {allWon.length + allLost.length} deals</span>
        </div>
      </div>

      {/* Deal table */}
      <div className="cz-card cz-cl-listcard">
        <div className="cz-ptable">
          <div className="cz-pthead" style={rowGrid}>
            <div>Deal</div>
            <div style={{ cursor: "pointer", color: sortCol("mrr") ? "var(--indigo)" : undefined }} onClick={headClick("mrr-desc", "mrr-asc")}>
              MRR <span style={{ fontSize: 10, marginLeft: 4, color: sortCol("mrr") ? "var(--indigo)" : "var(--ink-3)" }}>{sortKey === "mrr-asc" ? "▲" : "▼"}</span>
            </div>
            <div style={{ cursor: "pointer", color: sortCol("date") ? "var(--indigo)" : undefined }} onClick={headClick("date-desc", "date-asc")}>
              Closed <span style={{ fontSize: 10, marginLeft: 4, color: sortCol("date") ? "var(--indigo)" : "var(--ink-3)" }}>{sortKey === "date-asc" ? "▲" : "▼"}</span>
            </div>
            <div style={{ cursor: "pointer", color: sortCol("cycle") ? "var(--indigo)" : undefined }} onClick={headClick("cycle-desc", "cycle-asc")}>
              Cycle <span style={{ fontSize: 10, marginLeft: 4, color: sortCol("cycle") ? "var(--indigo)" : "var(--ink-3)" }}>{sortKey === "cycle-asc" ? "▲" : "▼"}</span>
            </div>
            <div style={{ cursor: "pointer", color: sortCol("meddic") ? "var(--indigo)" : undefined }} onClick={headClick("meddic-desc", "meddic-asc")}>
              MEDDIC <span style={{ fontSize: 10, marginLeft: 4, color: sortCol("meddic") ? "var(--indigo)" : "var(--ink-3)" }}>{sortKey === "meddic-asc" ? "▲" : "▼"}</span>
            </div>
            <div>Owner</div>
            <div></div>
          </div>
          {sorted.slice(0, visibleCount).map(d => (
            <BenchRow key={d.id} d={d} open={expandedId === d.id}
              onToggle={() => setExpandedId(expandedId === d.id ? null : d.id || null)}
              onOpen={onOpen}
              onAnalysis={() => setAnalysisId(d.id || null)} />
          ))}
          {visibleCount < sorted.length && (
            <button onClick={() => setVisibleCount(c => c + PAGE_SIZE)} style={{
              width: "100%", padding: "12px", border: "none", background: "var(--card-2)",
              cursor: "pointer", fontSize: 13, fontWeight: 600, color: "var(--indigo)",
              borderTop: "1px solid var(--line-2)",
            }}>
              Mostrar más ({sorted.length - visibleCount} restantes)
            </button>
          )}
          {!sorted.length && <div className="cz-empty">No deals match these filters.</div>}
        </div>
      </div>

      {/* Post-mortem overlay */}
      {analysisDeal && <PostMortem d={analysisDeal} onClose={() => setAnalysisId(null)} />}
    </div>
  );
}
