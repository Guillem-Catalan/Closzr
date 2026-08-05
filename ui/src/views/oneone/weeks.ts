export type CheckItem = {
  id: string;
  text: string;
  query?: string;
  queries?: string[];
  guide?: string[];
  metric?: string;
};

export type Section = {
  num: string;
  title: string;
  tone: string;
  time: number;
  items: CheckItem[];
};

export type WeekConfig = {
  type: number;
  label: string;
  subtitle: string;
  duration: number;
  sections: Section[];
};

const HIGIENE_QUERIES = ["past_close", "same_stage_30d", "stale_7d", "demo_6w"];
const HIGIENE_GUIDE = [
  "Fecha pasada|Close Date pasada → actualiza o mueve a lost",
  "Estancado|Mismo stage +30d → define acción concreta o ciérralo",
  "Sin actividad|Sin contacto 7d → pide que explique y define próximo paso",
  "Demo antigua|Demo hace +6 sem → acelera o limpia",
];

const M0_REVIEW_GUIDE = [
  "Forecast|¿El forecast category es correcto?",
  "Riesgos|¿Hay riesgos no nombrados?",
  "Next steps|¿Tiene próximos pasos definidos?",
  "Bloqueos|¿Hay algún bloqueo donde debas intervenir tú?",
];

const M1_REVIEW_GUIDE = [
  "Stage|¿El stage refleja dónde está realmente la oportunidad?",
  "Close Date|¿La Close Date es realista? Que la justifique con hechos",
  "Next step|¿Tiene next step concreto con fecha en los próximos 7 días?",
  "Forecast|¿La nota de forecast es clara?",
];

export const WEEKS: WeekConfig[] = [
  {
    type: 0, label: "W0", subtitle: "Higiene + M0 + M1", duration: 60,
    sections: [
      { num: "01", title: "HIGIENE DEL PIPELINE", tone: "red", time: 20, items: [
        { id: "w0-hyg", text: "Limpieza de pipeline — revisa cada deal problemático, actualiza o cierra", queries: HIGIENE_QUERIES, guide: HIGIENE_GUIDE },
      ]},
      { num: "02", title: "MES ACTUAL — M+0", tone: "amber", time: 15, items: [
        { id: "w0-m0", text: "Revisión deal por deal M+0 — forecast, riesgos y próximos pasos", query: "m0", guide: M0_REVIEW_GUIDE },
        { id: "w0-m0-gap", text: "Si hay gap por segmento, alinead generación o matching con SDs" },
        { id: "w0-m0-fc", text: "Pide que actualice el Forecast Submission con lo acordado" },
      ]},
      { num: "03", title: "PRÓXIMO MES — M+1", tone: "blue", time: 15, items: [
        { id: "w0-m1", text: "Revisión deal por deal M+1 — stage, fecha y next steps", query: "m1", guide: M1_REVIEW_GUIDE, metric: "coverage_m1" },
      ]},
      { num: "04", title: "COMPROMISOS", tone: "green", time: 10, items: [
        { id: "w0-comp", text: "Pide que resuma 2-3 compromisos: deals concretos, acciones y fechas" },
        { id: "w0-next", text: "Confirmad fecha y hora del próximo 1:1" },
      ]},
    ],
  },
  {
    type: 1, label: "W1", subtitle: "Pipe building", duration: 45,
    sections: [
      { num: "01", title: "HIGIENE RÁPIDA", tone: "red", time: 5, items: [
        { id: "w1-hyg", text: "Limpieza rápida — solo deals nuevos con problemas desde W0", queries: HIGIENE_QUERIES, guide: HIGIENE_GUIDE },
      ]},
      { num: "02", title: "M+0 — CONFIRMAR", tone: "amber", time: 5, items: [
        { id: "w1-m0", text: "Confirma que M+0 va según previsto — solo alertas o cambios importantes", query: "m0", guide: ["Cambios|¿Algún cambio desde W0?", "Riesgo|¿Algún deal en riesgo?", "Bloqueos|¿Necesita tu ayuda para desbloquear algo?"] },
      ]},
      { num: "03", title: "M+1 / M+2 — DEEP REVIEW", tone: "blue", time: 25, items: [
        { id: "w1-m1", text: "Revisión deal por deal M+1 — stage, fecha, next step y nota de forecast", query: "m1", guide: [...M1_REVIEW_GUIDE, "Notas|Pide que deje o actualice la nota de cada deal revisado"], metric: "coverage_m1" },
        { id: "w1-m2", text: "Pasada rápida M+2 — ¿stage correcto para cerrar en 2 meses?", query: "m2", guide: ["Stage|¿El stage es correcto para el timeline?", "Coverage|Si coverage M+1 corto, identifica 1-2 deals para acelerar a M+1"] },
      ]},
      { num: "04", title: "COMPROMISOS", tone: "green", time: 5, items: [
        { id: "w1-comp", text: "Pide que resuma compromisos: deals, acciones y fechas concretas" },
        { id: "w1-next", text: "Confirmad próximo 1:1" },
      ]},
    ],
  },
  {
    type: 2, label: "W2", subtitle: "Lock M+1 & push", duration: 45,
    sections: [
      { num: "01", title: "M+1 — LOCK", tone: "blue", time: 20, items: [
        { id: "w2-m1", text: "Seguimiento M+1 — estado real, forecast category, última actividad", query: "m1", guide: ["Forecast|¿El forecast category sigue siendo correcto?", "Contacto|¿Cuál fue el último contacto y qué respuesta hubo?", "Sin actividad|Sin actividad 5+ días → contactar esta semana o bajar de forecast", "Submission|Pide que actualice el Forecast Submission de M+1"], metric: "coverage_m1" },
      ]},
      { num: "02", title: "PUSH M+2 → M+1", tone: "indigo", time: 10, items: [
        { id: "w2-push", text: "Deals pusheables — momentum positivo o prob ≥40%, ¿se pueden adelantar?", query: "m1_m2_pusheable", guide: ["Acelerar|¿Qué haría falta para cerrar un mes antes?", "Coverage|Si gap de coverage M+1, elegid 1-3 deals de M+2 para acelerar"] },
        { id: "w2-m2", text: "Revisión general M+2 — stage y fecha correctos", query: "m2" },
      ]},
      { num: "03", title: "M+0 — RÁPIDA", tone: "amber", time: 5, items: [
        { id: "w2-m0", text: "M+0 — cambios desde W1 y deals en riesgo", query: "m0", guide: ["Cambios|¿Algún cambio importante?", "Riesgo|Deals sin actividad o momentum negativo → acción esta semana", "Bloqueos|¿Necesita tu ayuda para desbloquear?"] },
      ]},
      { num: "04", title: "COMPROMISOS", tone: "green", time: 5, items: [
        { id: "w2-comp", text: "Pide que resuma compromisos: deals, acciones y fechas" },
        { id: "w2-next", text: "Confirmad próximo 1:1" },
      ]},
    ],
  },
  {
    type: 3, label: "W3", subtitle: "Cierre M+0", duration: 45,
    sections: [
      { num: "01", title: "M+0 — FOCO TOTAL EN CIERRE", tone: "red", time: 25, items: [
        { id: "w3-m0", text: "Revisión deal por deal M+0 — qué falta para cerrar cada uno", query: "m0", guide: ["Cierre|¿Quién firma? ¿Cuándo? ¿Paso intermedio que pueda retrasarlo?", "Limbo|Si no cierra este mes → mueve a M+1 o lost, no dejar en limbo", "Bloqueos|¿Hay bloqueo por contrato, legal o pricing? Define quién resuelve y cuándo"] },
        { id: "w3-m0-soon", text: "Deals que cierran esta semana — confirmar o alertar slip", query: "m0_closing_soon", guide: ["Confirmación|¿Están confirmados o hay riesgo de slip?", "Urgencia|Acción concreta hoy o mañana, no 'la semana que viene'"] },
      ]},
      { num: "02", title: "INTERVENCIÓN DEL TL", tone: "amber", time: 10, items: [
        { id: "w3-tl", text: "¿En qué deals necesita que entres tú? Llamada a director, email a partner, escalación", guide: ["Bloqueos|Deals bloqueados por contrato, legal o pricing", "Contacto|Contacto tuyo con el cliente que pueda acelerar la decisión"] },
      ]},
      { num: "03", title: "M+1 — RÁPIDA", tone: "blue", time: 5, items: [
        { id: "w3-m1", text: "Pasada rápida M+1 — ¿algún cambio desde W2?", query: "m1" },
      ]},
      { num: "04", title: "CIERRE Y COMPROMISOS", tone: "green", time: 5, items: [
        { id: "w3-cierre", text: "Recuento final M+0 — MRR pendiente, ¿alcanzable? Pide Forecast Submission final", query: "m0" },
        { id: "w3-comp", text: "Compromisos de cierre: quién hace qué, cuándo. Confirmad próximo 1:1" },
      ]},
    ],
  },
];

export const PROBLEM_LABELS: Record<string, string> = {
  past_close: "Fecha pasada",
  same_stage_30d: "Estancado +30d",
  stale_7d: "Sin actividad",
  demo_6w: "Demo antigua",
};

export function getWeekType(date: Date = new Date()): number {
  return Math.min(3, Math.floor((date.getDate() - 1) / 7));
}

export function getMonday(date: Date = new Date()): string {
  const d = new Date(date);
  const day = d.getDay();
  d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
  return d.toISOString().slice(0, 10);
}

export function getMondayOfWeek(yearMonth: string, weekType: number): string {
  const [y, m] = yearMonth.split("-").map(Number);
  const targetDay = weekType * 7 + 4;
  const d = new Date(y, m - 1, targetDay);
  const day = d.getDay();
  d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
  return d.toISOString().slice(0, 10);
}

export function currentYearMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
