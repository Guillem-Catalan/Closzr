import { useState, useCallback } from "react";
import { supabase } from "../../data/supabase";

export type ReassignDeal = {
  deal_id: string;
  hs_deal_id: string;
  company_name: string;
  stage: string;
  macro_stage: string;
  mrr: number;
  pae: string;
  pbd: string;
  team: string;
  close_date: string | null;
  role: "pae" | "pbd";
  next_meeting: string | null;
  atlas_industry: string | null;
  atlas_employees: string | null;
  pipeline_name: string | null;
  assigned_to?: string;
};

export type WonDeal = {
  mrr: number;
  atlas_industry: string | null;
  atlas_employees: string | null;
  pipeline_name: string | null;
  close_date: string | null;
};

export type RepCapacity = {
  email: string;
  full_name: string;
  role: string;
  hs_owner_id: string | null;
  deal_count: number;
  total_mrr: number;
  demo_count: number;
  eval_count: number;
  closing_count: number;
  won_deals: WonDeal[];
  lost_count: number;
};

export type ReassignStep = "select_person" | "assign_deals" | "summary" | "safety_confirm" | "confirm";

const DEMO_PLUS = ["demo", "evaluating", "closing"];

export function useReassign() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<ReassignStep>("select_person");
  const [selectedEmail, setSelectedEmail] = useState("");
  const [selectedFullName, setSelectedFullName] = useState("");
  const [deals, setDeals] = useState<ReassignDeal[]>([]);
  const [reps, setReps] = useState<RepCapacity[]>([]);
  const [loadingDeals, setLoadingDeals] = useState(false);
  const [loadingReps, setLoadingReps] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<{ deal_id: string; ok: boolean }[]>([]);

  const openWizard = useCallback(() => {
    setOpen(true);
    setStep("select_person");
    setSelectedEmail("");
    setSelectedFullName("");
    setDeals([]);
    setReps([]);
    setError("");
    setResults([]);
  }, []);

  const closeWizard = useCallback(() => {
    setOpen(false);
    setStep("select_person");
    setSelectedEmail("");
    setSelectedFullName("");
    setDeals([]);
    setReps([]);
    setError("");
    setResults([]);
  }, []);

  const goBack = useCallback(() => {
    setStep(prev => {
      if (prev === "assign_deals") return "select_person";
      if (prev === "summary") return "assign_deals";
      if (prev === "safety_confirm") return "summary";
      return prev;
    });
  }, []);

  const goToSummary = useCallback(() => {
    setStep("summary");
  }, []);

  const goToSafetyConfirm = useCallback(() => {
    setStep("safety_confirm");
  }, []);

  const selectPerson = useCallback(async (email: string, team: string, fullName: string) => {
    setSelectedEmail(email);
    setSelectedFullName(fullName);
    setError("");
    setLoadingDeals(true);
    setLoadingReps(true);

    try {
      const { data: rawDeals, error: dealsErr } = await supabase
        .from("deal_ui")
        .select("deal_id, hs_deal_id, company_name, stage, macro_stage, mrr, pae, pbd, team, close_date, atlas_industry, atlas_employees, pipeline_name")
        .eq("pae", fullName)
        .in("macro_stage", DEMO_PLUS);

      if (dealsErr) {
        setError(`Error cargando deals: ${dealsErr.message}`);
      } else {
        const dealRows = rawDeals || [];
        const enriched: ReassignDeal[] = dealRows.map(d => ({
          ...d,
          mrr: Number(d.mrr) || 0,
          role: "pae" as const,
          next_meeting: null,
          assigned_to: undefined,
        }));

        const demoDeals = enriched.filter(d => d.macro_stage === "demo");
        if (demoDeals.length > 0) {
          const demoIds = demoDeals.map(d => d.deal_id);
          const { data: meetingRows } = await supabase
            .from("deals")
            .select("id, hs_next_meeting_start_time")
            .in("id", demoIds)
            .not("hs_next_meeting_start_time", "is", null);

          if (meetingRows) {
            const meetingMap = new Map(
              meetingRows.map((m: { id: string; hs_next_meeting_start_time: string }) => [m.id, m.hs_next_meeting_start_time])
            );
            for (const d of enriched) {
              if (d.macro_stage === "demo" && meetingMap.has(d.deal_id)) {
                d.next_meeting = meetingMap.get(d.deal_id)!;
              }
            }
          }
        }

        setDeals(enriched);
      }

      // ── Fetch team capacity + historical won/lost ──
      const { data: teamMembers } = await supabase
        .from("orgchart")
        .select("email, full_name, role, hs_owner_id")
        .eq("team_name", team)
        .eq("is_active", true);

      if (teamMembers && teamMembers.length > 0) {
        const repList: RepCapacity[] = [];

        for (const member of teamMembers) {
          if (member.email === email) continue;

          const { data: asPae } = await supabase
            .from("deal_ui")
            .select("mrr, macro_stage")
            .eq("pae", member.full_name)
            .in("macro_stage", DEMO_PLUS);

          const { data: asPbd } = await supabase
            .from("deal_ui")
            .select("mrr, macro_stage")
            .eq("pbd", member.full_name)
            .in("macro_stage", DEMO_PLUS);

          const active = [...(asPae || []), ...(asPbd || [])];

          const { data: wonPae } = await supabase
            .from("deal_ui")
            .select("mrr, atlas_industry, atlas_employees, pipeline_name, close_date")
            .eq("pae", member.full_name)
            .eq("outcome", "won");

          const { data: wonPbd } = await supabase
            .from("deal_ui")
            .select("mrr, atlas_industry, atlas_employees, pipeline_name, close_date")
            .eq("pbd", member.full_name)
            .eq("outcome", "won");

          const wonDeals: WonDeal[] = [...(wonPae || []), ...(wonPbd || [])].map(d => ({
            mrr: Number(d.mrr) || 0,
            atlas_industry: d.atlas_industry,
            atlas_employees: d.atlas_employees,
            pipeline_name: d.pipeline_name,
            close_date: d.close_date,
          }));

          const { count: lostPaeCount } = await supabase
            .from("deal_ui")
            .select("*", { count: "exact", head: true })
            .eq("pae", member.full_name)
            .eq("outcome", "lost");

          const { count: lostPbdCount } = await supabase
            .from("deal_ui")
            .select("*", { count: "exact", head: true })
            .eq("pbd", member.full_name)
            .eq("outcome", "lost");

          repList.push({
            email: member.email,
            full_name: member.full_name,
            role: member.role,
            hs_owner_id: member.hs_owner_id,
            deal_count: active.length,
            total_mrr: active.reduce((s, d) => s + (Number(d.mrr) || 0), 0),
            demo_count: active.filter(d => d.macro_stage === "demo").length,
            eval_count: active.filter(d => d.macro_stage === "evaluating").length,
            closing_count: active.filter(d => d.macro_stage === "closing").length,
            won_deals: wonDeals,
            lost_count: (lostPaeCount || 0) + (lostPbdCount || 0),
          });
        }

        repList.sort((a, b) => a.deal_count - b.deal_count);
        setReps(repList);
      }
    } catch {
      setError("Error de conexion.");
    }

    setLoadingDeals(false);
    setLoadingReps(false);
    setStep("assign_deals");
  }, []);

  const assignDeal = useCallback((dealId: string, newEmail: string) => {
    setDeals(prev =>
      prev.map(d => {
        if (d.deal_id !== dealId) return d;
        // Toggle: if already assigned to this email, unassign
        if (d.assigned_to === newEmail) return { ...d, assigned_to: undefined };
        return { ...d, assigned_to: newEmail };
      }),
    );
  }, []);

  const someAssigned = deals.some(d => d.assigned_to);

  const confirmReassign = useCallback(async () => {
    const toReassign = deals.filter(d => d.assigned_to);
    if (toReassign.length === 0) return;

    setSaving(true);
    setError("");

    const jobData = toReassign.map(d => ({
      deal_id: d.deal_id,
      new_email: d.assigned_to!,
      role: d.role,
      company_name: d.company_name,
      mrr: d.mrr,
    }));

    try {
      const { data, error: fnErr } = await supabase.functions.invoke("orgchart-ops", {
        body: {
          action: "submit_reassignment",
          source_email: selectedEmail,
          source_name: selectedFullName,
          job_data: jobData,
          requested_by: selectedEmail,
        },
      });

      if (fnErr || !data?.ok) {
        setError(data?.error || fnErr?.message || "Error al aplicar la reasignacion");
        setSaving(false);
        return;
      }

      const dealResults = (data.results || []) as { deal_id: string; ok: boolean }[];
      setResults(dealResults);
      setSaving(false);
      setStep("confirm");
    } catch {
      setError("Error de conexion.");
      setSaving(false);
    }
  }, [deals, selectedEmail, selectedFullName]);

  return {
    open,
    step,
    selectedEmail,
    selectedFullName,
    deals,
    reps,
    loadingDeals,
    loadingReps,
    saving,
    error,
    results,
    someAssigned,
    openWizard,
    closeWizard,
    goBack,
    goToSummary,
    goToSafetyConfirm,
    selectPerson,
    assignDeal,
    confirmReassign,
  };
}
