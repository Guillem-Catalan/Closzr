export type CheckItem = {
  id: string;
  text: string;
  query?: string;
  metric?: string;
};

export type Section = {
  num: string;
  title: string;
  tone: string;
  items: CheckItem[];
};

export type WeekConfig = {
  type: number;
  label: string;
  subtitle: string;
  sections: Section[];
};

export const WEEKS: WeekConfig[] = [
  {
    type: 0, label: "W0", subtitle: "Higiene + M0",
    sections: [
      {
        num: "01", title: "HIGIENE DEL PIPELINE", tone: "red",
        items: [
          { id: "01.1", text: "Revisa los deals con Close Date en el pasado — actualiza la fecha o muévelos a Closed Lost", query: "past_close" },
          { id: "01.2", text: "Revisa deals estancados en el mismo stage +30 días — pregunta por qué no avanza y define una acción concreta o ciérralo", query: "same_stage_30d" },
          { id: "01.3", text: "Repasa deals sin actividad en los últimos 7 días — pide que explique qué pasó y define el próximo paso", query: "stale_7d" },
          { id: "01.4", text: "Mira deals con demo de hace +6 semanas — marca Ageing, acelera o limpia", query: "demo_6w" },
        ],
      },
      {
        num: "02", title: "MES ACTUAL (M+0)", tone: "amber",
        items: [
          { id: "02.1", text: "Pide que confirme M+0: forecast claro, riesgos nombrados y próximos pasos definidos para cada deal", query: "m0" },
          { id: "02.2", text: "Si hay gap por segmento, alinead qué generación o matching se necesita con SDs este mes" },
          { id: "02.3", text: "Pregunta si hay algún bloqueo real donde debas intervenir tú (Director, partner, contractual)" },
          { id: "02.4", text: "Pide que actualice el Forecast Submission según lo que habéis acordado" },
        ],
      },
    ],
  },
  {
    type: 1, label: "W1", subtitle: "Setup completo",
    sections: [
      {
        num: "01", title: "PRE-SESIÓN (prepara antes del 1:1)", tone: "indigo",
        items: [
          { id: "01.1", text: "Abre la pipeline filtrada por este AE, ordenada por Close Date" },
          { id: "01.2", text: "Identifica deals con Close Date pasada o sin actividad en 7 días", query: "past_close_or_stale" },
          { id: "01.3", text: "Apunta todos los deals de M+1 — en esta sesión los vais a revisar todos", query: "m1" },
          { id: "01.4", text: "Calcula el coverage de M+1: suma MRR de deals M+1 / cuota mensual", metric: "coverage_m1" },
        ],
      },
      {
        num: "02", title: "HIGIENE DEL PIPELINE", tone: "red",
        items: [
          { id: "02.1", text: "Revisa los deals con Close Date en el pasado — actualiza la fecha o muévelos a Closed Lost", query: "past_close" },
          { id: "02.2", text: "Revisa deals estancados en el mismo stage +30 días — pregunta por qué no avanza y define una acción concreta o ciérralo", query: "same_stage_30d" },
          { id: "02.3", text: "Repasa deals sin actividad en los últimos 7 días — pide que explique qué pasó y define el próximo paso", query: "stale_7d" },
          { id: "02.4", text: "Mira deals con demo de hace +6 semanas — marca Ageing, acelera o limpia", query: "demo_6w" },
        ],
      },
      {
        num: "03", title: "MES ACTUAL (M+0)", tone: "amber",
        items: [
          { id: "03.1", text: "Pide que confirme M+0: forecast claro, riesgos nombrados y próximos pasos definidos para cada deal", query: "m0" },
          { id: "03.2", text: "Si hay gap por segmento, alinead qué generación o matching se necesita con SDs este mes" },
          { id: "03.3", text: "Pregunta si hay algún bloqueo real donde debas intervenir tú (Director, partner, contractual)" },
          { id: "03.4", text: "Pide que actualice el Forecast Submission según lo que habéis acordado" },
        ],
      },
      {
        num: "04", title: "PRÓXIMOS MESES (M+1 / M+2)", tone: "blue",
        items: [
          { id: "04.1", text: "Deal por deal en M+1: comprueba que el stage refleja dónde está realmente la oportunidad", query: "m1" },
          { id: "04.2", text: "Pregunta por cada deal M+1: ¿la Close Date es realista? Pide que la justifique con hechos concretos" },
          { id: "04.3", text: "Para cada deal M+1: pide el next step concreto con fecha en los próximos 7 días" },
          { id: "04.4", text: "Comprueba el coverage de M+1 (guía: 2.5x) — si hay gap, hablad de dónde sacar más pipeline", metric: "coverage_m1" },
          { id: "04.5", text: "Pide que deje o actualice la nota de cada deal M+1 revisado — valida que sea clara" },
          { id: "04.6", text: "Haz una pasada rápida por M+2 segmento M/L: ¿el stage es correcto para cerrar en 2 meses?", query: "m2" },
          { id: "04.7", text: "Identifica 1-2 deals de M+2 que se puedan acelerar a M+1 si el coverage es corto" },
        ],
      },
      {
        num: "05", title: "COMPROMISOS Y CIERRE", tone: "green",
        items: [
          { id: "05.1", text: "Pide que repita en voz alta sus 2-3 compromisos: deals concretos, acciones concretas, fechas concretas" },
          { id: "05.2", text: "Revisa que cree o actualice Tasks para cada compromiso — valida owner, fecha y next step" },
          { id: "05.3", text: "Pide que actualice el Forecast Submission para M+1 — valida la lógica de forecast" },
          { id: "05.4", text: "Comprueba que la nota de forecast esté clara y con próximos pasos" },
          { id: "05.5", text: "Cerrad confirmando fecha y hora del próximo 1:1" },
        ],
      },
    ],
  },
  {
    type: 2, label: "W2", subtitle: "Lock M+1 & push pipe",
    sections: [
      {
        num: "01", title: "SEGUIMIENTO M+1", tone: "blue",
        items: [
          { id: "01.1", text: "Repasa deal por deal en M+1 — pide el estado real de cada uno y si el forecast category sigue siendo correcto", query: "m1" },
          { id: "01.2", text: "Para cada deal M+1: pregunta cuál fue el último contacto y qué respuesta hubo" },
          { id: "01.3", text: "Si algún deal M+1 no ha tenido actividad en 5+ días, pide que contacte esta semana o lo baje de forecast", query: "stale_7d" },
          { id: "01.4", text: "Comprueba el coverage de M+1 (guía: 2.5x) — si está corto, pasad a la sección de push", metric: "coverage_m1" },
          { id: "01.5", text: "Pide que actualice el Forecast Submission de M+1 con lo que habéis acordado" },
        ],
      },
      {
        num: "02", title: "DEALS PUSHEABLES (M+2 → M+1)", tone: "indigo",
        items: [
          { id: "02.1", text: "Revisa los deals de M+2 con momentum positivo o probabilidad ≥40% — ¿se pueden adelantar a M+1?", query: "m1_m2_pusheable" },
          { id: "02.2", text: "Para cada deal pusheable: pregunta qué haría falta para cerrar un mes antes (reunión, propuesta, aprobación)" },
          { id: "02.3", text: "Si hay gap de coverage en M+1, elegid juntos 1-3 deals de M+2 para acelerar y definid acciones concretas" },
          { id: "02.4", text: "Revisa deals M+2 en general — ¿el stage y la fecha son correctos o necesitan actualización?", query: "m2" },
        ],
      },
      {
        num: "03", title: "M+0 — REVISIÓN RÁPIDA", tone: "amber",
        items: [
          { id: "03.1", text: "Pregunta cómo van los deals de M+0 que revisasteis la semana pasada — ¿algún cambio importante?", query: "m0" },
          { id: "03.2", text: "Si hay deals M+0 en riesgo (sin actividad o momentum negativo), define una acción esta semana", query: "m0_at_risk" },
          { id: "03.3", text: "Pregunta si necesita tu ayuda para desbloquear algo de M+0 esta semana" },
        ],
      },
      {
        num: "04", title: "COMPROMISOS", tone: "green",
        items: [
          { id: "04.1", text: "Pide que resuma sus compromisos: qué deals va a mover, qué acciones concretas, para cuándo" },
          { id: "04.2", text: "Revisa que los Tasks estén creados o actualizados para cada compromiso" },
          { id: "04.3", text: "Cerrad confirmando fecha y hora del próximo 1:1" },
        ],
      },
    ],
  },
  {
    type: 3, label: "W3", subtitle: "Cierre M+0",
    sections: [
      {
        num: "01", title: "M+0 — FOCO TOTAL EN CIERRE", tone: "red",
        items: [
          { id: "01.1", text: "Repasa todos los deals de M+0 uno por uno — pregunta exactamente qué falta para cerrar cada uno", query: "m0" },
          { id: "01.2", text: "Identifica los deals M+0 que cierran esta semana — ¿están confirmados o hay riesgo de slip?", query: "m0_closing_soon" },
          { id: "01.3", text: "Para cada deal en riesgo: define una acción concreta que haga hoy o mañana, no 'la semana que viene'", query: "m0_at_risk" },
          { id: "01.4", text: "Pregunta deal por deal: ¿quién firma? ¿cuándo? ¿hay algún paso intermedio que pueda retrasarlo?" },
          { id: "01.5", text: "Si algún deal M+0 ya no va a cerrar este mes, muévelo a M+1 o a Lost — no lo dejes en limbo" },
        ],
      },
      {
        num: "02", title: "INTERVENCIÓN DEL TL", tone: "amber",
        items: [
          { id: "02.1", text: "Pregunta en qué deals concretos necesita que entres tú: llamada a director, email a partner, escalación interna" },
          { id: "02.2", text: "Si hay algún deal bloqueado por contrato, legal o pricing — define quién lo resuelve y para cuándo" },
          { id: "02.3", text: "Revisa si hay algún deal donde un contacto tuyo con el cliente pueda acelerar la decisión" },
        ],
      },
      {
        num: "03", title: "CIERRE DE MES", tone: "green",
        items: [
          { id: "03.1", text: "Haz un recuento final de M+0: ¿cuánto MRR queda por cerrar? ¿Es alcanzable?", query: "m0" },
          { id: "03.2", text: "Pide que actualice el Forecast Submission final del mes — tiene que reflejar la realidad" },
          { id: "03.3", text: "Cerrad con los compromisos de cierre: quién hace qué, cuándo y qué pasa si no se cierra" },
        ],
      },
    ],
  },
];

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
