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
          { id: "01.1", text: "Deals con Close Date en el pasado → actualizar fecha o mover a Closed Lost", query: "past_close" },
          { id: "01.2", text: "Deals en mismo stage +30 días → ¿por qué no avanza? Acción concreta o cerrar", query: "same_stage_30d" },
          { id: "01.3", text: "Deals sin actividad últimos 7 días → el AE explica qué pasó y define próximo paso", query: "stale_7d" },
          { id: "01.4", text: "Deals con demo date +6 semanas de antigüedad → marcar Ageing, acelerar o mejorar la higiene", query: "demo_6w" },
        ],
      },
      {
        num: "02", title: "MES ACTUAL (M+0)", tone: "amber",
        items: [
          { id: "02.1", text: "AE confirma que M+0 está bajo control: forecast claro, riesgos nombrados y próximos pasos definidos", query: "m0" },
          { id: "02.2", text: "Si hay gap por segmento, alinear con SDs qué generación o matching se necesita este mes" },
          { id: "02.3", text: "¿Hay algún bloqueo real donde el TL debe intervenir? (Director, partner, contractual)" },
          { id: "02.4", text: "El AE actualiza el Forecast Submission según lo acordado" },
        ],
      },
    ],
  },
  {
    type: 1, label: "W1", subtitle: "Setup completo",
    sections: [
      {
        num: "01", title: "PRE-SESIÓN", tone: "indigo",
        items: [
          { id: "01.1", text: "Abre pipeline filtrada por AE, ordenada por Close Date" },
          { id: "01.2", text: "Identifica deals con Close Date en el pasado o sin actividad últimos 7 días", query: "past_close_or_stale" },
          { id: "01.3", text: "Anota todos los deals de M+1 — en esta primera sesión los revisarás todos", query: "m1" },
          { id: "01.4", text: "Calcula coverage M+1: suma MRR deals M+1 / cuota mensual del AE", metric: "coverage_m1" },
        ],
      },
      {
        num: "02", title: "HIGIENE DEL PIPELINE", tone: "red",
        items: [
          { id: "02.1", text: "Deals con Close Date en el pasado → actualizar fecha o mover a Closed Lost", query: "past_close" },
          { id: "02.2", text: "Deals en mismo stage +30 días → ¿por qué no avanza? Acción concreta o cerrar", query: "same_stage_30d" },
          { id: "02.3", text: "Deals sin actividad últimos 7 días → el AE explica qué pasó y define próximo paso", query: "stale_7d" },
          { id: "02.4", text: "Deals con demo date +6 semanas de antigüedad → marcar Ageing, acelerar o mejorar la higiene", query: "demo_6w" },
        ],
      },
      {
        num: "03", title: "MES ACTUAL (M+0)", tone: "amber",
        items: [
          { id: "03.1", text: "AE confirma que M+0 está bajo control: forecast claro, riesgos nombrados y próximos pasos definidos", query: "m0" },
          { id: "03.2", text: "Si hay gap por segmento, alinear con SDs qué generación o matching se necesita este mes" },
          { id: "03.3", text: "¿Hay algún bloqueo real donde el TL debe intervenir? (Director, partner, contractual)" },
          { id: "03.4", text: "El AE actualiza el Forecast Submission según lo acordado" },
        ],
      },
      {
        num: "04", title: "PRÓXIMOS MESES (M+1 / M+2)", tone: "blue",
        items: [
          { id: "04.1", text: "Por cada deal M+1: ¿el stage refleja dónde está realmente la oportunidad?", query: "m1" },
          { id: "04.2", text: "Por cada deal M+1: ¿la Close Date es realista? ¿El AE puede justificarla con hechos concretos?" },
          { id: "04.3", text: "Por cada deal M+1: ¿cuál es el next step concreto con fecha en los próximos 7 días?" },
          { id: "04.4", text: "Usando 2.5x como guía, ¿M+1 tiene suficiente coverage?", metric: "coverage_m1" },
          { id: "04.5", text: "El AE deja o actualiza la nota por cada deal M+1 revisado; el TL valida claridad" },
          { id: "04.6", text: "Revisión rápida deals M+2 segmento M/L: ¿stage correcto para cerrar en 2 meses?", query: "m2" },
          { id: "04.7", text: "Identificar 1-2 deals de M+2 que podrían acelerarse a M+1 si hay gap de coverage" },
        ],
      },
      {
        num: "05", title: "COMPROMISOS Y CIERRE", tone: "green",
        items: [
          { id: "05.1", text: "AE repite en voz alta sus 2-3 compromisos: deals concretos, acciones concretas, fechas concretas" },
          { id: "05.2", text: "El AE crea o actualiza Tasks para cada compromiso; el TL valida owner, fecha y next step" },
          { id: "05.3", text: "El AE actualiza el Forecast Submission para deals M+1; el TL valida la lógica de forecast" },
          { id: "05.4", text: "El AE añade o actualiza la nota de forecast; el TL valida claridad y próximos pasos" },
          { id: "05.5", text: "Confirmar fecha y hora del próximo 1:1" },
        ],
      },
    ],
  },
  { type: 2, label: "W2", subtitle: "Próximamente", sections: [] },
  { type: 3, label: "W3", subtitle: "Próximamente", sections: [] },
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
