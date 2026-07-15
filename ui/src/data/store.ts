import { createContext, useContext } from "react";

// ---- Types ----

export type DealRow = {
  id?: string;
  hsId?: string;
  deal: string;
  sub?: string;
  stage: string;
  mrr: number | null;
  prob: number | null;
  last: string;
  trend: number | null;
  closeDateHs: string | null;
  closeDateClaudio: string | null;
  owner: string;
  team?: string;
  meetingPaes?: string[];
  hora?: string;
  hero?: boolean;
  atlas?: string;
  stale?: boolean;
  signal?: string;
  score?: number;
  pipeline?: string;
};

export type Group = {
  id: string;
  title: string;
  meta: string;
  tint: string;
  rows: DealRow[];
};

export type FunnelStage = {
  key: string;
  label: string;
  tone: string;
  count: number;
  value: number;
  stale: number;
  rows: DealRow[];
};

export type ForecastDeal = DealRow & {
  closesThisMonth: boolean;
  closesNextMonth: boolean;
  pushable: boolean;
  pushAction: string | null;
  momentum: string | null;
  confidence: string | null;
  claudioCloseDate: string | null;
  forecastReasoning: string | null;
  forecastRisks: string | null;
  forecastAccelerators: string | null;
  hsCategory: string;
  closeDate: string | null;
};

export type ClosedDeal = DealRow & {
  dealAge: number | null;
  strengths: string | null;
  lessons: string[];
  interactions: { total_calls?: number; total_emails?: number } | null;
};

export type LostDeal = DealRow & {
  hsId?: string;
  closeDate: string | null;
  lostReason: string | null;
  dealAge: number | null;
};

export type BenchmarkDeal = {
  id?: string;
  hsId?: string;
  deal: string;
  mrr: number | null;
  owner: string;
  team: string;
  closeDate: string | null;
  dealAge: number | null;
  outcome: "won" | "lost";
  meddic: { m: number; e: number; dc: number; dp: number; i: number; c: number };
  meddicText: { m: string | null; e: string | null; dc: string | null; dp: string | null; i: string | null; c: string | null };
  outcomeSummary: string | null;
  dealAssessment: string | null;
  lostReason: string | null;
  employees: string | null;
  fullNarrative: string | null;
  timeline: { event: string; date?: string; detail?: string }[];
  whatWorked: string[];
  whatFailed: string[];
  couldHaveChanged: string | null;
  repAssessment: string | null;
  keyPeople: { name?: string; role?: string; influence?: string }[];
  productsPitched: { product?: string; reception?: string }[];
  productsMissed: { product?: string; reason?: string }[];
  productAssessment: string | null;
  trajectory: { date?: string; probability?: number; meddic?: { m: number; e: number; dc: number; dp: number; i: number; c: number } }[];
  interactions: { total_calls?: number; total_emails?: number; total_notes?: number; modjo_calls?: number; hs_meetings?: number } | null;
  lessons: string[];
  keyTurningPoint: string | null;
  pipeline?: string;
};

export type ForecastData = {
  target: number;
  hsTotal: number;
  closzrTotal: number;
  nextMonthTotal: number;
  pushableCount: number;
  closedTotal: number;
  lostTotal: number;
  hsDeals: ForecastDeal[];
  closzrDeals: ForecastDeal[];
  nextMonthDeals: ForecastDeal[];
  pushableDeals: ForecastDeal[];
  closedDeals: ClosedDeal[];
  lostDeals: LostDeal[];
  allDeals: ForecastDeal[];
  targets: { team: string; month: string; monthly_target: number }[];
  m0Deals: ForecastDeal[];
  m1Deals: ForecastDeal[];
  m2Deals: ForecastDeal[];
};

export type MethodologyItem = {
  n: number;
  label: string;
  tone: string;
  key: string;
  deals: DealRow[];
};

export type OneOnOneData = {
  reps: string[];
  rep: string;
  activeDeals: number;
  pipeline: number;
  top10: any[];
  meddicBase: number;
  meddic: { key: string; score: number }[];
  meddicNote: string;
  weakness: { label: string; count: number }[];
  tlActions: any[];
  methodologyOpen: number;
  methodology: MethodologyItem[];
};

export type ActionItem = {
  id: string;
  dealId: string;
  hsId?: string;
  dealName: string;
  dealOwner: string;
  dealMrr: number | null;
  dealStage: string;
  bucket: string;
  claudioCloseDate: string | null;
  actionHeadline: string;
  actionDetail: string | null;
  actionType: string;
  actionWho: string;
  actionWhen: string;
  actionPriority: number;
  actionDueDate: string | null;
  followUps: { order: number; type: string; who: string; text: string; when: string; due?: string }[];
  status: string;
  team: string;
  pipeline?: string;
};

export type CZData = {
  STAGE: Record<string, { tone: string }>;
  groups: Group[];
  nakiva: any;
  yukAtlas: any;
  pipeline: FunnelStage[];
  pipelineAside: FunnelStage[];
  forecast: ForecastData;
  benchmark: { won: BenchmarkDeal[]; lost: BenchmarkDeal[] };
  oneOnOne: OneOnOneData;
  todos: ActionItem[];
  loading: boolean;
};

export const DataContext = createContext<CZData>(null as any);

export function useData(): CZData {
  return useContext(DataContext);
}
