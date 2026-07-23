import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  const { action, ...params } = await req.json();

  try {
    switch (action) {
      // ── 1. Lookup: find HubSpot owner by email ──────────────────
      case "lookup": {
        const { email } = params as { email: string };
        if (!email) return _err("email required");

        const hsToken = Deno.env.get("HUBSPOT_TOKEN");
        if (!hsToken) return _err("HUBSPOT_TOKEN not configured");

        const resp = await fetch(
          `https://api.hubapi.com/crm/v3/owners?email=${encodeURIComponent(email)}&limit=1`,
          { headers: { Authorization: `Bearer ${hsToken}` } },
        );

        if (!resp.ok) {
          return _err(`HubSpot API error: ${resp.status}`);
        }

        const data = await resp.json();
        const owners = data.results || [];

        if (owners.length === 0) {
          return _ok({ found: false, email });
        }

        const owner = owners[0];
        return _ok({
          found: true,
          email,
          hs_owner_id: String(owner.id),
          full_name: [owner.firstName, owner.lastName].filter(Boolean).join(" "),
        });
      }

      // ── 2. Move team: update team on all deals for a person ─────
      case "update_team": {
        const { email, new_team } = params as { email: string; new_team: string };
        if (!email || !new_team) return _err("email and new_team required");

        // Resolve display name — pae/pbd columns store display names, not emails
        const { data: person } = await supabase
          .from("orgchart")
          .select("full_name")
          .eq("email", email)
          .single();
        const displayName = person?.full_name || email;

        const { count: dealsCount } = await supabase
          .from("deals")
          .update({ team: new_team })
          .or(`pae.eq.${displayName},pbd.eq.${displayName}`)
          .select("*", { count: "exact", head: true });

        const { count: uiCount } = await supabase
          .from("deal_ui")
          .update({ team: new_team })
          .or(`pae.eq.${displayName},pbd.eq.${displayName}`)
          .select("*", { count: "exact", head: true });

        return _ok({
          email,
          new_team,
          deals_updated: dealsCount ?? 0,
          deal_ui_updated: uiCount ?? 0,
        });
      }

      // ── 3. Reassign deals: move all deals from one person to another
      case "reassign_deals": {
        const { old_email, new_email } = params as {
          old_email: string;
          new_email: string;
        };
        if (!old_email || !new_email) return _err("old_email and new_email required");

        // Resolve display names — pae/pbd columns store display names, not emails
        const { data: oldPerson } = await supabase
          .from("orgchart")
          .select("full_name")
          .eq("email", old_email)
          .single();
        const oldDisplayName = oldPerson?.full_name || old_email;

        const { data: newPerson } = await supabase
          .from("orgchart")
          .select("full_name, team_name, hs_owner_id")
          .eq("email", new_email)
          .single();

        const newDisplayName = newPerson?.full_name || new_email;
        const newTeam = newPerson?.team_name || "";

        // Update deals table (pae/pbd = display name)
        await supabase
          .from("deals")
          .update({ pae: newDisplayName, team: newTeam })
          .eq("pae", oldDisplayName);

        await supabase
          .from("deals")
          .update({ pbd: newDisplayName, team: newTeam })
          .eq("pbd", oldDisplayName);

        // Update deal_ui table (pae/pbd = display name)
        await supabase
          .from("deal_ui")
          .update({ pae: newDisplayName, team: newTeam })
          .eq("pae", oldDisplayName);

        await supabase
          .from("deal_ui")
          .update({ pbd: newDisplayName, team: newTeam })
          .eq("pbd", oldDisplayName);

        return _ok({ old_email, new_email, new_team: newTeam });
      }

      // ── 4. Get Demo+ deals for a person (reassignment wizard) ──
      case "get_reassign_deals": {
        const { email } = params as { email: string };
        if (!email) return _err("email required");

        const { data: deals, error: dealsErr } = await supabase
          .from("deal_ui")
          .select("deal_id, hs_deal_id, company_name, stage, macro_stage, mrr, pae, pbd, team, close_date")
          .or(`pae.eq.${email},pbd.eq.${email}`)
          .in("macro_stage", ["demo", "evaluating", "closing"]);

        if (dealsErr) return _err(dealsErr.message);

        const dealIds = (deals || []).map((d: Record<string, unknown>) => d.deal_id);
        const meetingMap: Record<string, string> = {};
        if (dealIds.length > 0) {
          const { data: meetingRows } = await supabase
            .from("deals")
            .select("id, hs_next_meeting_start_time")
            .in("id", dealIds)
            .not("hs_next_meeting_start_time", "is", null);

          if (meetingRows) {
            for (const m of meetingRows as { id: string; hs_next_meeting_start_time: string }[]) {
              meetingMap[m.id] = m.hs_next_meeting_start_time;
            }
          }
        }

        const enriched = (deals || []).map((d: Record<string, unknown>) => ({
          ...d,
          role: d.pae === email ? "pae" : "pbd",
          next_meeting: d.macro_stage === "demo" ? (meetingMap[d.deal_id as string] || null) : null,
        }));

        return _ok({ email, deals: enriched });
      }

      // ── 5. Get team rep capacity (deal counts, MRR, availability) ──
      case "get_team_capacity": {
        const { team, exclude_email } = params as { team: string; exclude_email?: string };
        if (!team) return _err("team required");

        const { data: teamMembers } = await supabase
          .from("orgchart")
          .select("email, full_name, role, hs_owner_id")
          .eq("team_name", team)
          .eq("is_active", true);

        if (!teamMembers || teamMembers.length === 0) {
          return _ok({ team, reps: [] });
        }

        type DealRow = { mrr: number | null; macro_stage: string };
        const reps = [];
        for (const member of teamMembers as { email: string; full_name: string; role: string; hs_owner_id: string | null }[]) {
          if (exclude_email && member.email === exclude_email) continue;

          const { data: asPae } = await supabase
            .from("deal_ui")
            .select("mrr, macro_stage")
            .eq("pae", member.email)
            .in("macro_stage", ["demo", "evaluating", "closing"]);

          const { data: asPbd } = await supabase
            .from("deal_ui")
            .select("mrr, macro_stage")
            .eq("pbd", member.email)
            .in("macro_stage", ["demo", "evaluating", "closing"]);

          const allDeals: DealRow[] = [...(asPae || []), ...(asPbd || [])] as DealRow[];
          const totalMrr = allDeals.reduce((sum, d) => sum + (Number(d.mrr) || 0), 0);

          reps.push({
            email: member.email,
            full_name: member.full_name,
            role: member.role,
            hs_owner_id: member.hs_owner_id,
            deal_count: allDeals.length,
            total_mrr: totalMrr,
            demo_count: allDeals.filter(d => d.macro_stage === "demo").length,
            eval_count: allDeals.filter(d => d.macro_stage === "evaluating").length,
            closing_count: allDeals.filter(d => d.macro_stage === "closing").length,
          });
        }

        reps.sort((a, b) => a.deal_count - b.deal_count);
        return _ok({ team, reps });
      }

      // ── 6. Reassign deals (inline execution + audit log) ──
      case "submit_reassignment": {
        const { source_email, source_name, job_data, requested_by } = params as {
          source_email: string;
          source_name?: string;
          job_data: { deal_id: string; new_email: string; role: string; company_name?: string; mrr?: number }[];
          requested_by: string;
        };
        if (!source_email || !job_data || job_data.length === 0) {
          return _err("source_email and non-empty job_data required");
        }

        const hsToken = Deno.env.get("HUBSPOT_TOKEN");
        const results: { deal_id: string; ok: boolean; hs_updated?: boolean; error?: string }[] = [];

        for (const item of job_data) {
          try {
            // Look up new person in orgchart
            const { data: person } = await supabase
              .from("orgchart")
              .select("full_name, team_name, hs_owner_id")
              .eq("email", item.new_email)
              .eq("is_active", true)
              .single();

            if (!person) {
              results.push({ deal_id: item.deal_id, ok: false, error: `${item.new_email} not found` });
              continue;
            }

            const displayName = person.full_name;
            const newTeam = person.team_name || "";
            const col = item.role === "pae" ? "pae" : "pbd";

            // Update deals table (display name + team)
            const { error: dealErr } = await supabase
              .from("deals")
              .update({ [col]: displayName, team: newTeam })
              .eq("id", item.deal_id);
            if (dealErr) {
              results.push({ deal_id: item.deal_id, ok: false, error: dealErr.message });
              continue;
            }

            // Update deal_ui table (display name + team)
            const { error: uiErr } = await supabase
              .from("deal_ui")
              .update({ [col]: displayName, team: newTeam })
              .eq("deal_id", item.deal_id);
            if (uiErr) {
              results.push({ deal_id: item.deal_id, ok: false, error: uiErr.message });
              continue;
            }

            // Patch HubSpot owner (PAE role only)
            let hsUpdated = false;
            if (item.role === "pae" && person.hs_owner_id && hsToken) {
              const { data: dealRow } = await supabase
                .from("deal_ui")
                .select("hs_deal_id")
                .eq("deal_id", item.deal_id)
                .single();

              if (dealRow?.hs_deal_id) {
                const hsResp = await fetch(
                  `https://api.hubapi.com/crm/v3/objects/deals/${dealRow.hs_deal_id}`,
                  {
                    method: "PATCH",
                    headers: {
                      Authorization: `Bearer ${hsToken}`,
                      "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                      properties: { hubspot_owner_id: String(person.hs_owner_id) },
                    }),
                  },
                );
                hsUpdated = hsResp.ok;
              }
            }

            results.push({ deal_id: item.deal_id, ok: true, hs_updated: hsUpdated });
          } catch (e) {
            results.push({ deal_id: item.deal_id, ok: false, error: e.message });
          }
        }

        // Audit log
        await supabase.from("reassignment_jobs").insert({
          requested_by: requested_by || "unknown",
          source_email,
          source_name: source_name || null,
          job_data,
          status: "done",
          started_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          results,
        });

        const okCount = results.filter(r => r.ok).length;
        return _ok({ results, ok_count: okCount, failed_count: results.length - okCount });
      }

      default:
        return _err(`Unknown action: ${action}`);
    }
  } catch (e) {
    return _err(e.message || "Internal error", 500);
  }
});

function _ok(data: unknown) {
  return new Response(JSON.stringify({ ok: true, ...data as object }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function _err(message: string, status = 400) {
  return new Response(JSON.stringify({ ok: false, error: message }), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
