import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const hsToken = Deno.env.get("HUBSPOT_TOKEN");
  if (!hsToken) return _err("HUBSPOT_TOKEN not configured");

  const { action, ...params } = await req.json();

  try {
    switch (action) {
      case "update_close_date": {
        const { hs_deal_id, new_date } = params as { hs_deal_id: string; new_date: string };
        if (!hs_deal_id || !new_date) return _err("hs_deal_id and new_date required");

        const resp = await fetch(
          `https://api.hubapi.com/crm/v3/objects/deals/${hs_deal_id}`,
          {
            method: "PATCH",
            headers: { Authorization: `Bearer ${hsToken}`, "Content-Type": "application/json" },
            body: JSON.stringify({ properties: { closedate: new_date } }),
          },
        );

        if (!resp.ok) {
          const body = await resp.text();
          return _err(`HubSpot API error: ${resp.status} — ${body}`);
        }

        return _ok({ hs_deal_id, new_date, updated: true });
      }

      case "mark_lost": {
        const { hs_deal_id, lost_reason, detail } = params as {
          hs_deal_id: string; lost_reason: string; detail?: string;
        };
        if (!hs_deal_id || !lost_reason) return _err("hs_deal_id and lost_reason required");

        const properties: Record<string, string> = {
          dealstage: "closedlost",
          hs_manual_forecast_category: "omit",
          closed_lost_reason: lost_reason,
        };
        if (detail) properties.closed_lost_detail = detail;

        const resp = await fetch(
          `https://api.hubapi.com/crm/v3/objects/deals/${hs_deal_id}`,
          {
            method: "PATCH",
            headers: { Authorization: `Bearer ${hsToken}`, "Content-Type": "application/json" },
            body: JSON.stringify({ properties }),
          },
        );

        if (!resp.ok) {
          const body = await resp.text();
          return _err(`HubSpot API error: ${resp.status} — ${body}`);
        }

        return _ok({ hs_deal_id, lost_reason, updated: true });
      }

      case "add_note": {
        const { hs_deal_id, note } = params as { hs_deal_id: string; note: string };
        if (!hs_deal_id || !note) return _err("hs_deal_id and note required");

        const noteResp = await fetch(
          "https://api.hubapi.com/crm/v3/objects/notes",
          {
            method: "POST",
            headers: { Authorization: `Bearer ${hsToken}`, "Content-Type": "application/json" },
            body: JSON.stringify({
              properties: { hs_note_body: note, hs_timestamp: new Date().toISOString() },
            }),
          },
        );

        if (!noteResp.ok) {
          const body = await noteResp.text();
          return _err(`HubSpot note create error: ${noteResp.status} — ${body}`);
        }

        const noteData = await noteResp.json();
        const noteId = noteData.id;

        const assocResp = await fetch(
          `https://api.hubapi.com/crm/v3/objects/notes/${noteId}/associations/deals/${hs_deal_id}/note_to_deal`,
          {
            method: "PUT",
            headers: { Authorization: `Bearer ${hsToken}`, "Content-Type": "application/json" },
          },
        );

        if (!assocResp.ok) {
          const body = await assocResp.text();
          return _err(`HubSpot association error: ${assocResp.status} — ${body}`);
        }

        return _ok({ hs_deal_id, note_id: noteId, created: true });
      }

      case "update_forecast": {
        const { hs_deal_id, category } = params as { hs_deal_id: string; category: string };
        if (!hs_deal_id || !category) return _err("hs_deal_id and category required");

        const resp = await fetch(
          `https://api.hubapi.com/crm/v3/objects/deals/${hs_deal_id}`,
          {
            method: "PATCH",
            headers: { Authorization: `Bearer ${hsToken}`, "Content-Type": "application/json" },
            body: JSON.stringify({ properties: { hs_manual_forecast_category: category.toLowerCase() } }),
          },
        );

        if (!resp.ok) {
          const body = await resp.text();
          return _err(`HubSpot API error: ${resp.status} — ${body}`);
        }

        return _ok({ hs_deal_id, category, updated: true });
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
