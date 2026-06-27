import { supabase } from "./supabase";

export type DealDetail = {
  id: string;
  hsId: string | null;
  name: string;
  stage: string;
  pae: string;
  pbd: string;
  lastContact: string;
  mrr: number | string;
  prob: number | null;
  closeDate: string;
  forecast: string;
  employees: string;
  trend: number | null;
  signal: { kind: string; text: string; due: string };
  howto: { context: string; text: string };
  meddic: Record<string, { score: number; text: string }>;
  bant: { overall: string; items: { key: string; label: string; status: string; tone: string; text: string }[] };
  product: {
    products: string[];
    assessment: string;
    actions: { product: string; type: string; text: string }[];
    upsells: { product: string; text: string }[];
    expansion: string | null;
  };
  summary: string;
  signals: { strength: string; text: string }[];
  blockers: { sev: string; text: string }[];
  timeline: { date: string; prob: number }[];
  roadmap: { stage: string; range: string; dur: string; done: boolean; current?: boolean }[];
  nextSteps: { kind: string; who: string; text: string; when: string }[];
  tools: { name: string; sub: string; tone: string; active?: boolean }[];
  email: any;
  atlas: {
    company: string;
    tags: string[];
    crm: string;
    description: string;
    fit: { level: string; text: string };
    facts: { k: string; v: string }[];
    historyNote: string;
    warnings: string[];
    contacts: { name: string; role: string; initials: string; inDeal?: boolean; risk?: boolean }[];
    deals: { status: string; name: string; owner: string; date?: string }[];
    lostReasons: { reason: string; deals: string[] }[] | null;
    patterns: string[];
  };
};

function parseBullets(text: string | null): string[] {
  if (!text) return [];
  return text.split(/\n/).map(s => s.replace(/^[-•*\s]+/, "").trim()).filter(s => s.length > 3);
}

function initials(name: string): string {
  return (name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
}

function parseSignalKind(text: string): string {
  if (/\[CALL\]|llama|llamar|contactar/i.test(text)) return "CALL";
  if (/\[EMAIL\]|email|enviar/i.test(text)) return "EMAIL";
  if (/\[SLIDES\]/i.test(text)) return "SLIDES";
  if (/\[ROI\]/i.test(text)) return "ROI";
  return "PREP";
}

function bantTone(status: string | null): string {
  if (!status) return "ink";
  const s = status.toLowerCase();
  if (s === "confirmed") return "green";
  if (s === "partial") return "amber";
  return "red";
}

function bantLabel(status: string | null): string {
  if (!status) return "Sin datos";
  const map: Record<string, string> = {
    "confirmed": "Confirmado", "Confirmed": "Confirmado",
    "partial": "Parcial", "Partial": "Parcial",
    "not_validated": "Sin validar", "Not Validated": "Sin validar",
  };
  return map[status] || status;
}

function daysBetween(d1: string, d2: string): string {
  const ms = new Date(d2).getTime() - new Date(d1).getTime();
  const days = Math.round(ms / 86_400_000);
  if (days < 1) return "<1d";
  return days + "d";
}

type Contact = { name: string; role: string; initials: string; inDeal?: boolean; risk?: boolean };

function parseContacts(raw: any, contactsInfo?: string | null): Contact[] {
  const contacts: Contact[] = [];

  if (raw) {
    const text = typeof raw === "string" ? raw : JSON.stringify(raw);

    // Format 1: JSON array [{"nombre":"...","cargo":"..."}]
    if (text.startsWith("[")) {
      try {
        const arr = JSON.parse(text);
        for (const c of arr.slice(0, 8)) {
          contacts.push({
            name: c.nombre || c.name || "—",
            role: c.cargo || c.role || c.clasificacion || "—",
            initials: initials(c.nombre || c.name || ""),
            inDeal: c.clasificacion?.toLowerCase().includes("decision") || false,
            risk: c.clasificacion?.toLowerCase().includes("blocker") || false,
          });
        }
      } catch { /* fall through to markdown */ }
    }

    // Format 2: Markdown **Name** – Role...
    if (!contacts.length) {
      const re = /\*\*([^*]+)\*\*\s*[–—\-:]\s*([^\n]+)/g;
      let m;
      while ((m = re.exec(text)) !== null && contacts.length < 8) {
        const name = m[1].trim();
        const role = m[2].trim().slice(0, 80);
        contacts.push({ name, role, initials: initials(name) });
      }
    }

    // Format 3: Markdown - **Name** (without –)
    if (!contacts.length) {
      const re2 = /[-•]\s*\*\*([^*]+)\*\*[^:\n]*?(?:Cargo|Rol|rol)[:\s]*([^\n.]+)/gi;
      let m2;
      while ((m2 = re2.exec(text)) !== null && contacts.length < 8) {
        contacts.push({ name: m2[1].trim(), role: m2[2].trim().slice(0, 60), initials: initials(m2[1].trim()) });
      }
    }
  }

  // Fallback: deals.contacts_info ("Name | Role | Email" per line)
  if (!contacts.length && contactsInfo) {
    for (const line of contactsInfo.split("\n")) {
      const parts = line.split("|").map(s => s.trim());
      if (parts.length >= 2 && parts[0]) {
        contacts.push({
          name: parts[0],
          role: parts[1] || "—",
          initials: initials(parts[0]),
          inDeal: true,
        });
      }
      if (contacts.length >= 8) break;
    }
  }

  return contacts;
}

function parseContactsBreakdown(breakdown: string | null): Contact[] {
  if (!breakdown) return [];
  const contacts: Contact[] = [];
  const blocks = breakdown.split(/\n-\s+/).filter(Boolean);
  for (const block of blocks) {
    const lines = block.split("\n").map(l => l.trim());
    const name = lines[0]?.replace(/^-\s*/, "").trim();
    if (!name || name === "(sin nombre)") continue;
    const cargoLine = lines.find(l => l.startsWith("Cargo:"));
    const emailLine = lines.find(l => l.startsWith("Email:"));
    const cargo = cargoLine?.replace("Cargo:", "").trim() || "";
    const email = emailLine?.replace("Email:", "").trim() || "";
    const role = [cargo, email].filter(Boolean).join(" · ") || "—";
    contacts.push({ name, role, initials: initials(name) });
    if (contacts.length >= 10) break;
  }
  return contacts;
}

// Build stage roadmap from deal entered/exited timestamps
function buildRoadmap(deal: any, currentStage: string): DealDetail["roadmap"] {
  const stageOrder = [
    { key: "sdr_prequalified", label: "Prequalified" },
    { key: "sdr_attempting_to_contact", label: "Attempting to contact" },
    { key: "sdr_engaged", label: "Engaged" },
    { key: "dist_demo_booked", label: "Demo Booked" },
    { key: "dist_product_alignment", label: "Product Alignment" },
    { key: "dist_meddpicc_validation", label: "MEDDPICC" },
    { key: "dist_pricing_and_packaging", label: "Pricing & Packaging" },
    { key: "dist_contracting", label: "Contracting" },
    { key: "dist_closed_won", label: "Closed Won" },
    { key: "sales_meeting_booked", label: "Meeting Booked" },
    { key: "sales_discovery", label: "Discovery" },
    { key: "sales_product_alignment", label: "Product Alignment" },
    { key: "sales_pricing_and_packaging", label: "Pricing & Packaging" },
    { key: "sales_contracting", label: "Contracting" },
    { key: "sales_closed_won", label: "Closed Won" },
  ];

  const steps: DealDetail["roadmap"] = [];
  const seen = new Set<string>();

  for (const s of stageOrder) {
    const entered = deal[s.key + "_entered"];
    const exited = deal[s.key + "_exited"];
    if (!entered) continue;
    if (seen.has(s.label)) continue;
    seen.add(s.label);

    const range = exited ? `${entered} → ${exited}` : `${entered} →`;
    const dur = exited ? daysBetween(entered, exited) : "en curso";
    const done = !!exited;
    steps.push({ stage: s.label, range, dur, done });
  }

  // Mark current
  if (steps.length) {
    const last = steps[steps.length - 1];
    if (!last.done) last.current = true;
  }

  if (!steps.length) {
    steps.push({ stage: currentStage, range: "—", dur: "—", done: false, current: true });
  }

  return steps;
}

function parseJson(raw: any): any {
  if (!raw) return null;
  if (typeof raw === "object") return raw;
  try { return JSON.parse(raw); } catch { return null; }
}

function parseDealsBreakdown(text: string | null): { status: string; name: string; owner: string; date?: string }[] {
  if (!text) return [];
  const deals: { status: string; name: string; owner: string; date?: string }[] = [];
  const blocks = text.split(/\n-\s+/).filter(Boolean);
  for (const block of blocks) {
    const lines = block.split("\n").map(l => l.trim());
    const name = lines[0]?.replace(/^-\s*/, "").trim();
    if (!name) continue;
    const estadoLine = lines.find(l => l.startsWith("Estado:"));
    const ownerLine = lines.find(l => l.startsWith("Owner:"));
    const cierreLine = lines.find(l => l.startsWith("Cierre:"));
    const estado = estadoLine?.replace("Estado:", "").trim() || "";
    const isLost = /PERDIDO|CERRADO|lost/i.test(estado);
    deals.push({
      status: isLost ? "PERDIDO" : "ACTIVO",
      name,
      owner: ownerLine?.replace("Owner:", "").trim() || "—",
      date: cierreLine?.replace("Cierre:", "").trim(),
    });
  }
  return deals;
}

function buildAtlasData(
  company: string, deal: any, atlas: any, snap: any,
  contacts: Contact[],
  siblingDeals: { status: string; name: string; owner: string; date?: string }[],
): DealDetail["atlas"] {
  const card = parseJson(atlas?.company_card);
  const insights = parseJson(atlas?.deal_insights);

  // Tags from atlas fields
  const tags: string[] = [];
  if (atlas?.industry) tags.push(atlas.industry);
  if (atlas?.country) tags.push(atlas.country);
  if (atlas?.company_size) tags.push(atlas.company_size + " empleados");
  if (atlas?.website) tags.push(atlas.website);

  // Fit from company_card or fallback
  const fitScore = card?.fit?.score || null;
  const fitLevel = fitScore === "alto" ? "Fit alto" : fitScore === "medio" ? "Fit medio" : fitScore === "bajo" ? "Fit bajo" : "Fit por validar";
  const fitText = card?.fit?.reason || snap?.deal_assessment?.split(".")[0] || "—";

  // Facts from company_card.key_facts or fallback
  const facts = card?.key_facts?.length
    ? card.key_facts.map((f: any) => ({ k: f.label, v: f.value }))
    : [
        { k: "Stage", v: deal.deal_stage || "—" },
        { k: "MRR", v: deal.amount ? "€" + deal.amount : "—" },
        { k: "Empleados", v: atlas?.company_size || "—" },
        { k: "PAE", v: deal.pae || "—" },
      ];

  // History summary
  const historyNote = card?.history_summary || atlas?.deal_history?.slice(0, 150) || "Reconstruido desde HubSpot + Modjo.";

  // Warnings from company_card
  const warnings: string[] = card?.warnings || [];

  // Signals & blockers from deal_insights (for Atlas view, separate from snapshot signals)
  const atlasBuyingSignals = insights?.buying_signals?.map((s: any) => ({
    strength: s.strength === "fuerte" || s.strength === "alta" ? "Fuerte" : "Moderada",
    text: s.signal,
  })) || [];

  const atlasBlockers = insights?.blockers?.map((b: any) => ({
    sev: b.severity === "alto" ? "alto" : "medio",
    text: b.blocker,
  })) || [];

  // Loss reasons from deal_insights (deals field can be string or array)
  const lossReasons = insights?.loss_reasons?.length
    ? insights.loss_reasons.map((lr: any) => ({
        reason: lr.reason || lr,
        deals: Array.isArray(lr.deals) ? lr.deals : typeof lr.deals === "string" ? lr.deals.split(",").map((s: string) => s.trim()) : [],
      }))
    : siblingDeals.filter(d => d.status === "PERDIDO").length
      ? siblingDeals.filter(d => d.status === "PERDIDO").map(d => ({
          reason: `Deal perdido: ${d.name}`,
          deals: [d.name],
        }))
      : null;

  // Patterns from deal_insights
  const patterns: string[] = insights?.patterns || parseBullets(snap?.improvements).slice(0, 4);

  // Merge contacts: contacts_map (analyzed) + contacts_breakdown (raw from HubSpot)
  const breakdownContacts = parseContactsBreakdown(atlas?.contacts_breakdown);
  const allContactNames = new Set(contacts.map(c => c.name.toLowerCase()));
  for (const bc of breakdownContacts) {
    if (!allContactNames.has(bc.name.toLowerCase())) {
      contacts.push(bc);
      allContactNames.add(bc.name.toLowerCase());
    }
  }

  return {
    company,
    tags: tags.length ? tags : [deal.deal_stage || ""],
    crm: "HubSpot",
    description: card?.headline || (atlas?.company_context?.split(".").slice(0, 2).join(".") + ".") || snap?.deal_summary?.split(".")[0] + "." || "Sin información de empresa.",
    fit: { level: fitLevel, text: fitText },
    facts,
    historyNote,
    warnings,
    contacts,
    deals: [
      { status: "ACTIVO", name: deal.deal_name || "—", owner: deal.pae || "—" },
      ...siblingDeals,
    ],
    lostReasons: lossReasons,
    patterns,
    // Extra: pass atlas-level signals/blockers for the Atlas view
    _signals: atlasBuyingSignals,
    _blockers: atlasBlockers,
  } as any;
}

export async function fetchDealDetail(dealId: string): Promise<DealDetail | null> {
  // Fetch deal + atlas
  const { data: deal } = await supabase
    .from("deals")
    .select("*, atlas:atlas_id(company_name,company_size,company_context,contacts_map,contacts_breakdown,deals_breakdown,website,company_card,deal_insights,deal_history,industry,country)")
    .eq("id", dealId)
    .single();

  if (!deal) return null;

  // Fetch all snapshots for timeline + latest
  const { data: snaps } = await supabase
    .from("front_deal_snapshots")
    .select("snapshot_date,close_probability,action_signal,deal_summary,deal_assessment,live_blockers,buyer_signals,next_step,m_score,m_accumulate,e_score,e_accumulate,dc_score,dc_accumulate,dp_score,dp_accumulate,i_score,i_accumulate,c_score,c_accumulate,comp_score,comp_accumulate,claudio_forecast,objections,deal_strengths,improvements,howto_label,howto_body")
    .eq("deal_id", dealId)
    .order("snapshot_date", { ascending: false })
    .limit(10);

  const snap = snaps?.[0] || null;

  // Fetch latest BANT from pbd_audits
  const { data: bantAudits } = await supabase
    .from("pbd_audits")
    .select("bant_budget_status,bant_budget_evidence,bant_authority_status,bant_authority_evidence,bant_need_status,bant_need_evidence,bant_timing_status,bant_timing_evidence")
    .eq("deal_ref", dealId)
    .order("created_at", { ascending: false })
    .limit(1);

  // Fetch sibling deals: prefer deals_breakdown from atlas (has ALL deals including
  // ones not linked by atlas_id), fallback to querying deals table
  const atlasRaw = deal.atlas as any;
  let siblingDeals: { status: string; name: string; owner: string; date?: string }[] = [];
  const breakdownDeals = parseDealsBreakdown(atlasRaw?.deals_breakdown);
  if (breakdownDeals.length) {
    siblingDeals = breakdownDeals.filter(d => d.name !== deal.deal_name);
  } else if (deal.atlas_id) {
    const LOST_STAGES = ["Opportunity lost", "Closed lost", "Closed Lost", "Opportunity Lost"];
    const { data: siblings } = await supabase
      .from("deals")
      .select("id,deal_name,deal_stage,pae,close_date")
      .eq("atlas_id", deal.atlas_id)
      .neq("id", dealId)
      .limit(20);
    siblingDeals = (siblings || []).map(s => ({
      status: LOST_STAGES.includes(s.deal_stage || "") ? "PERDIDO" : "ACTIVO",
      name: s.deal_name || "—",
      owner: s.pae || "—",
      date: s.close_date || undefined,
    }));
  }

  // Fetch contacts from ALL sibling deals (not just current deal)
  let allContactsInfo = deal.contacts_info || "";
  if (deal.atlas_id) {
    const { data: siblingContactRows } = await supabase
      .from("deals")
      .select("contacts_info")
      .eq("atlas_id", deal.atlas_id)
      .neq("id", dealId)
      .not("contacts_info", "is", null)
      .limit(20);
    for (const row of siblingContactRows || []) {
      if (row.contacts_info) allContactsInfo += "\n" + row.contacts_info;
    }
  }

  // Fetch lost reasons from atlas.deal_insights
  const bant = bantAudits?.[0] || null;
  const atlas = deal.atlas as any;
  const prob = snap?.close_probability ?? null;
  const company = atlas?.company_name || deal.deal_name?.split(" - ")[0]?.split(" | ")[0]?.trim() || "—";

  // MEDDIC (7 pillars including Comp)
  const meddic: Record<string, { score: number; text: string }> = {
    M:    { score: snap?.m_score ?? 0,    text: snap?.m_accumulate || "Sin datos" },
    E:    { score: snap?.e_score ?? 0,    text: snap?.e_accumulate || "Sin datos" },
    DC:   { score: snap?.dc_score ?? 0,   text: snap?.dc_accumulate || "Sin datos" },
    DP:   { score: snap?.dp_score ?? 0,   text: snap?.dp_accumulate || "Sin datos" },
    I:    { score: snap?.i_score ?? 0,    text: snap?.i_accumulate || "Sin datos" },
    C:    { score: snap?.c_score ?? 0,    text: snap?.c_accumulate || "Sin datos" },
    Comp: { score: snap?.comp_score ?? 0, text: snap?.comp_accumulate || "Sin datos" },
  };

  // Timeline from historical snapshots
  const timeline = (snaps || []).filter(s => s.close_probability != null).reverse().map(s => ({
    date: s.snapshot_date,
    prob: s.close_probability!,
  }));
  if (!timeline.length && prob != null) {
    timeline.push({ date: new Date().toISOString().slice(0, 10), prob });
  }

  // Trend
  let trend: number | null = null;
  if (snaps && snaps.length >= 2 && snaps[0].close_probability != null && snaps[1].close_probability != null) {
    trend = snaps[0].close_probability - snaps[1].close_probability;
  }

  // Parse signal
  const actionText = snap?.action_signal || "Sin acción pendiente";
  const signal = {
    kind: parseSignalKind(actionText),
    text: actionText.replace(/\[(?:CALL|EMAIL|SLIDES|ROI|BATTLECARD)\]\s*/g, ""),
    due: "hoy",
  };

  // Howto: prefer dedicated fields, fall back to deal_assessment
  const howto = {
    context: snap?.howto_label || snap?.deal_assessment?.split(".")[0]?.slice(0, 60) || "Avanzar el deal",
    text: snap?.howto_body || snap?.deal_assessment || snap?.deal_summary || "Sin evaluación disponible.",
  };

  // Blockers & signals
  const blockers = parseBullets(snap?.live_blockers).map(t => ({
    sev: /crítico|alto|lost|perdido/i.test(t) ? "alto" : "medio",
    text: t,
  }));
  const buyerSignals = parseBullets(snap?.buyer_signals).map(t => ({
    strength: /fuerte|strong|confirmad/i.test(t) ? "Fuerte" : "Moderada",
    text: t,
  }));

  // Next steps — parse format: "• [TAG] Quién → acción — cuándo"
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  const nextStepLines = parseBullets(snap?.next_step);
  const nextSteps = nextStepLines.slice(0, 6).map(line => {
    const kind = parseSignalKind(line);
    const clean = line.replace(/\[(?:CALL|EMAIL|SLIDES|ROI|BATTLECARD)\]\s*/g, "");
    const arrowMatch = clean.match(/^([^→]+)→\s*(.+?)(?:\s*—\s*(.+))?$/);
    if (arrowMatch) {
      return { kind, who: arrowMatch[1].trim(), text: cap(arrowMatch[2].trim()), when: arrowMatch[3]?.trim() || "pendiente" };
    }
    const dashMatch = clean.match(/^(.+?)\s*—\s*(.+?)(?:\s*—\s*(.+))?$/);
    if (dashMatch && dashMatch[1].split(" ").length <= 3) {
      return { kind, who: dashMatch[1].trim(), text: cap(dashMatch[2].trim()), when: dashMatch[3]?.trim() || "pendiente" };
    }
    return { kind, who: deal.pae || "PAE", text: cap(clean), when: "pendiente" };
  });
  // Sort by timing urgency, then by tag importance
  const WHEN_ORDER: Record<string, number> = { "hoy": 0, "ahora": 0, "inmediatamente": 0, "durante la call": 1, "tras la call": 2, "inmediatamente después": 2, "mañana": 3, "esta semana": 4, "antes de": 4, "si no": 5, "viernes": 5, "pendiente": 6 };
  const KIND_ORDER: Record<string, number> = { "CALL": 0, "EMAIL": 1, "ROI": 2, "SLIDES": 3, "BATTLECARD": 4, "PREP": 5 };
  const whenScore = (w: string) => {
    const wl = (w || "pendiente").toLowerCase();
    for (const [key, score] of Object.entries(WHEN_ORDER)) {
      if (wl.includes(key)) return score;
    }
    return 5;
  };
  nextSteps.sort((a, b) => {
    const wDiff = whenScore(a.when) - whenScore(b.when);
    if (wDiff !== 0) return wDiff;
    return (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9);
  });

  if (!nextSteps.length) {
    nextSteps.push({ kind: "CALL", who: deal.pae || "PAE", text: "Contactar para avanzar el deal.", when: "pendiente" });
  }

  // Roadmap
  const roadmap = buildRoadmap(deal, deal.deal_stage || "—");

  // Contacts from atlas
  const contacts = parseContacts(atlas?.contacts_map, allContactsInfo);

  // Fetch briefings + slides + email_drafts + product intel for this deal
  const [{ data: briefingRows }, { data: slideRows }, { data: emailRows }, { data: productRows }] = await Promise.all([
    supabase.from("briefings").select("status,share_url").eq("deal_id", dealId).order("created_at", { ascending: false }).limit(1),
    supabase.from("slides").select("status,share_url").eq("deal_id", dealId).order("created_at", { ascending: false }).limit(1),
    supabase.from("email_drafts").select("recipient,send_when,reason,subject,body,status").eq("deal_id", dealId).order("created_at", { ascending: false }).limit(1),
    supabase.from("deal_product_signals").select("product_assessment,product_actions,expansion_summary").eq("deal_id", dealId).order("snapshot_date", { ascending: false }).limit(1),
  ]);

  const briefing = briefingRows?.[0];
  const slide = slideRows?.[0];
  const emailDraft = emailRows?.[0];

  // Product intel
  const piRaw = productRows?.[0];
  console.log("[fetchDetail] product raw:", piRaw);
  let productActions: { product: string; type: string; text: string }[] = [];
  if (piRaw?.product_actions) {
    try { productActions = typeof piRaw.product_actions === "string" ? JSON.parse(piRaw.product_actions) : piRaw.product_actions; } catch (e) { console.warn("[fetchDetail] product_actions parse error:", e); }
  }
  const productData = {
    products: [...new Set(productActions.map(a => a.product))].sort(),
    assessment: piRaw?.product_assessment || "",
    actions: productActions.filter(a => a.type !== "upsell"),
    upsells: productActions.filter(a => a.type === "upsell").map(a => ({ product: a.product, text: a.text })),
    expansion: piRaw?.expansion_summary || null,
  };

  // Tools — mark active if data exists
  const tools = [
    { name: "ROI", sub: "Calculadora", tone: "green" },
    { name: "Slides", sub: slide?.status === "ready" ? "Disponible" : slide ? "Generando..." : "Presentación", tone: "blue", active: slide?.status === "ready" },
    { name: "Battlecard", sub: "vs Competencia", tone: "amber" },
    { name: "Briefing", sub: briefing?.status === "ready" ? "Disponible" : briefing ? "Generando..." : "Prep meeting", tone: "indigo", active: briefing?.status === "ready" },
  ];

  return {
    id: deal.id,
    hsId: deal.deal_id || null,
    name: deal.deal_name || "—",
    stage: deal.deal_stage || "—",
    pae: deal.pae || "—",
    pbd: deal.pbd || "—",
    lastContact: deal.last_contacted_hs || "—",
    mrr: deal.amount ?? "—",
    prob,
    closeDate: deal.close_date || "—",
    forecast: snap?.claudio_forecast ? "€" + Math.round(snap.claudio_forecast) : "—",
    employees: atlas?.company_size || "—",
    trend,
    signal,
    howto,
    meddic,
    product: productData,
    bant: {
      overall: bant
        ? `B: ${bantLabel(bant.bant_budget_status)} · A: ${bantLabel(bant.bant_authority_status)} · N: ${bantLabel(bant.bant_need_status)} · T: ${bantLabel(bant.bant_timing_status)}`
        : "Sin datos BANT — no hay auditorías PBD para este deal.",
      items: [
        { key: "B", label: "Budget", status: bantLabel(bant?.bant_budget_status), tone: bantTone(bant?.bant_budget_status), text: bant?.bant_budget_evidence || "Sin datos" },
        { key: "A", label: "Authority", status: bantLabel(bant?.bant_authority_status), tone: bantTone(bant?.bant_authority_status), text: bant?.bant_authority_evidence || "Sin datos" },
        { key: "N", label: "Need", status: bantLabel(bant?.bant_need_status), tone: bantTone(bant?.bant_need_status), text: bant?.bant_need_evidence || "Sin datos" },
        { key: "T", label: "Timing", status: bantLabel(bant?.bant_timing_status), tone: bantTone(bant?.bant_timing_status), text: bant?.bant_timing_evidence || "Sin datos" },
      ],
    },
    summary: snap?.deal_assessment || snap?.deal_summary || atlas?.company_context || "Sin resumen disponible.",
    signals: buyerSignals.length ? buyerSignals : [{ strength: "—", text: "Sin señales de compra identificadas." }],
    blockers: blockers.length ? blockers : [{ sev: "—", text: "Sin blockers identificados." }],
    timeline,
    roadmap,
    nextSteps,
    tools,
    email: emailDraft ? {
      from: deal.pae || "Factorial",
      fromAddr: (deal.pae || "ventas").toLowerCase().replace(/ /g, ".") + "@factorial.co",
      fromInit: initials(deal.pae || "FA"),
      to: emailDraft.recipient || company,
      toAddr: emailDraft.recipient || "",
      when: emailDraft.send_when || "Pendiente",
      reason: emailDraft.reason || "Follow up",
      subject: emailDraft.subject || `Siguientes pasos — ${company}`,
      body: (emailDraft.body || "").split("\n\n").filter(Boolean),
      signoff: `Un saludo,\n${deal.pae || "Factorial"}`,
    } : null,
    atlas: buildAtlasData(company, deal, atlas, snap, contacts, siblingDeals),
  };
}
