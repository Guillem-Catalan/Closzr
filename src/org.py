"""
org.py — External Input Mappings (Factorial × HubSpot × Modjo × GCal)

Maps EVERY external input to its internal name or Supabase column.
This is the ONLY file that knows about HubSpot, Modjo, Google Calendar, Slack, etc.

If you switch CRM (HubSpot → Salesforce), rewrite this file. Nothing else changes.
If you're a new company, fill in this file with YOUR system's IDs and properties.

For each section:
  - WHAT: what data this maps
  - WHERE: which external system / API endpoint
  - HOW: how to get it (API call, property name, object type)
  - WHY: what the system uses it for

Structure:
  PART I   — CRM (HubSpot)
  PART II  — CALL PLATFORM (Modjo)
  PART III — CALENDAR (Google Calendar)
  PART IV  — MESSAGING (Slack)
  PART V   — PEOPLE & IDENTITY (Orgchart, Partners)
  PART VI  — DOMAINS (email classification)
  PART VII — API ENDPOINTS & CREDENTIALS
"""

from pathlib import Path
from zoneinfo import ZoneInfo


# ══════════════════════════════════════════════════════════════════════════════
# PART I — CRM (HubSpot)
#
# All data that comes from HubSpot CRM. If switching to Salesforce, Pipedrive,
# or any other CRM, replace this entire part.
#
# HubSpot API docs: https://developers.hubspot.com/docs/api/crm
# Auth: Bearer token via private app (env var HUBSPOT_TOKEN)
# ══════════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────────────
# 1. CRM_DEAL_PROPERTIES
#
# WHAT: Deal properties fetched from HubSpot and synced to Supabase `deals` table.
# WHERE: GET /crm/v3/objects/deals or POST /crm/v3/objects/deals/batch/read
# HOW: Pass property names in `properties` param. HubSpot returns them in response.
# WHY: Core deal data — stage, amount, owner, dates, forecast, activity counters.
#
# Format: "hs_property_name": {"label": "HubSpot UI label", "column": "supabase_column"}
# If column is None, the property is read but not persisted (used in-memory only).
#
# To add a new property:
#   1. Find the internal name in HubSpot Settings → Properties → Deal
#   2. Add it here with the target Supabase column
#   3. Create the column in Supabase if it doesn't exist
# ──────────────────────────────────────────────────────────────────────────────

CRM_DEAL_PROPERTIES = {  # ? ALL keys are HubSpot property names
    # ── Deal identity ──
    "hs_object_id":                          {"label": "Record ID",                      "internal": "deal_id",              "column": "deal_id"},
    "dealname":                              {"label": "Deal Name",                      "internal": "deal_name",            "column": "deal_name"},
    "amount":                                {"label": "Amount (MRR)",                   "internal": "mrr",                  "column": "amount"},
    "dealstage":                             {"label": "Deal Stage",                     "internal": "stage",                "column": "deal_stage"},
    "pipeline":                              {"label": "Pipeline",                       "internal": "pipeline",             "column": "pipeline_name"},
    "closedate":                             {"label": "Close Date",                     "internal": "close_date",           "column": "close_date"},
    "createdate":                            {"label": "Create Date",                    "internal": "create_date",          "column": "createdate"},
    "hs_lastmodifieddate":                   {"label": "Last Modified Date",             "internal": "last_modified",        "column": "last_hs_modified"},

    # ── Owner / team ──
    "hubspot_owner_id":                      {"label": "Deal owner",                     "internal": "owner_id",             "column": "hs_owner_id"},
    "created_by":                            {"label": "Deal created by",                "internal": "creator_id",           "column": "hs_created_by"},
    "hs_all_owner_ids":                      {"label": "All owner IDs",                  "internal": "all_owner_ids",        "column": "hs_all_owner_ids"},
    "current_hubspot_team__string_":         {"label": "Current HubSpot team (string)",  "internal": "team_string",          "column": "hs_team_string"},  # &
    "hubspot_team_id":                       {"label": "HubSpot team",                   "internal": "team_id",              "column": "hs_team_id"},

    # ── Provenance ──
    "partner_name":                          {"label": "Partner name",                   "internal": "partner_name_input",   "column": "partner_name"},  # &
    "marketing_lead_form_campaign_on_deal":  {"label": "Marketing campaign on deal",     "internal": "campaign",             "column": "hs_campaign"},  # &
    "hs_analytics_source":                   {"label": "Original Traffic Source",         "internal": "source",               "column": "hs_source"},

    # ── Forecast ──
    "hs_manual_forecast_category":           {"label": "Forecast category",              "internal": "forecast_category",    "column": "forecast_category"},
    "hs_forecast_probability":               {"label": "Forecast probability",           "internal": "rep_probability",      "column": "rep_probability"},
    "hs_deal_stage_probability":             {"label": "Deal probability",               "internal": "stage_probability_hs", "column": "stage_probability_hs"},

    # ── Activity ──
    "notes_last_contacted":                  {"label": "Last Contacted",                 "internal": "last_contacted",       "column": "last_contacted_hs"},
    "notes_last_updated":                    {"label": "Last Activity Date",             "internal": "last_activity",        "column": "last_activity_hs"},
    "num_associated_contacts":               {"label": "Number of Associated Contacts",  "internal": "contact_count",        "column": "contact_count"},
    "num_contacted_notes":                   {"label": "Number of times contacted",      "internal": "times_contacted",      "column": "num_times_contacted"},
    "num_notes":                             {"label": "Number of Sales Activities",     "internal": "sales_activities",     "column": "num_sales_activities"},
    "hs_next_step":                          {"label": "Next step",                      "internal": "rep_next_step",        "column": "rep_next_step"},
    "hs_latest_meeting_activity":            {"label": "Latest meeting activity",        "internal": "last_meeting",         "column": "last_meeting_hs"},

    # ── Meetings ──
    "first_meeting_at":                      {"label": "First meeting at",               "internal": "first_meeting_at",     "column": "first_meeting_at"},  # &
    "hs_next_meeting_start_time":            {"label": "Next Meeting Start Time",        "internal": "next_meeting",         "column": "hs_next_meeting_start_time"},

    # ── Close status ──
    "closed_lost_reason":                    {"label": "Primary Closed Lost Reason",     "internal": "closed_lost_reason",   "column": "closed_lost_reason"},
    "hs_is_closed_won":                      {"label": "Is Closed Won",                  "internal": "is_closed_won",        "column": "is_closed_won"},
    "hs_is_closed":                          {"label": "Is Deal Closed?",                "internal": "is_closed",            "column": "is_closed"},
    "closed_lost_stage_date":                {"label": "Closed lost stage date",         "internal": "closed_lost_date",     "column": "closed_lost_date"},  # &
    "sqo_date":                              {"label": "SQO date partners",              "internal": "sqo_date",             "column": "sqo_date"},  # &

    # ── Company size ──
    "revised_number_of_emloyeess":           {"label": "Revised number of employees",    "internal": "num_employees",        "column": "num_employees"},
    "numero_de_empleados":                   {"label": "Número de Empleados",            "internal": "num_employees_custom", "column": "num_employees_custom"},  # &

    # ── Champion ──
    "champion_name":                         {"label": "Champion name",                  "internal": "champion",             "column": "champion"},  # &

    # ── Demo dates ──
    "after_demo_date":                       {"label": "Demo Held Date",                 "internal": "after_demo_date",      "column": "after_demo_date"},  # &
    "after_demo_follow_up_meeting_date":     {"label": "After Demo Follow-up Date",      "internal": "after_demo_followup",  "column": "after_demo_followup_date"},  # &
}


# ──────────────────────────────────────────────────────────────────────────────
# 2. CRM_STAGE_MAP
#
# WHAT: Maps CRM-specific stage IDs to display labels.
# WHERE: HubSpot Settings → Objects → Deals → Pipelines → each stage has an ID
# HOW: When HubSpot returns `dealstage` as a raw ID (e.g. "35070729"),
#       look it up here to get the human label ("New Deals").
# WHY: Each pipeline has its OWN stage IDs for the same logical stage
#       (e.g. "Meeting Booked" has 7 different IDs, one per pipeline).
#       Labels then map to internal names via schema.STAGES.
#
# These labels are the BRIDGE between CRM IDs and schema internal names.
# CRM stage ID → display label (here) → schema internal name (in schema.py)
#
# To add stages for a new pipeline:
#   1. Go to HubSpot Settings → Deals → Pipelines → select pipeline
#   2. Copy each stage ID and its label
#   3. Add entries here
#   4. Make sure the label has a matching internal name in schema.STAGES
# ──────────────────────────────────────────────────────────────────────────────

CRM_STAGE_MAP = {  # & ALL entries — stage IDs are account-specific
    # ── Partners Distribution (pipeline 11834984) ──
    "35070729": "New Deals",
    "4977567965": "To reschedule",
    "35070730": "Demo Booked",
    "5366023400": "MEDDPICC Criteria Validation Started",
    "35070731": "Factorial Project Alignment started",
    "35118878": "Economical Alignment Started",
    "35118879": "Contract Sent",
    "104503991": "Closed - pending finance validation",
    "35118880": "Closed Won",
    "1008401982": "On Hold",
    "35119283": "Closed Lost",

    # ── SDR Partner Opportunities (pipeline 684767384) ──
    "1002830265": "Pre-qualified",
    "1002830336": "Attempting to contact",
    "1002830337": "Associating the partner",
    "1002830338": "Engaged",
    "1002830339": "Demo Booked",
    "1002830340": "Nurturing",
    "1002830341": "Opportunity lost",
    "1002829480": "To reschedule",

    # ── Sales Pipeline (pipeline "default") ──
    "f26b487d-e715-49c8-add3-9fa86aef79da": "To reschedule",
    "96e820da-7bc1-4ea3-81a2-bc533ed26934": "Meeting Booked",
    "49b7ad85-a23e-426c-9b3b-d44607d1c3af": "Discovery",
    "appointmentscheduled": "Product Alignment",
    "qualifiedtobuy": "Pricing & Packaging",
    "15738025": "Contracting",
    "51389338": "Closed - pending finance validation",
    "closedwon": "Closed won",
    "closedlost": "Closed lost",

    # ── OB SDR Pipeline (pipeline 9048177) ──
    "25761461": "New",
    "25761462": "Research & Outreach",
    "25761463": "Connected - Not Engaged",
    "26471690": "Engaged",
    "25761464": "Meeting Booked",
    "25761536": "To Reschedule",
    "27564328": "Hot Nurturing",
    "25761465": "Long Nurturing",
    "25761537": "Opportunity lost",

    # ── IB SDR Pipeline (pipeline 831558698) ──
    "1232383505": "New Qualified Opportunity",
    "1232383506": "Attempted to contact",
    "1232383507": "Engaged",
    "1232383508": "Meeting Booked",
    "1232383509": "To Reschedule",
    "1232383510": "Nurturing",
    "1232383511": "Opportunity Lost ",

    # ── XL Account Pipeline (pipeline 685413816) ──
    "1115587680": "Demo request from Prospect",
    "1003800944": "New",
    "1003800946": "Outreach",
    "1003800947": "Engaged",
    "4899425492": "Opportunity Lost",
    "1226596617": "Meeting Booked",
    "4899362020": "To Reschedule",
    "1003685894": "Discovery",
    "4897330392": "Sales Nurturing",
    "1003685895": "Product Alignment",
    "1003685896": "Pricing & Packaging",
    "1003685897": "Contracting",
    "1003800948": "Closed Pending Payment",
    "1003800949": "Closed Won",
    "1003800950": "Closed Lost",

    # ── XL SDR Pipeline (pipeline 3576083668) ──
    "4899425498": "New",
    "4899425499": "Research & Outreach",
    "4899425500": "Connected - Not Engaged",
    "4899425501": "Engaged",
    "4899425502": "Meeting Booked",
    "4899425503": "To reschedule",
    "4899425504": "Hot Nurturing",
    "4899425505": "Long Nurturing",
    "4899425506": "Opportunity Lost",

    # ── IT AE Pipeline (pipeline 824790797) ──
    "1220339227": "Demo request from Prospect",
    "1220339228": "New",
    "1220339229": "Outreach",
    "1220339230": "Engaged",
    "5043758307": "Meeting Booked",
    "5043750115": "To Reschedule",
    "1220339231": "Discovery",
    "1220339232": "Product Alignment",
    "1220339233": "Pricing & Packaging",
    "1220382581": "Contracting",
    "1220382582": "Closed Pending Payment",
    "1220382583": "Closed Won",
    "1220382584": "Closed Lost",
    "5043748053": "Opportunity Lost",
    "5043748049": "Sales Nurturing",

    # ── IT SDR Pipeline (pipeline 3612610753) ──
    "5467457780": "Demo Request from Prospect",
    "4969938161": "New",
    "4969938162": "Research & Outreach",
    "4969938163": "Connected - Not Engaged",
    "4969938164": "Engaged",
    "4969938165": "Meeting Booked",
    "4969938166": "To reschedule",
    "4969938167": "Hot Nurturing",
    "4969938168": "Long Nurturing",
    "4969938169": "Opportunity Lost",

    # ── Stages from excluded pipelines (exist in data, not actively processed) ──
    "12669405": "Closed Won - Finance Only",
    "4965266651": "Contract negotiation (Ongoing) ",
    "14163265": "Meeting scheduled",
    "63255406": "Pricing and Packaging",
}


# ──────────────────────────────────────────────────────────────────────────────
# 3. CRM_PIPELINE_MAP
#
# WHAT: Maps CRM pipeline IDs to pipeline names.
# WHERE: HubSpot Settings → Objects → Deals → Pipelines
# HOW: HubSpot returns pipeline ID in deal's `pipeline` property.
# WHY: Pipeline determines deal routing (partner vs owner-based assignment)
#       and which stage date properties to request.
#
# Pipeline names then map to internal names via schema.PIPELINES.
#
# "active": True = we process deals from this pipeline
# "active": False = excluded (post-sale, other country, internal)
# ──────────────────────────────────────────────────────────────────────────────

CRM_PIPELINE_MAP = {  # & ALL entries — pipeline IDs are account-specific
    # ── Active (new sales) ── prefix = column prefix in schema.STAGE_DATE_FIELDS
    "11834984":    {"name": "Partners Distribution",                "active": True,  "prefix": "dist"},
    "684767384":   {"name": "SDR Partner Opportunities Pipeline",   "active": True,  "prefix": "sdr"},
    "default":     {"name": "Sales Pipeline",                       "active": True,  "prefix": "sales"},
    "9048177":     {"name": "OB SDR Pipeline",                      "active": True,  "prefix": "ob"},
    "831558698":   {"name": "IB SDR Pipeline",                      "active": True,  "prefix": "ib"},
    "685413816":   {"name": "XL Account Pipeline",                  "active": True,  "prefix": "xl"},
    "3576083668":  {"name": "XL SDR Pipeline",                      "active": True,  "prefix": "xlsdr"},
    "824790797":   {"name": "IT AE Pipeline",                       "active": True,  "prefix": "itae"},
    "3612610753":  {"name": "IT SDR Pipeline",                      "active": True,  "prefix": "itsdr"},
    # ── Excluded (post-sale / other) ──
    "12669399":    {"name": "Upselling Pipeline",                   "active": False},
    "120778282":   {"name": "Onboarding Pipeline",                  "active": False},
    "84352288":    {"name": "Churn Pipeline",                       "active": False},
    "14163264":    {"name": "Partner Acquisition",                  "active": False},
    "823385946":   {"name": "BR SDR Pipeline - Outbound",           "active": False},
    "85850465":    {"name": "Brazil Sales Pipeline",                "active": False},
    "3508829384":  {"name": "Consultants Pipeline",                 "active": False},
    "3721428207":  {"name": "Hubspot Shared Pipeline",              "active": False},
}


# ──────────────────────────────────────────────────────────────────────────────
# 4. CRM_STAGE_DATE_PROPERTIES
#
# WHAT: Stage transition timestamps — when a deal entered/exited each stage.
# WHERE: HubSpot auto-generates these as `hs_v2_date_entered_{stage_id}`
#        and `hs_v2_date_exited_{stage_id}` for every stage in every pipeline.
# HOW: Requested alongside deal properties in batch/read calls.
# WHY: Used to calculate stage velocity, build trajectories,
#       detect no-shows, and feed daily/weekly analytics.
#
# ~196 properties across 9 active pipelines.
# Each pipeline section is labeled with its HubSpot pipeline ID.
#
# To add a new pipeline's stage dates:
#   1. Find the pipeline's stage IDs in HubSpot
#   2. Generate entered/exited property names: hs_v2_date_entered_{id}, hs_v2_date_exited_{id}
#   3. Choose Supabase column names following the pattern: {prefix}_{stage_snake}_entered/exited
# ──────────────────────────────────────────────────────────────────────────────

CRM_STAGE_DATE_PROPERTIES = {  # & ALL entries — stage IDs are account-specific
    # ── SDR Partner Opportunities Pipeline (684767384) ──
    "hs_v2_date_entered_1002830265": {"label": 'Date entered "Pre-qualified"',             "internal": "sdr_prequalified_entered", "column": "sdr_prequalified_entered"},
    "hs_v2_date_exited_1002830265":  {"label": 'Date exited "Pre-qualified"',              "internal": "sdr_prequalified_exited", "column": "sdr_prequalified_exited"},
    "hs_v2_date_entered_1002830336": {"label": 'Date entered "Attempting to contact"',     "internal": "sdr_attempting_to_contact_entered", "column": "sdr_attempting_to_contact_entered"},
    "hs_v2_date_exited_1002830336":  {"label": 'Date exited "Attempting to contact"',      "internal": "sdr_attempting_to_contact_exited", "column": "sdr_attempting_to_contact_exited"},
    "hs_v2_date_entered_1002830337": {"label": 'Date entered "Associating the partner"',   "internal": "sdr_associating_the_partner_entered", "column": "sdr_associating_the_partner_entered"},
    "hs_v2_date_exited_1002830337":  {"label": 'Date exited "Associating the partner"',    "internal": "sdr_associating_the_partner_exited", "column": "sdr_associating_the_partner_exited"},
    "hs_v2_date_entered_1002830338": {"label": 'Date entered "Engaged"',                   "internal": "sdr_engaged_entered", "column": "sdr_engaged_entered"},
    "hs_v2_date_exited_1002830338":  {"label": 'Date exited "Engaged"',                    "internal": "sdr_engaged_exited", "column": "sdr_engaged_exited"},
    "hs_v2_date_entered_1002830339": {"label": 'Date entered "Demo Booked"',               "internal": "sdr_demo_booked_entered", "column": "sdr_demo_booked_entered"},
    "hs_v2_date_exited_1002830339":  {"label": 'Date exited "Demo Booked"',                "internal": "sdr_demo_booked_exited", "column": "sdr_demo_booked_exited"},
    "hs_v2_date_entered_1002830340": {"label": 'Date entered "Nurturing"',                 "internal": "sdr_nurturing_entered", "column": "sdr_nurturing_entered"},
    "hs_v2_date_exited_1002830340":  {"label": 'Date exited "Nurturing"',                  "internal": "sdr_nurturing_exited", "column": "sdr_nurturing_exited"},
    "hs_v2_date_entered_1002830341": {"label": 'Date entered "Opportunity lost"',          "internal": "sdr_opportunity_lost_entered", "column": "sdr_opportunity_lost_entered"},
    "hs_v2_date_exited_1002830341":  {"label": 'Date exited "Opportunity lost"',           "internal": "sdr_opportunity_lost_exited", "column": "sdr_opportunity_lost_exited"},
    "hs_v2_date_entered_1002829480": {"label": 'Date entered "To reschedule"',             "internal": "sdr_to_reschedule_entered", "column": "sdr_to_reschedule_entered"},
    "hs_v2_date_exited_1002829480":  {"label": 'Date exited "To reschedule"',              "internal": "sdr_to_reschedule_exited", "column": "sdr_to_reschedule_exited"},

    # ── Partners Distribution Pipeline (11834984) ──
    "hs_v2_date_entered_35070729":   {"label": 'Date entered "New Deals"',                 "internal": "dist_new_deals_entered", "column": "dist_new_deals_entered"},
    "hs_v2_date_exited_35070729":    {"label": 'Date exited "New Deals"',                  "internal": "dist_new_deals_exited", "column": "dist_new_deals_exited"},
    "hs_v2_date_entered_35070730":   {"label": 'Date entered "Demo Booked"',               "internal": "dist_demo_booked_entered", "column": "dist_demo_booked_entered"},
    "hs_v2_date_exited_35070730":    {"label": 'Date exited "Demo Booked"',                "internal": "dist_demo_booked_exited", "column": "dist_demo_booked_exited"},
    "hs_v2_date_entered_35070731":   {"label": 'Date entered "Product Alignment"',         "internal": "dist_product_alignment_entered", "column": "dist_product_alignment_entered"},
    "hs_v2_date_exited_35070731":    {"label": 'Date exited "Product Alignment"',          "internal": "dist_product_alignment_exited", "column": "dist_product_alignment_exited"},
    "hs_v2_date_entered_35070732":   {"label": 'Entered (unused stage)',                   "internal": "dist_do_not_use_entered", "column": "dist_do_not_use_entered"},
    "hs_v2_date_exited_35070732":    {"label": 'Exited (unused stage)',                    "internal": "dist_do_not_use_exited", "column": "dist_do_not_use_exited"},
    "hs_v2_date_entered_35118878":   {"label": 'Date entered "Economical Alignment"',      "internal": "dist_pricing_and_packaging_entered", "column": "dist_pricing_and_packaging_entered"},
    "hs_v2_date_exited_35118878":    {"label": 'Date exited "Economical Alignment"',       "internal": "dist_pricing_and_packaging_exited", "column": "dist_pricing_and_packaging_exited"},
    "hs_v2_date_entered_35118879":   {"label": 'Date entered "Contract Sent"',             "internal": "dist_contracting_entered", "column": "dist_contracting_entered"},
    "hs_v2_date_exited_35118879":    {"label": 'Date exited "Contract Sent"',              "internal": "dist_contracting_exited", "column": "dist_contracting_exited"},
    "hs_v2_date_entered_104503991":  {"label": 'Date entered "Closed - pending finance"',  "internal": "dist_closed_pending_payment_entered", "column": "dist_closed_pending_payment_entered"},
    "hs_v2_date_exited_104503991":   {"label": 'Date exited "Closed - pending finance"',   "internal": "dist_closed_pending_payment_exited", "column": "dist_closed_pending_payment_exited"},
    "hs_v2_date_entered_35118880":   {"label": 'Date entered "Closed Won"',                "internal": "dist_closed_won_entered", "column": "dist_closed_won_entered"},
    "hs_v2_date_exited_35118880":    {"label": 'Date exited "Closed Won"',                 "internal": "dist_closed_won_exited", "column": "dist_closed_won_exited"},
    "hs_v2_date_entered_1008401982": {"label": 'Date entered "On Hold"',                   "internal": "dist_on_hold_entered", "column": "dist_on_hold_entered"},
    "hs_v2_date_exited_1008401982":  {"label": 'Date exited "On Hold"',                    "internal": "dist_on_hold_exited", "column": "dist_on_hold_exited"},
    "hs_v2_date_entered_35119283":   {"label": 'Date entered "Closed Lost"',               "internal": "dist_closed_lost_entered", "column": "dist_closed_lost_entered"},
    "hs_v2_date_exited_35119283":    {"label": 'Date exited "Closed Lost"',                "internal": "dist_closed_lost_exited", "column": "dist_closed_lost_exited"},
    "hs_v2_date_entered_4977567965": {"label": 'Date entered "To reschedule"',             "internal": "dist_to_reschedule_entered", "column": "dist_to_reschedule_entered"},
    "hs_v2_date_exited_4977567965":  {"label": 'Date exited "To reschedule"',              "internal": "dist_to_reschedule_exited", "column": "dist_to_reschedule_exited"},
    "hs_v2_date_entered_5366023400": {"label": 'Date entered "MEDDPICC Validation"',       "internal": "dist_meddpicc_validation_entered", "column": "dist_meddpicc_validation_entered"},
    "hs_v2_date_exited_5366023400":  {"label": 'Date exited "MEDDPICC Validation"',        "internal": "dist_meddpicc_validation_exited", "column": "dist_meddpicc_validation_exited"},

    # ── Sales Pipeline ("default") ──
    "hs_v2_date_entered_96e820da_7bc1_4ea3_81a2_bc533ed26934_2127198906": {"label": 'Date entered "Meeting Booked"',     "internal": "sales_meeting_booked_entered", "column": "sales_meeting_booked_entered"},
    "hs_v2_date_exited_96e820da_7bc1_4ea3_81a2_bc533ed26934_2127198906":  {"label": 'Date exited "Meeting Booked"',      "internal": "sales_meeting_booked_exited", "column": "sales_meeting_booked_exited"},
    "hs_v2_date_entered_49b7ad85_a23e_426c_9b3b_d44607d1c3af_2009251351": {"label": 'Date entered "Discovery"',          "internal": "sales_discovery_entered", "column": "sales_discovery_entered"},
    "hs_v2_date_exited_49b7ad85_a23e_426c_9b3b_d44607d1c3af_2009251351":  {"label": 'Date exited "Discovery"',           "internal": "sales_discovery_exited", "column": "sales_discovery_exited"},
    "hs_v2_date_entered_f26b487d_e715_49c8_add3_9fa86aef79da_127692047":  {"label": 'Date entered "To reschedule"',      "internal": "sales_to_reschedule_entered", "column": "sales_to_reschedule_entered"},
    "hs_v2_date_exited_f26b487d_e715_49c8_add3_9fa86aef79da_127692047":   {"label": 'Date exited "To reschedule"',       "internal": "sales_to_reschedule_exited", "column": "sales_to_reschedule_exited"},
    "hs_v2_date_entered_appointmentscheduled": {"label": 'Date entered "Product Alignment"',    "internal": "sales_product_alignment_entered", "column": "sales_product_alignment_entered"},
    "hs_v2_date_exited_appointmentscheduled":  {"label": 'Date exited "Product Alignment"',     "internal": "sales_product_alignment_exited", "column": "sales_product_alignment_exited"},
    "hs_v2_date_entered_qualifiedtobuy":       {"label": 'Date entered "Pricing & Packaging"',  "internal": "sales_pricing_and_packaging_entered", "column": "sales_pricing_and_packaging_entered"},
    "hs_v2_date_exited_qualifiedtobuy":        {"label": 'Date exited "Pricing & Packaging"',   "internal": "sales_pricing_and_packaging_exited", "column": "sales_pricing_and_packaging_exited"},
    "hs_v2_date_entered_15738025":   {"label": 'Date entered "Contracting"',               "internal": "sales_contracting_entered", "column": "sales_contracting_entered"},
    "hs_v2_date_exited_15738025":    {"label": 'Date exited "Contracting"',                "internal": "sales_contracting_exited", "column": "sales_contracting_exited"},
    "hs_v2_date_entered_51389338":   {"label": 'Date entered "Closed - pending finance"',  "internal": "sales_closed_pending_payment_entered", "column": "sales_closed_pending_payment_entered"},
    "hs_v2_date_exited_51389338":    {"label": 'Date exited "Closed - pending finance"',   "internal": "sales_closed_pending_payment_exited", "column": "sales_closed_pending_payment_exited"},
    "hs_v2_date_entered_closedwon":  {"label": 'Date entered "Closed won"',                "internal": "sales_closed_won_entered", "column": "sales_closed_won_entered"},
    "hs_v2_date_exited_closedwon":   {"label": 'Date exited "Closed won"',                 "internal": "sales_closed_won_exited", "column": "sales_closed_won_exited"},
    "hs_v2_date_entered_closedlost": {"label": 'Date entered "Closed lost"',               "internal": "sales_closed_lost_entered", "column": "sales_closed_lost_entered"},
    "hs_v2_date_exited_closedlost":  {"label": 'Date exited "Closed lost"',                "internal": "sales_closed_lost_exited", "column": "sales_closed_lost_exited"},

    # ── OB SDR Pipeline (9048177) ──
    "hs_v2_date_entered_25761461": {"label": 'Date entered "New"',                     "internal": "ob_new_entered", "column": "ob_new_entered"},
    "hs_v2_date_exited_25761461":  {"label": 'Date exited "New"',                      "internal": "ob_new_exited", "column": "ob_new_exited"},
    "hs_v2_date_entered_25761462": {"label": 'Date entered "Research & Outreach"',     "internal": "ob_research_outreach_entered", "column": "ob_research_outreach_entered"},
    "hs_v2_date_exited_25761462":  {"label": 'Date exited "Research & Outreach"',      "internal": "ob_research_outreach_exited", "column": "ob_research_outreach_exited"},
    "hs_v2_date_entered_25761463": {"label": 'Date entered "Connected - Not Engaged"', "internal": "ob_connected_not_engaged_entered", "column": "ob_connected_not_engaged_entered"},
    "hs_v2_date_exited_25761463":  {"label": 'Date exited "Connected - Not Engaged"',  "internal": "ob_connected_not_engaged_exited", "column": "ob_connected_not_engaged_exited"},
    "hs_v2_date_entered_26471690": {"label": 'Date entered "Engaged"',                 "internal": "ob_engaged_entered", "column": "ob_engaged_entered"},
    "hs_v2_date_exited_26471690":  {"label": 'Date exited "Engaged"',                  "internal": "ob_engaged_exited", "column": "ob_engaged_exited"},
    "hs_v2_date_entered_25761464": {"label": 'Date entered "Meeting Booked"',          "internal": "ob_meeting_booked_entered", "column": "ob_meeting_booked_entered"},
    "hs_v2_date_exited_25761464":  {"label": 'Date exited "Meeting Booked"',           "internal": "ob_meeting_booked_exited", "column": "ob_meeting_booked_exited"},
    "hs_v2_date_entered_25761536": {"label": 'Date entered "To Reschedule"',           "internal": "ob_to_reschedule_entered", "column": "ob_to_reschedule_entered"},
    "hs_v2_date_exited_25761536":  {"label": 'Date exited "To Reschedule"',            "internal": "ob_to_reschedule_exited", "column": "ob_to_reschedule_exited"},
    "hs_v2_date_entered_27564328": {"label": 'Date entered "Hot Nurturing"',           "internal": "ob_hot_nurturing_entered", "column": "ob_hot_nurturing_entered"},
    "hs_v2_date_exited_27564328":  {"label": 'Date exited "Hot Nurturing"',            "internal": "ob_hot_nurturing_exited", "column": "ob_hot_nurturing_exited"},
    "hs_v2_date_entered_25761465": {"label": 'Date entered "Long Nurturing"',          "internal": "ob_long_nurturing_entered", "column": "ob_long_nurturing_entered"},
    "hs_v2_date_exited_25761465":  {"label": 'Date exited "Long Nurturing"',           "internal": "ob_long_nurturing_exited", "column": "ob_long_nurturing_exited"},
    "hs_v2_date_entered_25761537": {"label": 'Date entered "Opportunity lost"',        "internal": "ob_opportunity_lost_entered", "column": "ob_opportunity_lost_entered"},
    "hs_v2_date_exited_25761537":  {"label": 'Date exited "Opportunity lost"',         "internal": "ob_opportunity_lost_exited", "column": "ob_opportunity_lost_exited"},

    # ── IB SDR Pipeline (831558698) ──
    "hs_v2_date_entered_1232383505": {"label": 'Date entered "New Qualified"',         "internal": "ib_new_qualified_entered", "column": "ib_new_qualified_entered"},
    "hs_v2_date_exited_1232383505":  {"label": 'Date exited "New Qualified"',          "internal": "ib_new_qualified_exited", "column": "ib_new_qualified_exited"},
    "hs_v2_date_entered_1232383506": {"label": 'Date entered "Attempted to contact"',  "internal": "ib_attempted_contact_entered", "column": "ib_attempted_contact_entered"},
    "hs_v2_date_exited_1232383506":  {"label": 'Date exited "Attempted to contact"',   "internal": "ib_attempted_contact_exited", "column": "ib_attempted_contact_exited"},
    "hs_v2_date_entered_1232383507": {"label": 'Date entered "Engaged"',               "internal": "ib_engaged_entered", "column": "ib_engaged_entered"},
    "hs_v2_date_exited_1232383507":  {"label": 'Date exited "Engaged"',                "internal": "ib_engaged_exited", "column": "ib_engaged_exited"},
    "hs_v2_date_entered_1232383508": {"label": 'Date entered "Meeting Booked"',        "internal": "ib_meeting_booked_entered", "column": "ib_meeting_booked_entered"},
    "hs_v2_date_exited_1232383508":  {"label": 'Date exited "Meeting Booked"',         "internal": "ib_meeting_booked_exited", "column": "ib_meeting_booked_exited"},
    "hs_v2_date_entered_1232383509": {"label": 'Date entered "To Reschedule"',         "internal": "ib_to_reschedule_entered", "column": "ib_to_reschedule_entered"},
    "hs_v2_date_exited_1232383509":  {"label": 'Date exited "To Reschedule"',          "internal": "ib_to_reschedule_exited", "column": "ib_to_reschedule_exited"},
    "hs_v2_date_entered_1232383510": {"label": 'Date entered "Nurturing"',             "internal": "ib_nurturing_entered", "column": "ib_nurturing_entered"},
    "hs_v2_date_exited_1232383510":  {"label": 'Date exited "Nurturing"',              "internal": "ib_nurturing_exited", "column": "ib_nurturing_exited"},
    "hs_v2_date_entered_1232383511": {"label": 'Date entered "Opportunity Lost"',      "internal": "ib_opportunity_lost_entered", "column": "ib_opportunity_lost_entered"},
    "hs_v2_date_exited_1232383511":  {"label": 'Date exited "Opportunity Lost"',       "internal": "ib_opportunity_lost_exited", "column": "ib_opportunity_lost_exited"},

    # ── XL Account Pipeline (685413816) ──
    "hs_v2_date_entered_1115587680": {"label": 'Date entered "Demo request"',          "internal": "xl_demo_request_entered", "column": "xl_demo_request_entered"},
    "hs_v2_date_exited_1115587680":  {"label": 'Date exited "Demo request"',           "internal": "xl_demo_request_exited", "column": "xl_demo_request_exited"},
    "hs_v2_date_entered_1003800944": {"label": 'Date entered "New"',                   "internal": "xl_new_entered", "column": "xl_new_entered"},
    "hs_v2_date_exited_1003800944":  {"label": 'Date exited "New"',                    "internal": "xl_new_exited", "column": "xl_new_exited"},
    "hs_v2_date_entered_1003800946": {"label": 'Date entered "Outreach"',              "internal": "xl_outreach_entered", "column": "xl_outreach_entered"},
    "hs_v2_date_exited_1003800946":  {"label": 'Date exited "Outreach"',               "internal": "xl_outreach_exited", "column": "xl_outreach_exited"},
    "hs_v2_date_entered_1003800947": {"label": 'Date entered "Engaged"',               "internal": "xl_engaged_entered", "column": "xl_engaged_entered"},
    "hs_v2_date_exited_1003800947":  {"label": 'Date exited "Engaged"',                "internal": "xl_engaged_exited", "column": "xl_engaged_exited"},
    "hs_v2_date_entered_4899425492": {"label": 'Date entered "Opportunity Lost"',      "internal": "xl_opportunity_lost_entered", "column": "xl_opportunity_lost_entered"},
    "hs_v2_date_exited_4899425492":  {"label": 'Date exited "Opportunity Lost"',       "internal": "xl_opportunity_lost_exited", "column": "xl_opportunity_lost_exited"},
    "hs_v2_date_entered_1226596617": {"label": 'Date entered "Meeting Booked"',        "internal": "xl_meeting_booked_entered", "column": "xl_meeting_booked_entered"},
    "hs_v2_date_exited_1226596617":  {"label": 'Date exited "Meeting Booked"',         "internal": "xl_meeting_booked_exited", "column": "xl_meeting_booked_exited"},
    "hs_v2_date_entered_4899362020": {"label": 'Date entered "To Reschedule"',         "internal": "xl_to_reschedule_entered", "column": "xl_to_reschedule_entered"},
    "hs_v2_date_exited_4899362020":  {"label": 'Date exited "To Reschedule"',          "internal": "xl_to_reschedule_exited", "column": "xl_to_reschedule_exited"},
    "hs_v2_date_entered_1003685894": {"label": 'Date entered "Discovery"',             "internal": "xl_discovery_entered", "column": "xl_discovery_entered"},
    "hs_v2_date_exited_1003685894":  {"label": 'Date exited "Discovery"',              "internal": "xl_discovery_exited", "column": "xl_discovery_exited"},
    "hs_v2_date_entered_4897330392": {"label": 'Date entered "Sales Nurturing"',       "internal": "xl_sales_nurturing_entered", "column": "xl_sales_nurturing_entered"},
    "hs_v2_date_exited_4897330392":  {"label": 'Date exited "Sales Nurturing"',        "internal": "xl_sales_nurturing_exited", "column": "xl_sales_nurturing_exited"},
    "hs_v2_date_entered_1003685895": {"label": 'Date entered "Product Alignment"',     "internal": "xl_product_alignment_entered", "column": "xl_product_alignment_entered"},
    "hs_v2_date_exited_1003685895":  {"label": 'Date exited "Product Alignment"',      "internal": "xl_product_alignment_exited", "column": "xl_product_alignment_exited"},
    "hs_v2_date_entered_1003685896": {"label": 'Date entered "Pricing & Packaging"',   "internal": "xl_pricing_packaging_entered", "column": "xl_pricing_packaging_entered"},
    "hs_v2_date_exited_1003685896":  {"label": 'Date exited "Pricing & Packaging"',    "internal": "xl_pricing_packaging_exited", "column": "xl_pricing_packaging_exited"},
    "hs_v2_date_entered_1003685897": {"label": 'Date entered "Contracting"',           "internal": "xl_contracting_entered", "column": "xl_contracting_entered"},
    "hs_v2_date_exited_1003685897":  {"label": 'Date exited "Contracting"',            "internal": "xl_contracting_exited", "column": "xl_contracting_exited"},
    "hs_v2_date_entered_1003800948": {"label": 'Date entered "Closed Pending Payment"', "internal": "xl_closed_pending_payment_entered", "column": "xl_closed_pending_payment_entered"},
    "hs_v2_date_exited_1003800948":  {"label": 'Date exited "Closed Pending Payment"',  "internal": "xl_closed_pending_payment_exited", "column": "xl_closed_pending_payment_exited"},
    "hs_v2_date_entered_1003800949": {"label": 'Date entered "Closed Won"',            "internal": "xl_closed_won_entered", "column": "xl_closed_won_entered"},
    "hs_v2_date_exited_1003800949":  {"label": 'Date exited "Closed Won"',             "internal": "xl_closed_won_exited", "column": "xl_closed_won_exited"},
    "hs_v2_date_entered_1003800950": {"label": 'Date entered "Closed Lost"',           "internal": "xl_closed_lost_entered", "column": "xl_closed_lost_entered"},
    "hs_v2_date_exited_1003800950":  {"label": 'Date exited "Closed Lost"',            "internal": "xl_closed_lost_exited", "column": "xl_closed_lost_exited"},

    # ── XL SDR Pipeline (3576083668) ──
    "hs_v2_date_entered_4899425498": {"label": 'Date entered "New"',                   "internal": "xlsdr_new_entered", "column": "xlsdr_new_entered"},
    "hs_v2_date_exited_4899425498":  {"label": 'Date exited "New"',                    "internal": "xlsdr_new_exited", "column": "xlsdr_new_exited"},
    "hs_v2_date_entered_4899425499": {"label": 'Date entered "Research & Outreach"',   "internal": "xlsdr_research_outreach_entered", "column": "xlsdr_research_outreach_entered"},
    "hs_v2_date_exited_4899425499":  {"label": 'Date exited "Research & Outreach"',    "internal": "xlsdr_research_outreach_exited", "column": "xlsdr_research_outreach_exited"},
    "hs_v2_date_entered_4899425500": {"label": 'Date entered "Connected - Not Engaged"', "internal": "xlsdr_connected_not_engaged_entered", "column": "xlsdr_connected_not_engaged_entered"},
    "hs_v2_date_exited_4899425500":  {"label": 'Date exited "Connected - Not Engaged"',  "internal": "xlsdr_connected_not_engaged_exited", "column": "xlsdr_connected_not_engaged_exited"},
    "hs_v2_date_entered_4899425501": {"label": 'Date entered "Engaged"',               "internal": "xlsdr_engaged_entered", "column": "xlsdr_engaged_entered"},
    "hs_v2_date_exited_4899425501":  {"label": 'Date exited "Engaged"',                "internal": "xlsdr_engaged_exited", "column": "xlsdr_engaged_exited"},
    "hs_v2_date_entered_4899425502": {"label": 'Date entered "Meeting Booked"',        "internal": "xlsdr_meeting_booked_entered", "column": "xlsdr_meeting_booked_entered"},
    "hs_v2_date_exited_4899425502":  {"label": 'Date exited "Meeting Booked"',         "internal": "xlsdr_meeting_booked_exited", "column": "xlsdr_meeting_booked_exited"},
    "hs_v2_date_entered_4899425503": {"label": 'Date entered "To reschedule"',         "internal": "xlsdr_to_reschedule_entered", "column": "xlsdr_to_reschedule_entered"},
    "hs_v2_date_exited_4899425503":  {"label": 'Date exited "To reschedule"',          "internal": "xlsdr_to_reschedule_exited", "column": "xlsdr_to_reschedule_exited"},
    "hs_v2_date_entered_4899425504": {"label": 'Date entered "Hot Nurturing"',         "internal": "xlsdr_hot_nurturing_entered", "column": "xlsdr_hot_nurturing_entered"},
    "hs_v2_date_exited_4899425504":  {"label": 'Date exited "Hot Nurturing"',          "internal": "xlsdr_hot_nurturing_exited", "column": "xlsdr_hot_nurturing_exited"},
    "hs_v2_date_entered_4899425505": {"label": 'Date entered "Long Nurturing"',        "internal": "xlsdr_long_nurturing_entered", "column": "xlsdr_long_nurturing_entered"},
    "hs_v2_date_exited_4899425505":  {"label": 'Date exited "Long Nurturing"',         "internal": "xlsdr_long_nurturing_exited", "column": "xlsdr_long_nurturing_exited"},
    "hs_v2_date_entered_4899425506": {"label": 'Date entered "Opportunity Lost"',      "internal": "xlsdr_opportunity_lost_entered", "column": "xlsdr_opportunity_lost_entered"},
    "hs_v2_date_exited_4899425506":  {"label": 'Date exited "Opportunity Lost"',       "internal": "xlsdr_opportunity_lost_exited", "column": "xlsdr_opportunity_lost_exited"},

    # ── IT AE Pipeline (824790797) ──
    "hs_v2_date_entered_1220339227": {"label": 'Date entered "Demo request"',          "internal": "itae_demo_request_entered", "column": "itae_demo_request_entered"},
    "hs_v2_date_exited_1220339227":  {"label": 'Date exited "Demo request"',           "internal": "itae_demo_request_exited", "column": "itae_demo_request_exited"},
    "hs_v2_date_entered_1220339228": {"label": 'Date entered "New"',                   "internal": "itae_new_entered", "column": "itae_new_entered"},
    "hs_v2_date_exited_1220339228":  {"label": 'Date exited "New"',                    "internal": "itae_new_exited", "column": "itae_new_exited"},
    "hs_v2_date_entered_1220339229": {"label": 'Date entered "Outreach"',              "internal": "itae_outreach_entered", "column": "itae_outreach_entered"},
    "hs_v2_date_exited_1220339229":  {"label": 'Date exited "Outreach"',               "internal": "itae_outreach_exited", "column": "itae_outreach_exited"},
    "hs_v2_date_entered_1220339230": {"label": 'Date entered "Engaged"',               "internal": "itae_engaged_entered", "column": "itae_engaged_entered"},
    "hs_v2_date_exited_1220339230":  {"label": 'Date exited "Engaged"',                "internal": "itae_engaged_exited", "column": "itae_engaged_exited"},
    "hs_v2_date_entered_5043758307": {"label": 'Date entered "Meeting Booked"',        "internal": "itae_meeting_booked_entered", "column": "itae_meeting_booked_entered"},
    "hs_v2_date_exited_5043758307":  {"label": 'Date exited "Meeting Booked"',         "internal": "itae_meeting_booked_exited", "column": "itae_meeting_booked_exited"},
    "hs_v2_date_entered_5043750115": {"label": 'Date entered "To Reschedule"',         "internal": "itae_to_reschedule_entered", "column": "itae_to_reschedule_entered"},
    "hs_v2_date_exited_5043750115":  {"label": 'Date exited "To Reschedule"',          "internal": "itae_to_reschedule_exited", "column": "itae_to_reschedule_exited"},
    "hs_v2_date_entered_1220339231": {"label": 'Date entered "Discovery"',             "internal": "itae_discovery_entered", "column": "itae_discovery_entered"},
    "hs_v2_date_exited_1220339231":  {"label": 'Date exited "Discovery"',              "internal": "itae_discovery_exited", "column": "itae_discovery_exited"},
    "hs_v2_date_entered_1220339232": {"label": 'Date entered "Product Alignment"',     "internal": "itae_product_alignment_entered", "column": "itae_product_alignment_entered"},
    "hs_v2_date_exited_1220339232":  {"label": 'Date exited "Product Alignment"',      "internal": "itae_product_alignment_exited", "column": "itae_product_alignment_exited"},
    "hs_v2_date_entered_1220339233": {"label": 'Date entered "Pricing & Packaging"',   "internal": "itae_pricing_packaging_entered", "column": "itae_pricing_packaging_entered"},
    "hs_v2_date_exited_1220339233":  {"label": 'Date exited "Pricing & Packaging"',    "internal": "itae_pricing_packaging_exited", "column": "itae_pricing_packaging_exited"},
    "hs_v2_date_entered_1220382581": {"label": 'Date entered "Contracting"',           "internal": "itae_contracting_entered", "column": "itae_contracting_entered"},
    "hs_v2_date_exited_1220382581":  {"label": 'Date exited "Contracting"',            "internal": "itae_contracting_exited", "column": "itae_contracting_exited"},
    "hs_v2_date_entered_1220382582": {"label": 'Date entered "Closed Pending Payment"', "internal": "itae_closed_pending_payment_entered", "column": "itae_closed_pending_payment_entered"},
    "hs_v2_date_exited_1220382582":  {"label": 'Date exited "Closed Pending Payment"',  "internal": "itae_closed_pending_payment_exited", "column": "itae_closed_pending_payment_exited"},
    "hs_v2_date_entered_1220382583": {"label": 'Date entered "Closed Won"',            "internal": "itae_closed_won_entered", "column": "itae_closed_won_entered"},
    "hs_v2_date_exited_1220382583":  {"label": 'Date exited "Closed Won"',             "internal": "itae_closed_won_exited", "column": "itae_closed_won_exited"},
    "hs_v2_date_entered_1220382584": {"label": 'Date entered "Closed Lost"',           "internal": "itae_closed_lost_entered", "column": "itae_closed_lost_entered"},
    "hs_v2_date_exited_1220382584":  {"label": 'Date exited "Closed Lost"',            "internal": "itae_closed_lost_exited", "column": "itae_closed_lost_exited"},
    "hs_v2_date_entered_5043748053": {"label": 'Date entered "Opportunity Lost"',      "internal": "itae_opportunity_lost_entered", "column": "itae_opportunity_lost_entered"},
    "hs_v2_date_exited_5043748053":  {"label": 'Date exited "Opportunity Lost"',       "internal": "itae_opportunity_lost_exited", "column": "itae_opportunity_lost_exited"},
    "hs_v2_date_entered_5043748049": {"label": 'Date entered "Sales Nurturing"',       "internal": "itae_sales_nurturing_entered", "column": "itae_sales_nurturing_entered"},
    "hs_v2_date_exited_5043748049":  {"label": 'Date exited "Sales Nurturing"',        "internal": "itae_sales_nurturing_exited", "column": "itae_sales_nurturing_exited"},

    # ── IT SDR Pipeline (3612610753) ──
    "hs_v2_date_entered_5467457780": {"label": 'Date entered "Demo Request"',          "internal": "itsdr_demo_request_entered", "column": "itsdr_demo_request_entered"},
    "hs_v2_date_exited_5467457780":  {"label": 'Date exited "Demo Request"',           "internal": "itsdr_demo_request_exited", "column": "itsdr_demo_request_exited"},
    "hs_v2_date_entered_4969938161": {"label": 'Date entered "New"',                   "internal": "itsdr_new_entered", "column": "itsdr_new_entered"},
    "hs_v2_date_exited_4969938161":  {"label": 'Date exited "New"',                    "internal": "itsdr_new_exited", "column": "itsdr_new_exited"},
    "hs_v2_date_entered_4969938162": {"label": 'Date entered "Research & Outreach"',   "internal": "itsdr_research_outreach_entered", "column": "itsdr_research_outreach_entered"},
    "hs_v2_date_exited_4969938162":  {"label": 'Date exited "Research & Outreach"',    "internal": "itsdr_research_outreach_exited", "column": "itsdr_research_outreach_exited"},
    "hs_v2_date_entered_4969938163": {"label": 'Date entered "Connected - Not Engaged"', "internal": "itsdr_connected_not_engaged_entered", "column": "itsdr_connected_not_engaged_entered"},
    "hs_v2_date_exited_4969938163":  {"label": 'Date exited "Connected - Not Engaged"',  "internal": "itsdr_connected_not_engaged_exited", "column": "itsdr_connected_not_engaged_exited"},
    "hs_v2_date_entered_4969938164": {"label": 'Date entered "Engaged"',               "internal": "itsdr_engaged_entered", "column": "itsdr_engaged_entered"},
    "hs_v2_date_exited_4969938164":  {"label": 'Date exited "Engaged"',                "internal": "itsdr_engaged_exited", "column": "itsdr_engaged_exited"},
    "hs_v2_date_entered_4969938165": {"label": 'Date entered "Meeting Booked"',        "internal": "itsdr_meeting_booked_entered", "column": "itsdr_meeting_booked_entered"},
    "hs_v2_date_exited_4969938165":  {"label": 'Date exited "Meeting Booked"',         "internal": "itsdr_meeting_booked_exited", "column": "itsdr_meeting_booked_exited"},
    "hs_v2_date_entered_4969938166": {"label": 'Date entered "To reschedule"',         "internal": "itsdr_to_reschedule_entered", "column": "itsdr_to_reschedule_entered"},
    "hs_v2_date_exited_4969938166":  {"label": 'Date exited "To reschedule"',          "internal": "itsdr_to_reschedule_exited", "column": "itsdr_to_reschedule_exited"},
    "hs_v2_date_entered_4969938167": {"label": 'Date entered "Hot Nurturing"',         "internal": "itsdr_hot_nurturing_entered", "column": "itsdr_hot_nurturing_entered"},
    "hs_v2_date_exited_4969938167":  {"label": 'Date exited "Hot Nurturing"',          "internal": "itsdr_hot_nurturing_exited", "column": "itsdr_hot_nurturing_exited"},
    "hs_v2_date_entered_4969938168": {"label": 'Date entered "Long Nurturing"',        "internal": "itsdr_long_nurturing_entered", "column": "itsdr_long_nurturing_entered"},
    "hs_v2_date_exited_4969938168":  {"label": 'Date exited "Long Nurturing"',         "internal": "itsdr_long_nurturing_exited", "column": "itsdr_long_nurturing_exited"},
    "hs_v2_date_entered_4969938169": {"label": 'Date entered "Opportunity Lost"',      "internal": "itsdr_opportunity_lost_entered", "column": "itsdr_opportunity_lost_entered"},
    "hs_v2_date_exited_4969938169":  {"label": 'Date exited "Opportunity Lost"',       "internal": "itsdr_opportunity_lost_exited", "column": "itsdr_opportunity_lost_exited"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 5. CRM_MEETING_PROPERTIES
#
# WHAT: Meeting properties synced to `deal_meetings` table.
# WHERE: GET /crm/v3/objects/meetings/{id} with properties param.
# HOW: First get meeting IDs via deal associations, then batch-read properties.
# WHY: Track upcoming/past meetings per deal for briefing generation and no-show detection.
# ──────────────────────────────────────────────────────────────────────────────

CRM_MEETING_SYNC_PROPERTIES = {  # ? HubSpot meeting properties
    "hs_meeting_start_time":  {"label": "Meeting start time",     "column": "meeting_start"},
    "hs_meeting_end_time":    {"label": "Meeting end time",       "column": "meeting_end"},
    "hs_meeting_title":       {"label": "Meeting name",           "column": "title"},
    "hs_meeting_outcome":     {"label": "Meeting outcome",        "column": "outcome"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 6. CRM_CONTEXT_PROPERTIES
#
# WHAT: Engagement properties read to build deal_context (narrative text).
#       NOT persisted to any table — consumed in memory by intelligence.py.
# WHERE: GET /crm/v3/objects/{emails|notes|calls|meetings}/{id}
# HOW: Get engagement IDs via deal associations, batch-read, build text.
# WHY: Context text feeds the Claude prompt for snapshot/audit.
#
# Each dict = one engagement type. Keys are HubSpot property internal names.
# ──────────────────────────────────────────────────────────────────────────────

CRM_EMAIL_PROPERTIES = {  # ? HubSpot email properties
    "hs_timestamp":           {"label": "Activity date",                                     "column": "activity_date"},
    "hs_createdate":          {"label": "HubSpot Create Date",                               "column": "created_at"},
    "hs_email_direction":     {"label": "Email Direction (INCOMING_EMAIL / OUTGOING_EMAIL)",  "column": "direction"},
    "hs_email_from_email":    {"label": "Email From Address",                                "column": "from_email"},
    "hs_email_subject":       {"label": "Email subject",                                     "column": "subject"},
    "hs_email_text":          {"label": "Text body (plain)",                                 "column": "body_text"},
    "hs_email_html":          {"label": "Email body (HTML — stripped to text at runtime)",    "column": "body_html"},
}

CRM_NOTE_PROPERTIES = {  # ? HubSpot note properties
    "hs_timestamp":           {"label": "Activity date",                                     "column": "activity_date"},
    "hs_createdate":          {"label": "HubSpot Create Date",                               "column": "created_at"},
    "hs_note_body":           {"label": "Note body (HTML — stripped to text at runtime)",     "column": "body"},
    "hubspot_owner_id":       {"label": "Note author (resolved to name via CRM_OWNER_MAP)",  "column": "owner_id"},
}

CRM_CALL_PROPERTIES = {  # ? HubSpot call properties
    "hs_timestamp":           {"label": "Activity date",                                     "column": "activity_date"},
    "hs_call_body":           {"label": "Call notes (HTML — also scanned for Modjo links)",   "column": "call_body"},
    "hs_call_duration":       {"label": "Call duration (milliseconds)",                      "column": "call_duration_ms"},
    "hs_call_title":          {"label": "Call Title",                                        "column": "call_title"},
    "hubspot_owner_id":       {"label": "Call owner (resolved to name via CRM_OWNER_MAP)",   "column": "owner_id"},
}

CRM_MEETING_CONTEXT_PROPERTIES = {  # ? HubSpot meeting properties
    "hs_timestamp":               {"label": "Activity date",                                          "column": "activity_date"},
    "hs_meeting_title":           {"label": "Meeting name",                                           "column": "meeting_title"},
    "hs_meeting_body":            {"label": "Meeting description",                                    "column": "meeting_body"},
    "hs_internal_meeting_notes":  {"label": "Internal Meeting Notes (also scanned for Modjo links)",   "column": "meeting_notes"},
    "hs_meeting_start_time":      {"label": "Meeting start time",                                     "column": "meeting_start"},
    "hs_meeting_end_time":        {"label": "Meeting end time",                                       "column": "meeting_end"},
    "hs_meeting_outcome":         {"label": "Meeting outcome (COMPLETED / NO_SHOW / SCHEDULED)",      "column": "meeting_outcome"},
    "hubspot_owner_id":           {"label": "Meeting owner",                                          "column": "owner_id"},
    "hs_attendee_owner_ids":      {"label": "HubSpot attendee owner IDs (comma-separated)",           "column": "attendee_owner_ids"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 6b. CRM ENGAGEMENT ENUMS
#
# WHAT: Enum values returned by HubSpot for engagement properties.
# WHERE: Response values in hs_email_direction, hs_meeting_outcome.
# HOW: Compare raw CRM value against these maps.
# WHY: Convert CRM enum → internal name (e.g. "INCOMING_EMAIL" → "inbound").
# ──────────────────────────────────────────────────────────────────────────────

CRM_EMAIL_DIRECTIONS = {  # ? HubSpot enum → internal name
    "INCOMING_EMAIL": "inbound",
    "OUTGOING_EMAIL": "outbound",
}

CRM_MEETING_PROCESSABLE_OUTCOMES = frozenset({"COMPLETED", "NO_SHOW"})  # ? HubSpot enum values


# ──────────────────────────────────────────────────────────────────────────────
# 7. CRM_COMPANY_PROPERTIES
#
# WHAT: Company properties fetched for Atlas (company dossier).
# WHERE: GET /crm/v3/objects/companies/{id} with properties param.
# HOW: Get company ID via deal→company association, then read properties.
# WHY: Build company context for Claude prompt (atlas.py generates company_card, etc.)
#
# "column" = Supabase atlas table column (None if used only in prompt, not persisted)
# ──────────────────────────────────────────────────────────────────────────────

CRM_COMPANY_PROPERTIES = {  # ? HubSpot company properties
    "name":                 {"label": "Company Name",           "internal": "company_name",   "column": "company_name"},
    "industry":             {"label": "Industry",               "internal": "industry",       "column": "industry"},
    "numberofemployees":    {"label": "Number of employees",    "internal": "company_size",   "column": "company_size"},
    "country":              {"label": "Country",                "internal": "country",        "column": "country"},
    "website":              {"label": "Website",                "internal": "website",        "column": "website"},
    "description":          {"label": "Description",            "internal": "description",    "column": "description"},
    "city":                 {"label": "City",                   "internal": "city",           "column": "city"},
    "state":                {"label": "State/Province",         "internal": "state",          "column": "state"},
    "annualrevenue":        {"label": "Annual revenue",         "internal": "annual_revenue", "column": "annual_revenue"},
    "domain":               {"label": "Domain (for sibling company search)", "internal": "domain", "column": "domain"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 8. CRM_CONTACT_PROPERTIES
#
# WHAT: Contact properties fetched for Atlas.
# WHERE: GET /crm/v3/objects/contacts/{id} with properties param.
# HOW: Get contact IDs via company→contact association, then batch-read.
# WHY: Build contacts_map for Claude — who are the key people on the deal.
# ──────────────────────────────────────────────────────────────────────────────

CRM_CONTACT_PROPERTIES = {  # ? HubSpot contact properties
    "firstname":    {"label": "First Name",  "internal": "firstname"},
    "lastname":     {"label": "Last Name",   "internal": "lastname"},
    "email":        {"label": "Email",       "internal": "email"},
    "jobtitle":     {"label": "Job Title",   "internal": "jobtitle"},
    "phone":        {"label": "Phone",       "internal": "phone"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 9. CRM_OWNER_FIELDS
#
# WHAT: Fields returned by the HubSpot Owners API.
# WHERE: GET /crm/v3/owners
# HOW: Paginated list of all owners in the account. Cached in memory per run.
# WHY: Resolve owner IDs (from deal properties) to names and emails.
#       owner_id → email → orgchart → team/role/partner
# ──────────────────────────────────────────────────────────────────────────────

CRM_OWNER_API_FIELDS = {  # ? HubSpot owners API fields
    "id":        "Owner ID (numeric string, e.g. '76824216')",
    "firstName": "First name",
    "lastName":  "Last name",
    "email":     "Email address (primary key for orgchart lookup)",
}


# ──────────────────────────────────────────────────────────────────────────────
# 10. CRM_ASSOCIATIONS
#
# WHAT: Object-to-object relationships in HubSpot.
# WHERE: POST /crm/v4/associations/{fromType}/{toType}/batch/read
#        or GET /crm/v4/objects/{type}/{id}/associations/{toType}
# HOW: Pass object IDs, get back related object IDs.
# WHY: Deals don't contain company/contact/partner data directly.
#       Must follow associations to get related objects.
#
# Format: "name": {"from": "object_type", "to": "object_type", "usage": "why"}
# ──────────────────────────────────────────────────────────────────────────────

CRM_ASSOCIATIONS = {  # ? HubSpot association API
    "deal_to_company":    {"from": "deals",     "to": "companies",  "usage": "Atlas lookup — which company owns this deal"},
    "deal_to_partner":    {"from": "deals",     "to": "2-3229093",  "usage": "Partner detection — which partner referred this deal"},  # & custom object type ID
    "deal_to_emails":     {"from": "deals",     "to": "emails",     "usage": "Context builder — emails on this deal"},
    "deal_to_notes":      {"from": "deals",     "to": "notes",      "usage": "Context builder — notes on this deal"},
    "deal_to_meetings":   {"from": "deals",     "to": "meetings",   "usage": "Context + meeting sync — meetings on this deal"},
    "deal_to_calls":      {"from": "deals",     "to": "calls",      "usage": "Context builder — HubSpot calls (not Modjo) on this deal"},
    "deal_to_contacts":   {"from": "deals",     "to": "contacts",   "usage": "Atlas — which contacts participated in each deal"},
    "company_to_deals":   {"from": "companies", "to": "deals",      "usage": "Atlas — all deals for a company (siblings)"},
    "company_to_contacts":{"from": "companies", "to": "contacts",   "usage": "Atlas — all contacts at a company"},
    "meeting_to_deals":   {"from": "meetings",  "to": "deals",      "usage": "Meeting sync — resolve which deal a meeting belongs to"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 11. CRM_PARTNER_OBJECTS
#
# WHAT: Custom object type for partner associations in HubSpot.
# WHERE: HubSpot Settings → Objects → Custom Objects → "Partner"
# HOW: Each deal can have a partner association (custom object).
#       The partner object's ID maps to a team name.
# WHY: Most reliable way to detect partner deals (partner_name field is unreliable).
# ──────────────────────────────────────────────────────────────────────────────

CRM_PARTNER_OBJECT_TYPE_ID = "2-3229093"  # &

CRM_PARTNER_OBJECTS = {  # & ALL entries — HubSpot custom object IDs
    "4767807590":    {"team": "Santander",        "display": "Santander"},
    "401845373146":  {"team": "Santander Mexico", "display": "Santander México"},
    "28079747484":   {"team": "Santander",        "display": "Santander PT"},
    "4767660726":    {"team": "Telefonica",       "display": "Telefonica"},
    "25968646986":   {"team": "TIM",              "display": "TIM"},
    "25359694224":   {"team": "TELEKOM",          "display": "Deutsche Telekom"},
    "34458760336":   {"team": "MEO",              "display": "MEO / Altice"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 12. CRM_OWNER_MAP
#
# WHAT: Maps email → HubSpot owner ID + display name.
# WHERE: HubSpot Settings → Users & Teams → each user has an owner ID.
# HOW: Used to build HubSpot Search API queries (filter by owner_id)
#       and to resolve owner_id → email → orgchart → team/role.
# WHY: HubSpot Search API requires owner IDs (not emails) for filtering.
#
# To add a new rep:
#   1. Find their owner ID in HubSpot (Settings → Users → click user → URL contains ID)
#   2. Add email → {id, name} entry here
#   3. Add them to the ORGCHART section
# ──────────────────────────────────────────────────────────────────────────────

CRM_OWNER_MAP = {  # & ALL entries — owner IDs and emails
    "abel.exposito@factorial.co": {"id": "81684298", "name": "Abel Expósito Roselló"},
    "albert.fernandez@factorial.co": {"id": "309581666", "name": "Albert Fernandez"},
    "alberto.toboso@factorial.co": {"id": "86980984", "name": "Alberto Toboso"},
    "alejandra.denobregas@factorial.co": {"id": "1911202931", "name": "Alejandra De Nóbregas"},
    "alejandro.moreno@factorial.co": {"id": "34637474", "name": "Alejandro Moreno Luna"},
    "alejandro.soto@factorial.co": {"id": "32980021", "name": "Alejandro Soto Velasco"},
    "alessandro.cardinale@factorial.co": {"id": "89052244", "name": "Alessandro Cardinale"},
    "alex.martinez@factorial.co": {"id": "79352699", "name": "Alex Martinez"},
    "alexander.ulrich@factorial.co": {"id": "86686795", "name": "Alexander Ulrich"},
    "amadeo.cuellar@factorial.co": {"id": "82431537", "name": "Amadeo Cuellar"},
    "andre.reis@factorial.co": {"id": "83619876", "name": "André Reis Pombinho"},
    "andrea.alonso@factorial.co": {"id": "85923597", "name": "Andrea Alonso de Paz"},
    "andrea.castanar@factorial.co": {"id": "80330300", "name": "Andrea Castañar"},
    "andrea.galimberti@factorial.co": {"id": "343535117", "name": "Andrea Galimberti"},
    "andreu.aloguin@factorial.co": {"id": "84984317", "name": "Andreu Aloguin Serramia"},
    "angel.hernandez@factorial.co": {"id": "81867015", "name": "Ángel Hernández"},
    "antoni.grau@factorial.co": {"id": "33868845", "name": "Antoni Grau Zorita"},
    "ariadna.isla@factorial.co": {"id": "100419730", "name": "Ariadna Isla Domínguez"},
    "arnau.palos@factorial.co": {"id": "500008456", "name": "Arnau Palos Figueras"},
    "beatriz.bravo@factorial.co": {"id": "34637457", "name": "Beatriz Bravo"},
    "belen.lombardia@factorial.co": {"id": "554650133", "name": "Belén Lombardía"},
    "blanca.orti@factorial.co": {"id": "343529996", "name": "Blanca Orti Morillo"},
    "carlos.acosta@factorial.co": {"id": "77159731", "name": "Carlos Acosta"},
    "carlos.sanchez@factorial.co": {"id": "2078231828", "name": "Carlos Sanchez"},
    "carlota.alvarez@factorial.co": {"id": "77922017", "name": "Carlota Álvarez"},
    "caterina.peraire@factorial.co": {"id": "34212948", "name": "Caterina Peraire"},
    "cecilia.rinaldo@factorial.co": {"id": "32832928", "name": "Cecilia Rinaldo"},
    "chiang.nguyen@factorial.co": {"id": "32980547", "name": "Chiang Dinh-Khai Nguyen"},
    "christian.lombardo@factorial.co": {"id": "86980724", "name": "Christian Lombardo"},
    "cristian.ramos@factorial.co": {"id": "32550211", "name": "Cristian Ramos"},
    "cristina.tarres@factorial.co": {"id": "85923618", "name": "Cristina Tarrés"},
    "daniela.hernandez@factorial.co": {"id": "83250329", "name": "Daniela Hernandez"},
    "daniela.orozco@factorial.co": {"id": "578909258", "name": "Daniela Orozco Parra"},
    "daniel.terrasa@factorial.co": {"id": "558202936", "name": "Daniel Terrasa"},
    "david.clemente@factorial.co": {"id": "77408863", "name": "David Clemente"},
    "david.donaire@factorial.co": {"id": "76655118", "name": "David Donaire"},
    "david.soler@factorial.co": {"id": "32687506", "name": "David Soler"},
    "denis.peramos@factorial.co": {"id": "82080024", "name": "Denis Peramos"},
    "diana.bernal@factorial.co": {"id": "77922801", "name": "Diana Bernal"},
    "diego.hernandez@factorial.co": {"id": "133287347", "name": "Diego Osvaldo Hernandez Vicuña"},
    "edgar.ybarguengoitia@factorial.co": {"id": "85521152", "name": "Edgar Ybargüengoitia"},
    "edoardo.rapezzi@factorial.co": {"id": "86687949", "name": "Edoardo Rapezzi"},
    "eduardo.mahr@factorial.co": {"id": "554934310", "name": "Eduardo Mahr"},
    "eduardo.zafra@factorial.co": {"id": "561316186", "name": "Eduardo Zafra"},
    "emilio.fabbro@factorial.co": {"id": "77408871", "name": "Emilio Fabbro"},
    "enrique.gautier@factorial.co": {"id": "76126161", "name": "Enrique Gautier Bolz"},
    "ernesto.blanco@factorial.co": {"id": "80909459", "name": "Ernesto Blanco Sierra"},
    "fiona.durr@factorial.co": {"id": "82557508", "name": "Fiona Dürr"},
    "fabiola.villalobos@factorial.co": {"id": "94319291", "name": "Fabiola Villalobos Damian"},
    "francesc.terns@factorial.co": {"id": "82179188", "name": "Francesc Terns"},
    "gabriel.lichtenstein@factorial.co": {"id": "32550082", "name": "Gabriel Lichtenstein"},
    "gerard.ghneim@factorial.co": {"id": "311993943", "name": "Gerard Ghneim Peroy"},
    "gerard.tarradas@factorial.co": {"id": "1214888545", "name": "Gerard Tarradas Alarcon"},
    "giacomo.torresi@factorial.co": {"id": "507963188", "name": "Giacomo Torresi"},
    "giovanni.laghi@factorial.co": {"id": "32147416", "name": "Giovanni Laghi"},
    "giuditta.giunta@factorial.co": {"id": "77159727", "name": "Giuditta Giunta"},
    "gloria.nunez@factorial.co": {"id": "81399037", "name": "Gloria Nuñez"},
    "guillermo.ferrer@factorial.co": {"id": "168739388", "name": "Guillermo Ferrer"},
    "gustavo.torres@factorial.co": {"id": "188140936", "name": "Gustavo Torres"},
    "iban.cordobes@factorial.co": {"id": "84370034", "name": "Iban Cordobés"},
    "ignacio.catasus@factorial.co": {"id": "150984090", "name": "Ignacio Catasús"},
    "ignacio.otero@factorial.co": {"id": "34450774", "name": "Ignacio Otero"},
    "iker.gordo@factorial.co": {"id": "77408730", "name": "Iker Gordo"},
    "ines.rivera@factorial.co": {"id": "78463306", "name": "Inés Rivera"},
    "irene.orra@factorial.co": {"id": "32980034", "name": "Irene Orra"},
    "jacobo.enriquez@factorial.co": {"id": "75910515", "name": "Jacobo Enríquez"},
    "joan.balana@factorial.co": {"id": "124080727", "name": "Joan Balaña"},
    "joan.lorenzo@factorial.co": {"id": "946496370", "name": "Joan Lorenzo Galles"},
    "johanna.henrich@factorial.co": {"id": "82431659", "name": "Johanna Henrich"},
    "jon.azconobieta@factorial.co": {"id": "78463284", "name": "Jon Azconobieta"},
    "jonas.tretter@factorial.co": {"id": "34213545", "name": "Jonas Tretter"},
    "jordi.reina@factorial.co": {"id": "83619860", "name": "Jordi Reina Garcia"},
    "jose.donis@factorial.co": {"id": "554650010", "name": "Jose Donis"},
    "josep.fora@factorial.co": {"id": "78736698", "name": "Josep Fora"},
    "juan.ruiz@factorial.co": {"id": "31866070", "name": "Juan Felipe Ruiz"},
    "julia.flaque@factorial.co": {"id": "32708064", "name": "Júlia Flaqué Porta"},
    "karen.andrade@factorial.co": {"id": "248927013", "name": "Karen Andrade"},
    "katrin.virtbauer@factorial.co": {"id": "83903815", "name": "Katrin Virtbauer"},
    "l.rodriguez@factorial.co": {"id": "684817577", "name": "Luis Rodríguez de Luz"},
    "laura.proefrock@factorial.co": {"id": "1700853807", "name": "Laura Proefrock"},
    "leonhard.zeus@factorial.co": {"id": "80791735", "name": "Leonhard Zeus"},
    "lorena.tapia@factorial.co": {"id": "84016824", "name": "Lorena Tapia Arroyo"},
    "lucia.detorres@factorial.co": {"id": "32708231", "name": "Lucia De Torres Alcalde"},
    "lucia.garana@factorial.co": {"id": "33081553", "name": "Lucia Garaña"},
    "manuel.conesa@factorial.co": {"id": "84984311", "name": "Manuel Conesa"},
    "maximiliano.velasco@factorial.co": {"id": "35659596", "name": "Max Velasco"},
    "marco.falaschetti@factorial.co": {"id": "187721367", "name": "Marco Falaschetti"},
    "maria.masoliver@factorial.co": {"id": "32147470", "name": "María Masoliver"},
    "maria.reina@factorial.co": {"id": "1358098012", "name": "Maria Reina Caballero"},
    "marta.ruiz@factorial.co": {"id": "554655901", "name": "Marta Ruiz Sánchez"},
    "meritxell.goikoetxea@factorial.co": {"id": "35660040", "name": "Meritxell Goikoetxea"},
    "miljan.nojkic@factorial.co": {"id": "34212992", "name": "Miljan Nojkic"},
    "miquel.criado@factorial.co": {"id": "32708305", "name": "Miquel Criado"},
    "mireia.bach@factorial.co": {"id": "103459488", "name": "Mireia Bach"},
    "nerea.urien@factorial.co": {"id": "645417472", "name": "Nerea Urien Meizoso"},
    "nicolas.gonzalez@factorial.co": {"id": "84394154", "name": "Nicolás González-Tarrío"},
    "nil.oleaga@factorial.co": {"id": "82847426", "name": "Nil Oleaga"},
    "nunzio.fumo@factorial.co": {"id": "343525024", "name": "Nunzio Fumo"},
    "pablo.andres@factorial.co": {"id": "95103446", "name": "Pablo Andrés Ruiz"},
    "nuria.delacerda@factorial.co": {"id": "80763157", "name": "Nuria De La Cerda Sánchez"},
    "nuria.gisbert@factorial.co": {"id": "78959985", "name": "Nuria Gisbert Martínez"},
    "oriol.gubau@factorial.co": {"id": "673801091", "name": "Oriol Gubau"},
    "oriol.pesa@factorial.co": {"id": "447489166", "name": "Oriol Pesa"},
    "paula.gil@factorial.co": {"id": "81867010", "name": "Paula Gil"},
    "pilar.elizaga@factorial.co": {"id": "86980707", "name": "Maria del Pilar Elizaga"},
    "pol.bartolome@factorial.co": {"id": "105443852", "name": "Pol Bartolomé"},
    "roberto.moran@factorial.co": {"id": "105445464", "name": "Roberto Morán"},
    "ruben.mariscal@factorial.co": {"id": "490300827", "name": "Rubén Mariscal"},
    "sabri.blaybel@factorial.co": {"id": "121160834", "name": "Sabri Blaybel"},
    "santiago.tintore@factorial.co": {"id": "81399946", "name": "Santiago Tintoré"},
    "sebastian.boudet@factorial.co": {"id": "84394220", "name": "Sebastian Boudet"},
    "sonia.jimenez@factorial.co": {"id": "82431538", "name": "Sonia Jimenez Ruiz"},
    "stefan.platt@factorial.co": {"id": "86980969", "name": "Stefan Platt"},
    "tania.diaz@factorial.co": {"id": "146400912", "name": "Tania Diaz Soto"},
    "tatiana.baltatescu@factorial.co": {"id": "33868827", "name": "Tatiana Baltatescu"},
    "teresa.santamaria@factorial.co": {"id": "390628148", "name": "Teresa Santamaria"},
    "xavier.fortuny@factorial.co": {"id": "76824216", "name": "Xavier Fortuny"},
    "yolanda.tello@factorial.co": {"id": "33372303", "name": "Yolanda Tello"},
}

CRM_ACCOUNT_ID = "4960096"  # &
CRM_NAME = "HubSpot"  # &
CRM_SHORT = "HS"  # &
ORG_NAME = "Factorial"  # &

CRM_FORECAST_CATEGORIES = ["Commit", "Upside", "Pipeline", "Omit"]  # &


# ──────────────────────────────────────────────────────────────────────────────
# 13. CRM_SYNC_STRATEGY
#
# WHAT: How deals are found in HubSpot (search strategy + trigger logic).
# WHERE: POST /crm/v3/objects/deals/search
# HOW: 3-phase search: partner deals → Mexico → owner-based.
# WHY: No single query can find all our deals — different teams use
#       different identification methods (partner_name, team_string, owner_id).
# ──────────────────────────────────────────────────────────────────────────────

CRM_SYNC_STRATEGY = {  # & pipeline IDs are account-specific
    "default_mode": "incremental",
    "full_sync_interval_hours": 168,
    "incremental_lookback_minutes": 70,
}

CRM_CORE_TRIGGER = {  # & pipeline IDs are account-specific
    "search_internal": "last_modified",
    "activity_internal": "last_activity",
}


# ══════════════════════════════════════════════════════════════════════════════
# PART II — CALL PLATFORM (Modjo)
#
# All data that comes from Modjo (call recording + transcription platform).
# If switching to Gong, Chorus, or any other call platform, replace this part.
#
# Modjo API docs: https://api.modjo.ai/docs
# Auth: Bearer token (env var MODJO_API_KEY)
# ══════════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────────────
# 14. CALL_PLATFORM_FIELDS
#
# WHAT: Fields returned by the Modjo Calls Export API.
# WHERE: POST /v1/calls/exports
# HOW: Request with filters.callIds or date range. Response includes call data,
#       user relations, transcript lines, and tags.
# WHY: Calls are the primary input for audits. Transcripts feed Claude prompts.
# ──────────────────────────────────────────────────────────────────────────────

CALL_PLATFORM_FIELDS = {  # ? Modjo API field names
    # ── Call-level fields ──
    "callId":    {"maps_to": "call_id",           "type": "string", "description": "Unique call ID in Modjo"},
    "title":     {"maps_to": "titulo",            "type": "string", "description": "Call title (usually auto-generated)"},
    "startDate": {"maps_to": "fecha",             "type": "datetime", "description": "Call start time (ISO 8601)"},
    "duration":  {"maps_to": "duracion_segundos", "type": "integer", "description": "Call duration in seconds"},

    # ── User fields (from relations.users[]) ──
    "user.email":   {"maps_to": "owner_email",  "type": "string", "description": "Rep's email (matched against orgchart)"},
    "user.name":    {"maps_to": "owner_nombre", "type": "string", "description": "Rep's display name"},
    "user.isOwner": {"maps_to": "is_owner",      "type": "boolean", "description": "True if this user is the call owner (vs participant)"},

    # ── Transcript fields (from relations.transcript[]) ──
    "transcript.startTime": {"maps_to": "start_time",        "type": "float",  "description": "Timestamp in seconds (for [MM:SS] prefix)"},
    "transcript.content":   {"maps_to": "transcript",         "type": "string", "description": "Transcript text (assembled into full transcript)"},
    "transcript.userName":  {"maps_to": "speaker_name",       "type": "string", "description": "Speaker name"},
    "transcript.speaker":   {"maps_to": "speaker_fallback",   "type": "string", "description": "Fallback speaker identification"},

    # ── Tag fields (from relations.tags[]) ──
    "tag.name": {"maps_to": "tags", "type": "string", "description": "Tag name (matched against CALL_TAGS below)"},
}

CALL_PLATFORM_LINK_PATTERN = r"app\.modjo\.ai/call-details/(\d+)"  # ? Modjo URL pattern


# ──────────────────────────────────────────────────────────────────────────────
# 15. CALL_TAGS
#
# WHAT: Tags applied to calls in Modjo by reps or auto-rules.
# WHERE: Modjo Settings → Tags (or returned in call export response)
# HOW: Each call has 0-N tags. Tags determine which audit prompt to use
#       and what level of analysis to perform (full vs light).
# WHY: Tag drives the entire audit flow — prompt selection, BANT/MEDDIC scoring,
#       handover triggers, and Slack notifications.
#
# tag_to_prompt: tag name → prompt file path (relative to prompts/ dir)
#   None = use untagged.txt (Claude infers call type)
# tag_audit_level: tag name → "full_pbd" | "full_pae" | "light"
#   full = complete BANT/MEDDIC analysis
#   light = quick summary only
# ──────────────────────────────────────────────────────────────────────────────

CALL_TAGS_PBD = {  # & ALL entries — Modjo tag names
    "91. Partners - PBD Demo Scheduled",
    "92. Partners - PBD Positive Champion Connected Call",
    "93. Partners - PBD Gatekeeper Call Connected",
    "94. Partners - PBD Connected Call - Objection",
    "95. Partners - PBD Connected Call - Busy/Bad Time",
    "96. Partners - PBD Non Connected - Left Voicemail",
    "97. Partners - PBD Non Connected - No Answer/Busy",
    "98. Partners - PBD Connected Call - Wrong Number",
    "99. Partners - PBD Connected Call - Wrong Champion/Person inside the Company",
    "991. Partners - PBD Partner Call",
    "Partners - PBD Demo Scheduled Call",
    "Partners - PBD Discovery Call",
    "Partners - PBD Partner Call",
}

CALL_TAGS_PAE = {  # & ALL entries — Modjo tag names
    "Partners - PAE Demo",
    "Partners - PAE Follow Up",
    "Partners - PAE Follow Up Meeting",
    "Partners - PAE Closing Call",
    "Partners - PAE Closing Meeting",
    "Partners - PAE Other",
}

CALL_TAGS_DIRECT_SALES = {  # & ALL entries — Modjo tag names
    "1. SDR - Demo Scheduled Call",
    "2. SDR - Positive Champion Call Connected",
    "3. SDR - Negative Champion Call Connected",
    "4. SDR - Gatekeeper Call Connected",
    "7. SDR - No Answer",
    "AE - Discovery Meeting",
    "AE - Follow Up",
    "AE - Closing Call",
    "Follow up Meeting",
}

CALL_TAGS_PARTNER_MGMT = {  # & ALL entries — Modjo tag names
    "Partners - Partner Training Meeting",
    "Partners - Partner Forecast Meeting",
    "Partners - PDM Training Meeting",
    "Partners - PDM Recurring Meeting",
    "Partners - PAM Onboarding Call",
    "Partners - PAM Recurring Meeting",
    "Partners - PAM Partner Training",
    "Partners - PAM Feedback & Troubleshooting",
    "Partner - Spontaneous calls",
}

CALL_TAGS_SKIP = {  # & ALL entries — Modjo tag names
    "OB - Onboarding", "OB - Discovery", "OB - Final Call", "OB - Risk of Churn",
    "CX - AM Upsell Follow up", "CX - AM Discovery", "CX - AM Demo",
    "CX - Payroll Consultancy", "CX - AM Regular Meeting",
    "CX - AM Engagement Call", "CX - AM QBR", "CX - Handover",
    "INTERNAL - Meeting/Training",
    "PRODUCT - DOCUMENTS - Distribution",
    "Platform - CIAM - Security Settings",
}

CALL_TAGS_METADATA = {"Possible Rejected"}

MODJO_FIELD_MAP = {
    # call-level
    "call_id": "callId",
    "titulo": "title",
    "fecha": "startDate",
    "duracion": "duration",
    "relations": "relations",
    # nested containers
    "transcript_lines": "transcript",
    "users": "users",
    "tags": "tags",
    # transcript line fields
    "start_time": "startTime",
    "content": "content",
    # speaker identification
    "speaker_name": "userName",
    "speaker_fallback": "speaker",
    # user fields
    "user_email": "email",
    "user_name": "name",
    "is_owner": "isOwner",
    # tag fields
    "tag_name": "name",
    # API request structure
    "endpoint": "/calls/exports",
    "response_key": "values",
    "req_pagination": "pagination",
    "req_page": "page",
    "req_per_page": "perPage",
    "req_filters": "filters",
    "req_call_ids": "callIds",
    "req_relations": "relations",
    "auth_header": "X-API-KEY",
}

MODJO_BATCH_SIZE = 50

CALL_TAG_ALIASES = {  # & depends on tag names
    "Partners - PBD Demo Scheduled Call": "91. Partners - PBD Demo Scheduled",
    "Partners - PBD Partner Call": "991. Partners - PBD Partner Call",
}

CALL_TAG_TO_PROMPT = {  # & depends on tag names
    "91. Partners - PBD Demo Scheduled": "pbd/91.txt",
    "Partners - PBD Demo Scheduled Call": "pbd/91.txt",
    "92. Partners - PBD Positive Champion Connected Call": "pbd/92.txt",
    "93. Partners - PBD Gatekeeper Call Connected": "pbd/93.txt",
    "94. Partners - PBD Connected Call - Objection": "pbd/94.txt",
    "95. Partners - PBD Connected Call - Busy/Bad Time": "pbd/95.txt",
    "96. Partners - PBD Non Connected - Left Voicemail": "pbd/96.txt",
    "97. Partners - PBD Non Connected - No Answer/Busy": "pbd/97.txt",
    "98. Partners - PBD Connected Call - Wrong Number": "pbd/98.txt",
    "99. Partners - PBD Connected Call - Wrong Champion/Person inside the Company": "pbd/99.txt",
    "991. Partners - PBD Partner Call": "pbd/991.txt",
    "Partners - PBD Discovery Call": "pbd/92.txt",
    "Partners - PBD Partner Call": "pbd/991.txt",
    "Partners - PAE Demo": "pae/demo.txt",
    "Partners - PAE Follow Up": "pae/follow_up.txt",
    "Partners - PAE Follow Up Meeting": "pae/follow_up.txt",
    "Partners - PAE Closing Call": "pae/closing.txt",
    "Partners - PAE Closing Meeting": "pae/closing.txt",
    "Partners - PAE Other": None,
    "1. SDR - Demo Scheduled Call": "pbd/91.txt",
    "2. SDR - Positive Champion Call Connected": "pbd/92.txt",
    "3. SDR - Negative Champion Call Connected": "pbd/94.txt",
    "4. SDR - Gatekeeper Call Connected": "pbd/93.txt",
    "7. SDR - No Answer": "pbd/97.txt",
    "AE - Discovery Meeting": "pae/demo.txt",
    "AE - Follow Up": "pae/follow_up.txt",
    "AE - Closing Call": "pae/closing.txt",
    "Follow up Meeting": "pae/follow_up.txt",
    "Partners - Partner Training Meeting": None,
    "Partners - Partner Forecast Meeting": None,
    "Partners - PDM Training Meeting": None,
    "Partners - PDM Recurring Meeting": None,
    "Partners - PAM Onboarding Call": None,
    "Partners - PAM Recurring Meeting": None,
    "Partners - PAM Partner Training": None,
    "Partners - PAM Feedback & Troubleshooting": None,
    "Partner - Spontaneous calls": None,
}

CALL_TAG_AUDIT_LEVEL = {  # & depends on tag names
    "91. Partners - PBD Demo Scheduled": "full_pbd",
    "92. Partners - PBD Positive Champion Connected Call": "full_pbd",
    "94. Partners - PBD Connected Call - Objection": "full_pbd",
    "Partners - PBD Demo Scheduled Call": "full_pbd",
    "Partners - PBD Discovery Call": "full_pbd",
    "93. Partners - PBD Gatekeeper Call Connected": "light",
    "991. Partners - PBD Partner Call": "light",
    "Partners - PBD Partner Call": "light",
    "95. Partners - PBD Connected Call - Busy/Bad Time": "light",
    "96. Partners - PBD Non Connected - Left Voicemail": "light",
    "97. Partners - PBD Non Connected - No Answer/Busy": "light",
    "98. Partners - PBD Connected Call - Wrong Number": "light",
    "99. Partners - PBD Connected Call - Wrong Champion/Person inside the Company": "light",
    "Partners - PAE Demo": "full_pae",
    "Partners - PAE Follow Up": "full_pae",
    "Partners - PAE Follow Up Meeting": "full_pae",
    "Partners - PAE Closing Call": "full_pae",
    "Partners - PAE Closing Meeting": "full_pae",
    "Partners - PAE Other": "light",
    "1. SDR - Demo Scheduled Call": "full_pbd",
    "2. SDR - Positive Champion Call Connected": "full_pbd",
    "3. SDR - Negative Champion Call Connected": "full_pbd",
    "4. SDR - Gatekeeper Call Connected": "light",
    "7. SDR - No Answer": "light",
    "AE - Discovery Meeting": "full_pae",
    "AE - Follow Up": "full_pae",
    "AE - Closing Call": "full_pae",
    "Follow up Meeting": "full_pae",
}

CALL_HANDOVER_TRIGGER_TAG = "91. Partners - PBD Demo Scheduled"
CALL_TAG_CATEGORY_PRIORITY = ["partners_pae", "partners_pbd", "direct_sales", "partner_mgmt"]
CALL_LEVEL_PRIORITY = {"full_pae": 1, "full_pbd": 2, "light": 3, "light_pae": 3}


# ══════════════════════════════════════════════════════════════════════════════
# PART III — CALENDAR (Google Calendar)
#
# Meetings from Google Calendar API. Used for briefing generation (pre-meeting prep).
# If switching to Outlook Calendar, replace this part.
#
# Auth: OAuth 2.0 service account with calendar.readonly scope
# ══════════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────────────
# 16. CALENDAR_FIELDS
#
# WHAT: Fields from Google Calendar Events API.
# WHERE: GET /calendar/v3/calendars/{calendarId}/events
# HOW: calendarId = rep's email. Query with timeMin/timeMax.
# WHY: Detect upcoming meetings → generate briefings → send via Slack.
# ──────────────────────────────────────────────────────────────────────────────

CALENDAR_EVENT_FIELDS = {  # ? Google Calendar API fields
    "id":              {"maps_to": "gcal_event_id",  "description": "Google Calendar event ID"},
    "summary":         {"maps_to": "title",          "description": "Event title (filtered: skip internal meetings)"},
    "status":          {"maps_to": "event_status",    "description": "Event status (skip if 'cancelled')"},
    "start.dateTime":  {"maps_to": "meeting_start",  "description": "Event start (skip if missing = all-day event)"},
    "end.dateTime":    {"maps_to": "meeting_end",    "description": "Event end"},
}

CALENDAR_ATTENDEE_FIELDS = {  # ? Google Calendar API fields
    "email":          {"maps_to": "email",            "description": "Attendee email (lowercased, filtered against domains)"},
    "displayName":    {"maps_to": "name",             "description": "Attendee display name"},
    "responseStatus": {"maps_to": "attendee_rsvp",     "description": "RSVP status (skip if 'declined')"},
}

GCAL_FIELD_MAP = {
    # response structure
    "response_key": "items",
    # event fields
    "event_id": "id",
    "event_title": "summary",
    "event_status": "status",
    "event_start": "start",
    "event_end": "end",
    "event_datetime": "dateTime",
    "event_attendees": "attendees",
    # status values
    "status_cancelled": "cancelled",
    # attendee fields
    "attendee_email": "email",
    "attendee_name": "displayName",
    "attendee_rsvp": "responseStatus",
    # rsvp values
    "rsvp_declined": "declined",
    # query params
    "order_by": "startTime",
}

CALENDAR_INTERNAL_KEYWORDS = [  # & language-specific keywords
    "weekly", "daily", "1:1", "1 to 1", "sync", "sincro",
    "standup", "stand-up", "retro", "planning", "sprint", "partner sales team",
]

CALENDAR_ACTIVE_REPS = {  # & ALL entries — rep emails with calendar access
    "xavier.fortuny@factorial.co",
    "jose.donis@factorial.co",
    "pol.bartolome@factorial.co",
    "roberto.moran@factorial.co",
    "beatriz.bravo@factorial.co",
    "joan.lorenzo@factorial.co",
    "joan.balana@factorial.co",
    "eduardo.zafra@factorial.co",
    "david.clemente@factorial.co",
    "nerea.urien@factorial.co",
    "carlos.sanchez@factorial.co",
    "alejandro.soto@factorial.co",
    "nunzio.fumo@factorial.co",
    "emilio.fabbro@factorial.co",
    "marco.falaschetti@factorial.co",
    "giovanni.laghi@factorial.co",
    "edoardo.rapezzi@factorial.co",
    "christian.lombardo@factorial.co",
    "giuditta.giunta@factorial.co",
    "gabriel.lichtenstein@factorial.co",
    "leonhard.zeus@factorial.co",
    "katrin.virtbauer@factorial.co",
    "stefan.platt@factorial.co",
    "enrique.gautier@factorial.co",
    "jonas.tretter@factorial.co",
}


# ══════════════════════════════════════════════════════════════════════════════
# PART IV — MESSAGING (Slack)
#
# Channel IDs for notifications. Slack is output-only (we send, never receive).
# If switching to Teams, replace channel IDs with Teams webhook URLs.
# ══════════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────────────
# 17. SLACK_CHANNELS
#
# WHAT: Slack channel IDs per person and per team.
# WHERE: Slack workspace → channel info → copy channel ID.
# HOW: Used by slack_notifier.py to post messages.
# WHY: Individual channels for briefings/alerts. Team channels for TL reports.
# ──────────────────────────────────────────────────────────────────────────────

SLACK_FALLBACK_CHANNEL = "C0ATY3V8CN4"

SLACK_TEAM_CHANNELS = {  # & ALL entries — Slack channel IDs
    "Santander":  {"tl_channel": "C0B36RD537X"},
    "Telefonica": {"tl_channel": "C0B33QJLF8B"},
    "TIM":        {"tl_channel": "C0B9QCWDCQ4"},
    "TELEKOM":    {"tl_channel": "C0B9QCWDCQ4"},
}

SLACK_PERSON_CHANNELS = {  # & ALL entries — Slack channel IDs per person
    "joan.balana@factorial.co": "C0B36RD537X",
    "roberto.moran@factorial.co": "C0B36RD537X",
    "carlos.sanchez@factorial.co": "C0B33QJLF8B",
    "xavier.fortuny@factorial.co": "C0B1CNJTPMZ",
    "jose.donis@factorial.co": "C0B24A51PNE",
    "pol.bartolome@factorial.co": "C0B33Q2T7FV",
    "beatriz.bravo@factorial.co": "C0B8BKTS1CL",
    "joan.lorenzo@factorial.co": "C0B2UMVT5NK",
    "david.clemente@factorial.co": "C0B33QDE4KD",
    "nerea.urien@factorial.co": "C0B2UMRUV2T",
    "alejandro.soto@factorial.co": "C0B36Q1EX9T",
}

SLACK_EB_ALERT_CHANNELS = {  # & ALL entries — EB alert channel IDs
    "Santander":  "C0B1VPPG1F1",
    "Telefonica": "C0B1VPPG1F1",
    "TIM":        "C0BA1MU9S1J",
    "TELEKOM":    "C0B9QCWDCQ4",
}

SLACK_EB_ALERT_EMOJI = {  # & ALL entries — emoji per team
    "Santander": ":Santander:",
    "Telefonica": ":telefonica:",
    "TIM": ":tim:",
    "TELEKOM": ":telekom:",
}


# ══════════════════════════════════════════════════════════════════════════════
# PART V — PEOPLE & IDENTITY
#
# Company-specific: who works here, what teams exist, which partners we have.
# If deploying for a different company, replace this entire part.
# ══════════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────────────
# 18. ORGCHART
#
# WHAT: Every person in the sales org — their email, team, and role.
# WHERE: Internal HR / team structure.
# HOW: Emails are the primary key. Used to resolve CRM owner IDs to teams/roles.
# WHY: When a deal owner is "xavier.fortuny@factorial.co", the system needs to know
#       he's a PAE on Santander to select the right audit prompt, Slack channel, etc.
#
# Structure:
#   PARTNERS_ORGCHART: teams selling via partner channel (Santander, Telefonica, TIM, TELEKOM, Mexico)
#     - pbd = set of PBD (Business Developer) emails
#     - pae = set of PAE (Account Executive) emails
#     - leadership = directors, TLs (also sell — included in pbd/pae where applicable)
#     - active = True if team is fully onboarded for audit/snapshot/forecast
#   DIRECT_SALES: teams selling directly (no partner)
#     - ae = set of AE (Account Executive) emails
#     - subteams = nested team structure
#   XL_SALES: large enterprise sales team
#   MANAGER_EMAILS: managers who see reports but don't sell
# ──────────────────────────────────────────────────────────────────────────────

PARTNERS_ORGCHART = {  # & ALL entries — people, teams, emails
    "Telefonica": {
        "active": False,
        "pipeline_ids": ["11834984", "684767384"],
    },
    "TIM": {
        "active": True,
        "pipeline_ids": ["824790797", "3612610753"],
        "leadership": {
            "director": {"email": "andrea.galimberti@factorial.co", "name": "Andrea Galimberti", "role": "Director of Partnerships Italy"},
            "tl_pae": {"email": "nunzio.fumo@factorial.co", "name": "Nunzio Fumo", "role": "Partner Sales Team Lead"},
            "tl_pbd": {"email": "giacomo.torresi@factorial.co", "name": "Giacomo Torresi", "role": "Partner Business Developer Team Lead"},
        },
        "pbd": {
            "giacomo.torresi@factorial.co", "cecilia.rinaldo@factorial.co",
            "alessandro.cardinale@factorial.co", "miljan.nojkic@factorial.co",
        },
        "pae": {
            "nunzio.fumo@factorial.co", "marco.falaschetti@factorial.co",
            "emilio.fabbro@factorial.co", "giovanni.laghi@factorial.co",
            "edoardo.rapezzi@factorial.co", "christian.lombardo@factorial.co",
            "giuditta.giunta@factorial.co",
        },
    },
    "TELEKOM": {
        "active": True,
        "pipeline_ids": ["824790797", "3612610753"],
        "leadership": {
            "director": {"email": "laura.proefrock@factorial.co", "name": "Laura Proefrock", "role": "Partnerships Director DACH"},
            "tl_pae": {"email": "gabriel.lichtenstein@factorial.co", "name": "Gabriel Lichtenstein", "role": "Team Lead Partner Sales DACH"},
            "tl_pbd": {"email": "fiona.durr@factorial.co", "name": "Fiona Dürr", "role": "Partner Business Developer Team Lead"},
        },
        "pbd": {
            "fiona.durr@factorial.co", "enrique.gautier@factorial.co",
            "johanna.henrich@factorial.co", "chiang.nguyen@factorial.co",
            "alexander.ulrich@factorial.co",
        },
        "pae": {
            "gabriel.lichtenstein@factorial.co", "leonhard.zeus@factorial.co",
            "enrique.gautier@factorial.co", "katrin.virtbauer@factorial.co",
            "stefan.platt@factorial.co", "lior.shechori@factorial.co",
            "jonas.tretter@factorial.co",
        },
    },
    "Mexico": {
        "active": True,
        "pipeline_ids": ["default", "9048177"],
        "tl": "oriol.pesa@factorial.co", "tl_name": "Oriol Pesa",
        "subteams": {
            "Mexico Francesc": {
                "active": True,
                "tl": "francesc.terns@factorial.co", "tl_name": "Francesc Terns",
                "subteams": {
                    "Mexico Meritxell": {
                        "active": True,
                        "tl": "meritxell.goikoetxea@factorial.co", "tl_name": "Meritxell Goikoetxea",
                        "ae": {"daniela.orozco@factorial.co", "diana.bernal@factorial.co",
                               "cristian.ramos@factorial.co", "maximiliano.velasco@factorial.co"},
                    },
                },
                "ae": {"diego.hernandez@factorial.co", "marta.ruiz@factorial.co", "fabiola.villalobos@factorial.co"},
            },
            "Mexico Ernesto": {
                "active": True,
                "tl": "ernesto.blanco@factorial.co", "tl_name": "Ernesto Blanco Sierra",
                "ae": {"gustavo.torres@factorial.co", "eduardo.mahr@factorial.co"},
            },
        },
    },
}

DIRECT_SALES = {  # & ALL entries — people, teams, emails
    "pipeline_ids": ["default", "9048177", "831558698"],
    "teams": {
        "DS Joan Balaña": {
            "active": True,
            "tl": "joan.balana@factorial.co", "tl_name": "Joan Balaña",
            "subteams": {
                "DS Antoni Grau": {
                    "active": True,
                    "tl": "antoni.grau@factorial.co", "tl_name": "Antoni Grau Zorita",
                    "subteams": {
                        "DS Mireia": {
                            "active": True,
                            "tl": "mireia.bach@factorial.co", "tl_name": "Mireia Bach Ruiz",
                            "subteams": {
                                "DS Rubén": {
                                    "active": True,
                                    "tl": "ruben.mariscal@factorial.co", "tl_name": "Rubén Mariscal",
                                    "ae": {"blanca.orti@factorial.co", "arnau.palos@factorial.co", "nil.oleaga@factorial.co",
                                           "iban.cordobes@factorial.co", "camila.aldana@factorial.co", "miquel.criado@factorial.co",
                                           "guillermo.ferrer@factorial.co", "andreu.aloguin@factorial.co"},
                                },
                                "DS Andrea C": {
                                    "active": True,
                                    "tl": "andrea.castanar@factorial.co", "tl_name": "Andrea Castañar Esteban",
                                    "ae": {"gerard.tarradas@factorial.co", "nuria.gisbert@factorial.co",
                                           "abel.exposito@factorial.co", "denis.peramos@factorial.co",
                                           "tatiana.baltatescu@factorial.co", "carlota.alvarez@factorial.co",
                                           "alejandro.moreno@factorial.co", "pablo.andres@factorial.co"},
                                },
                            },
                            "ae": {"sonia.jimenez@factorial.co", "edgar.ybarguengoitia@factorial.co"},
                        },
                        "DS Roberto": {
                            "active": True,
                            "tl": "roberto.moran@factorial.co", "tl_name": "Roberto Morán",
                            "ae": {"xavier.fortuny@factorial.co", "jose.donis@factorial.co", "pol.bartolome@factorial.co",
                                   "beatriz.bravo@factorial.co", "joan.lorenzo@factorial.co"},
                        },
                        "DS Luis": {
                            "active": True,
                            "tl": "l.rodriguez@factorial.co", "tl_name": "Luis Rodriguez de Luz",
                            "ae": {"jordi.reina@factorial.co", "daniela.hernandez@factorial.co", "iker.gordo@factorial.co",
                                   "irene.orra@factorial.co", "maria.reina@factorial.co", "nuria.delacerda@factorial.co",
                                   "amadeo.cuellar@factorial.co"},
                        },
                        "DS Pilar": {
                            "active": True,
                            "tl": "pilar.elizaga@factorial.co", "tl_name": "Maria del Pilar Elizaga",
                            "ae": {"alejandra.denobregas@factorial.co", "andrea.alonso@factorial.co", "cristina.tarres@factorial.co",
                                   "david.donaire@factorial.co", "julia.flaque@factorial.co", "manuel.conesa@factorial.co"},
                        },
                        "DS Caterina": {
                            "active": True,
                            "tl": "caterina.peraire@factorial.co", "tl_name": "Caterina Peraire Lores",
                            "ae": {"alberto.toboso@factorial.co", "ignacio.catasus@factorial.co",
                                   "teresa.santamaria@factorial.co", "sabri.blaybel@factorial.co"},
                        },
                    },
                },
                "DS Zafra": {
                    "active": True,
                    "tl": "eduardo.zafra@factorial.co", "tl_name": "Eduardo Zafra",
                    "ae": {"daniel.terrasa@factorial.co", "belen.lombardia@factorial.co", "yolanda.tello@factorial.co"},
                },
                "DS Monica": {
                    "active": True,
                    "tl": "monica.ortiz@factorial.co", "tl_name": "Monica Ortiz",
                    "ae": {"david.clemente@factorial.co", "nerea.urien@factorial.co",
                           "alejandro.soto@factorial.co", "joane.fuldain@factorial.co"},
                },
            },
        },
    },
}

XL_SALES = {  # & ALL entries — people, emails
    "active": True,
    "pipeline_ids": ["685413816", "3576083668"],
    "country_manager": {"email": "ariadna.isla@factorial.co", "name": "Ariadna Isla Dominguez"},
    "ae": {
        "ariadna.isla@factorial.co", "lorena.tapia@factorial.co", "gerard.ghneim@factorial.co",
        "juan.ruiz@factorial.co", "gloria.nunez@factorial.co", "andre.reis@factorial.co",
    },
    "sdr": {
        "oriol.gubau@factorial.co", "karen.andrade@factorial.co",
        "jacobo.enriquez@factorial.co", "sebastian.boudet@factorial.co",
    },
}

MANAGER_EMAILS = {  # & ALL entries — manager emails
    "domenica.galarza@factorial.co", "oriol.delmoral@factorial.co",
    "alex.martinez@factorial.co", "guillem.catalan@factorial.co",
    "albert.fernandez@factorial.co", "samuel.fernandez@factorial.co",
    "lucas.siroo@factorial.co", "marc.macia@factorial.co",
    "marc.sorensen@factorial.co",
}


# ──────────────────────────────────────────────────────────────────────────────
# 19. PARTNER_IDENTITY
#
# WHAT: How to identify each partner in external data.
# WHERE: HubSpot deal names, partner_name field, email domains.
# HOW: partner_names = strings to match in deal data (lowercase).
#       partner_domains = email domains belonging to the partner.
# WHY: Partner detection (is this a partner deal?), prompt language selection,
#       timezone for briefing scheduling, prompt injection ("Banco Santander is the REFERRER").
# ──────────────────────────────────────────────────────────────────────────────

PARTNER_IDENTITY = {  # & ALL entries — partner names, domains, labels
    "Santander": {
        "partner_names": {"santander", "banco santander", "santander bank", "santander espana"},
        "partner_domains": {"gruposantander.es", "gruposantander.com", "santander.com", "bancosantander.es", "santander.es"},
        "prompt_partner_label": "Banco Santander / Telefonica",
        "lang": "es", "lang_file": "lang/es.txt", "tz": "Europe/Madrid",
    },
    "Telefonica": {
        "partner_names": {"telefonica", "telefónica", "telefonica espana", "telefónica españa", "movistar"},
        "partner_domains": {"telefonica.com", "telefonica.es", "movistar.es"},
        "prompt_partner_label": "Banco Santander / Telefonica",
        "lang": "es", "lang_file": "lang/es.txt", "tz": "Europe/Madrid",
    },
    "TIM": {
        "partner_names": {"tim", "tim italia", "telecom italia"},
        "partner_domains": {"sa.telecomitalia.it", "telecomitalia.it", "tim.com"},
        "prompt_partner_label": "TIM",
        "lang": "it", "lang_file": "lang/it.txt", "tz": "Europe/Rome",
    },
    "TELEKOM": {
        "partner_names": {"telekom", "deutsche telekom", "t-mobile"},
        "partner_domains": {"telekom.de"},
        "prompt_partner_label": "TELEKOM",
        "lang": "de", "lang_file": "lang/de.txt", "tz": "Europe/Berlin",
    },
    "Santander Mexico": {
        "partner_names": {"santander mexico", "santander mx", "santander méxico"},
        "partner_domains": {"gruposantander.es", "gruposantander.com", "santander.com"},
        "prompt_partner_label": "Santander Mexico",
        "lang": "es", "lang_file": "lang/es.txt", "tz": "America/Mexico_City",
    },
    "Mexico": {
        "partner_names": set(),
        "partner_domains": set(),
        "prompt_partner_label": "Mexico",
        "lang": "es", "lang_file": "lang/es.txt", "tz": "America/Mexico_City",
    },
}

TEAM_IDENTITY = {  # & ALL entries — team display config
    "direct_sales_es": {"lang": "es", "lang_file": "lang/es.txt", "tz": "Europe/Madrid"},
    "xl_sales":        {"lang": "es", "lang_file": "lang/es.txt", "tz": "Europe/Madrid"},
}

OUTPUT_LANG_DEFAULT = "es"
OUTPUT_LANGUAGES = {  # & ALL entries — language per team
    "es": "Responde siempre en español.",
    "en": "Always respond in English.",
    "it": "Rispondi sempre in italiano.",
    "de": "Antworte immer auf Deutsch.",
    "pt": "Responde sempre em português.",
}

PERSON_LANG_OVERRIDE: dict[str, str] = {  # & ALL entries — person-level language exceptions
    "andre.reis@factorial.co": "pt",
}

TIMEZONES = {  # & ALL entries — timezone per team
    "Europe/Madrid": ZoneInfo("Europe/Madrid"),
    "Europe/Rome": ZoneInfo("Europe/Rome"),
    "Europe/Berlin": ZoneInfo("Europe/Berlin"),
    "America/Mexico_City": ZoneInfo("America/Mexico_City"),
}
TZ_DEFAULT = ZoneInfo("Europe/Madrid")


# ══════════════════════════════════════════════════════════════════════════════
# PART VI — DOMAINS
#
# Email domain classification for filtering external contacts.
# Used by Atlas (ignore internal/generic emails) and Calendar (ignore internal meetings).
# ══════════════════════════════════════════════════════════════════════════════

INTERNAL_DOMAINS = frozenset({"factorial.co", "factorial.com", "factorialhr.com"})

GENERIC_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.es",
    "hotmail.com", "hotmail.es", "outlook.com", "outlook.es",
    "live.com", "icloud.com", "me.com", "protonmail.com",
    "aol.com", "mail.com", "zoho.com", "yandex.com", "tutanota.com",
    "msn.com", "gmx.com",
})

ISP_DOMAINS = frozenset({
    "telefonica.net", "movistar.es", "orange.es", "vodafone.es",
    "jazztel.es", "ono.com", "terra.es", "terra.com", "wanadoo.es",
    "libero.it", "alice.it", "tin.it", "virgilio.it",
    "tiscali.it", "fastwebnet.it", "pec.it",
    "t-online.de", "web.de", "gmx.de", "freenet.de", "arcor.de", "vodafone.de",
})

MISC_IGNORE_DOMAINS = frozenset({
    "seg-social.es", "aeat.es", "gob.es",
    "empresite.eleconomista.es", "empresia.es", "einforma.com",
    "icab.cat", "icab.es", "docs.hackerone.com", "visitandorra.com",
    "hormail.com", "cmheia.com", "omeie.com",
    "yopmail.com", "mailinator.com", "guerrillamail.com",
})


# ══════════════════════════════════════════════════════════════════════════════
# PART VII — API ENDPOINTS & CREDENTIALS
#
# Base URLs for external services. Auth tokens come from environment variables.
# ══════════════════════════════════════════════════════════════════════════════

API_ENDPOINTS = {
    "hubspot":          "https://api.hubapi.com",
    "hubspot_app":      "https://app.hubspot.com",
    "modjo":            "https://api.modjo.ai/v1",
    "slack":            "https://slack.com/api",
    "google_token":     "https://oauth2.googleapis.com/token",
    "google_calendar_scope": "https://www.googleapis.com/auth/calendar.readonly",
    "azure_api_version": "2024-10-01",
    "azure_auth_header": "api-key",

    # CRM API paths (HubSpot-specific)
    "deal_search":              "/crm/v3/objects/deals/search",
    "deal_batch_read":          "/crm/v3/objects/deals/batch/read",
    "owners":                   "/crm/v3/owners",
    "company_associations":     "/crm/v4/associations/deals/companies/batch/read",
    "partner_associations":     "/crm/v4/associations/deals/{partner_type}/batch/read",
    "company_read":             "/crm/v3/objects/companies/{company_id}",
    "company_search":           "/crm/v3/objects/companies/search",
    "association_read":         "/crm/v4/objects/{from_type}/{object_id}/associations/{to_type}",
    "batch_read":               "/crm/v3/objects/{object_type}/batch/read",
}


CRM_OWNER_RESPONSE_FIELDS = {  # ? HubSpot owner API response field names
    "id":         "id",
    "first_name": "firstName",
    "last_name":  "lastName",
    "email":      "email",
}

ENV_VARS = {
    "HUBSPOT_TOKEN":         "HubSpot private app token (Settings → Integrations → Private Apps)",
    "MODJO_API_KEY":         "Modjo API key (Settings → Integrations → API)",
    "GCAL_CLIENT_ID":        "Google OAuth client ID (Google Cloud Console → Credentials)",
    "GCAL_CLIENT_SECRET":    "Google OAuth client secret",
    "GCAL_REFRESH_TOKEN":    "Google OAuth refresh token (generated during initial auth flow)",
    "AZURE_CLAUDE_ENDPOINT": "Azure AI Foundry endpoint for Claude (e.g. https://xxx.openai.azure.com)",
    "SUPABASE_URL":          "Supabase project URL (e.g. https://xxx.supabase.co)",
    "SUPABASE_KEY":          "Supabase service role key",
}


# ══════════════════════════════════════════════════════════════════════════════
# DERIVED — auto-computed from sections above. Do not edit manually.
# ══════════════════════════════════════════════════════════════════════════════

CRM_ALL_DEAL_PROPS = list(CRM_DEAL_PROPERTIES.keys()) + list(CRM_STAGE_DATE_PROPERTIES.keys())
CRM_ALL_EMAIL_PROPS = list(CRM_EMAIL_PROPERTIES.keys())
CRM_ALL_NOTE_PROPS = list(CRM_NOTE_PROPERTIES.keys())
CRM_ALL_CALL_PROPS = list(CRM_CALL_PROPERTIES.keys())
CRM_ALL_MEETING_PROPS = list(CRM_MEETING_CONTEXT_PROPERTIES.keys())
CRM_ALL_MEETING_SYNC_PROPS = list(CRM_MEETING_SYNC_PROPERTIES.keys())

CRM_TO_SUPABASE = {k: v["column"] for k, v in CRM_DEAL_PROPERTIES.items()}
CRM_TO_SUPABASE.update({k: v["column"] for k, v in CRM_STAGE_DATE_PROPERTIES.items()})
CRM_TO_SUPABASE_MEETINGS = {k: v["column"] for k, v in CRM_MEETING_SYNC_PROPERTIES.items()}

# internal name → CRM property name (reverse of CRM_DEAL_PROPERTIES)
CRM_INTERNAL_TO_PROP = {v["internal"]: k for k, v in CRM_DEAL_PROPERTIES.items()}


def crm_prop(internal_name: str) -> str:
    """Internal name → CRM property name.  crm_prop("stage") → "dealstage" """
    return CRM_INTERNAL_TO_PROP[internal_name]

ALL_AUDIT_TAGS = CALL_TAGS_PBD | CALL_TAGS_PAE | CALL_TAGS_DIRECT_SALES
ALL_KNOWN_TAGS = ALL_AUDIT_TAGS | CALL_TAGS_PARTNER_MGMT | CALL_TAGS_SKIP | CALL_TAGS_METADATA

CRM_PIPELINE_NAMES = {v["name"]: k for k, v in CRM_PIPELINE_MAP.items()}
CRM_ACTIVE_PIPELINE_IDS = [pid for pid, v in CRM_PIPELINE_MAP.items() if v["active"]]
CRM_EXCLUDE_PIPELINE_IDS = {pid for pid, v in CRM_PIPELINE_MAP.items() if not v["active"]}

# ? CRM stage label (from CRM_STAGE_MAP) → schema internal name
CRM_STAGE_LABEL_TO_INTERNAL = {
    "New":                                  "new",
    "New Deals":                            "new_deals",
    "New Qualified Opportunity":            "new_qualified",
    "Research & Outreach":                  "research_outreach",
    "Outreach":                             "outreach",
    "Pre-qualified":                        "pre_qualified",
    "Attempting to contact":                "attempting_to_contact",
    "Attempted to contact":                 "attempted_to_contact",
    "Associating the partner":              "associating_partner",
    "Connected - Not Engaged":              "connected_not_engaged",
    "Engaged":                              "engaged",
    "Demo request from Prospect":           "demo_request",
    "Demo Request from Prospect":           "demo_request",
    "Demo Booked":                          "demo_booked",
    "Meeting Booked":                       "meeting_booked",
    "Meeting scheduled":                    "meeting_scheduled",
    "Discovery":                            "discovery",
    "MEDDPICC Criteria Validation Started": "meddpicc_validation",
    "Factorial Project Alignment started":  "factorial_project_alignment",
    "Product Alignment":                    "product_alignment",
    "Economical Alignment Started":         "economical_alignment",
    "Pricing & Packaging":                  "pricing_packaging",
    "Pricing and Packaging":                "pricing_packaging",
    "Contracting":                          "contracting",
    "Contract Sent":                        "contract_sent",
    "Contract negotiation (Ongoing) ":      "contract_negotiation",
    "Closed - pending finance validation":  "closed_pending_validation",
    "Closed Pending Payment":               "closed_pending_payment",
    "Closed Won":                           "closed_won",
    "Closed won":                           "closed_won",
    "Closed Won - Finance Only":            "closed_won_finance",
    "Closed Lost":                          "closed_lost",
    "Closed lost":                          "closed_lost",
    "Opportunity lost":                     "opportunity_lost",
    "Opportunity Lost":                     "opportunity_lost",
    "Opportunity Lost ":                    "opportunity_lost",
    "On Hold":                              "on_hold",
    "To reschedule":                        "to_reschedule",
    "To Reschedule":                        "to_reschedule",
    "Nurturing":                            "nurturing",
    "Hot Nurturing":                        "hot_nurturing",
    "Long Nurturing":                       "long_nurturing",
    "Sales Nurturing":                      "sales_nurturing",
}

SLACK_ACTIVE = {email for email, ch in SLACK_PERSON_CHANNELS.items() if ch}


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING NOTE — Supabase seed tables (one-shot, not synced)
#
# The tables below are NOT fed by any API or pipeline. They must be populated
# manually in Supabase when onboarding a new company. Without them, Claude's
# product analysis and benchmarking will be empty.
#
#   product_stats  — Product catalog with benchmarks per module.
#                    Columns: product name, adoption %, avg deal size, common objections,
#                    competitive positioning, target persona. One row per product.
#                    Used by: snapshot prompts (product_assessment, expansion_summary).
#
# This is static reference data — update when the product catalog changes.
# ══════════════════════════════════════════════════════════════════════════════
