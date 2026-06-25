"""
Closzr — Configuracion centralizada.

Estructura:
  1. PATHS, TIMEZONE, MODELS, LANGUAGES
  2. ORGCHART — personas, roles, jerarquias (Partners + Direct Sales + XL)
  3. PARTNER IDENTITY — nombres, dominios, idioma, timezone por partner
  4. HUBSPOT DEAL SEARCH — pipelines, sync strategy, busqueda 3 fases, owner IDs, routing
  5. DEAL STAGES — categorias funcionales, stage IDs, sets compuestos
  6. MODJO TAGS — tags por categoria, multi-tag resolution, audit level, prompt mapping
  7. SLACK — canales por equipo y persona
  8. EB ALERTS — colores, headers
  9. HUBSPOT PROPERTIES — props que pedimos a la API
  10. DOMAINS — dominios internos, genericos, partner, ISP
  11. CALENDAR — keywords para filtrar meetings internas
  12. THRESHOLDS — limites, batch sizes, timeouts, max_tokens
  13. FORECAST — pesos formula probabilidad
  14. LOCALIZACION — meses y dias en espanol
  15. API ENDPOINTS
  16. DERIVED SETS — generados automaticamente del orgchart
  17. HELPER FUNCTIONS
"""

from pathlib import Path
from zoneinfo import ZoneInfo


# ============================================================================
# 1. PATHS, TIMEZONE, MODELS
# ============================================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
PROMPTS_DIR = ROOT_DIR / "prompts"

# Timezone por defecto (Europa). Cada equipo puede tener la suya en PARTNER_IDENTITY.
TZ_DEFAULT = ZoneInfo("Europe/Madrid")

TIMEZONES = {
    "Europe/Madrid": ZoneInfo("Europe/Madrid"),       # Santander, Telefonica, DS España
    "Europe/Rome": ZoneInfo("Europe/Rome"),            # TIM
    "Europe/Berlin": ZoneInfo("Europe/Berlin"),        # TELEKOM
    "America/Mexico_City": ZoneInfo("America/Mexico_City"),  # México
}

# Claude (Azure AI Foundry)
MODEL_SONNET = "claudio-claude-sonnet-4-6"
MODEL_OPUS = "claudio-claude-opus-4-6"
MODEL_DEFAULT = MODEL_SONNET

# GPT (Azure AI Foundry — requiere OpenAI SDK, no Anthropic SDK)
MODEL_GPT_55 = "claudio-gpt-5.5"
MODEL_GPT_54_MINI = "claudio-gpt-5.4-mini"

# Idioma de los outputs generados por Claude.
# Cada equipo puede tener el suyo (definido en PARTNER_IDENTITY.lang).
# Este es el default para equipos sin lang definido.
OUTPUT_LANG_DEFAULT = "es"

OUTPUT_LANGUAGES = {
    "es": "Responde siempre en español.",
    "en": "Always respond in English.",
    "it": "Rispondi sempre in italiano.",
    "de": "Antworte immer auf Deutsch.",
}


# ============================================================================
# 2. ORGCHART
#
# Todas las personas, roles y jerarquias en un solo sitio.
# Cada persona que cierra deals esta en pbd/pae/ae (incluidos TLs y directors).
# El campo "leadership" indica quien gestiona a quien, no excluye de vender.
# ============================================================================

# --- 2a. Partners ---

PARTNERS_ORGCHART = {

    "Santander": {
        "active": True,
        "leadership": {
            "director": {"email": "joan.balana@factorial.co", "name": "Joan Balaña", "role": "Partner Sales Director", "scope": ["Santander", "Telefonica"]},
            "tl_pae": {"email": "roberto.moran@factorial.co", "name": "Roberto Morán", "role": "Partner Sales Manager"},
            "tl_pbd": {"email": "carlos.acosta@factorial.co", "name": "Carlos Acosta", "role": "Partner Business Developer Manager", "scope": ["Santander", "Telefonica"]},
        },
        "pbd": {
            "carlos.acosta@factorial.co",
            "ines.rivera@factorial.co",
            "marta.ruiz@factorial.co",
            "paula.gil@factorial.co",
            "david.soler@factorial.co",
            "lucia.garana@factorial.co",
            "ignacio.otero@factorial.co",
            "nicolas.gonzalez@factorial.co",
        },
        "pae": {
            "joan.balana@factorial.co",
            "roberto.moran@factorial.co",
            "eduardo.zafra@factorial.co",
            "xavier.fortuny@factorial.co",
            "jose.donis@factorial.co",
            "pol.bartolome@factorial.co",
            "beatriz.bravo@factorial.co",
            "joan.lorenzo@factorial.co",
        },
    },

    "Telefonica": {
        "active": True,
        "leadership": {
            "director": {"email": "joan.balana@factorial.co", "name": "Joan Balaña", "role": "Partner Sales Director", "scope": ["Santander", "Telefonica"]},
            "tl_pae": {"email": "carlos.sanchez@factorial.co", "name": "Carlos Sanchez", "role": "PAE Team Leader Telefónica"},
            "tl_pbd": {"email": "carlos.acosta@factorial.co", "name": "Carlos Acosta", "role": "Partner Business Developer Manager", "scope": ["Santander", "Telefonica"]},
        },
        "pbd": {
            "carlos.acosta@factorial.co",
            "angel.hernandez@factorial.co",
            "jon.azconobieta@factorial.co",
            "maria.masoliver@factorial.co",
            "alejandro.soto@factorial.co",
        },
        "pae": {
            "joan.balana@factorial.co",
            "carlos.sanchez@factorial.co",
            "david.clemente@factorial.co",
            "nerea.urien@factorial.co",
            "alejandro.soto@factorial.co",
        },
    },

    "TIM": {
        "active": True,
        "leadership": {
            "director": {"email": "andrea.galimberti@factorial.co", "name": "Andrea Galimberti", "role": "Director of Partnerships Italy"},
            "tl_pae": {"email": "nunzio.fumo@factorial.co", "name": "Nunzio Fumo", "role": "Partner Sales Team Lead"},
            "tl_pbd": {"email": "giacomo.torresi@factorial.co", "name": "Giacomo Torresi", "role": "Partner Business Developer Team Lead"},
        },
        # Nota: hay deals TIM en Sales Pipeline gestionados por Direct Sales Italia
        # (Giacomo Fatti, Davide Calise, Simone Gentili, etc.) → se mapearan con direct_sales_it
        "pbd": {
            "giacomo.torresi@factorial.co",
            "cecilia.rinaldo@factorial.co",
            "alessandro.cardinale@factorial.co",
            "miljan.nojkic@factorial.co",
        },
        "pae": {
            "nunzio.fumo@factorial.co",
            "marco.falaschetti@factorial.co",
            "emilio.fabbro@factorial.co",
            "giovanni.laghi@factorial.co",
            "edoardo.rapezzi@factorial.co",
            "christian.lombardo@factorial.co",
            "giuditta.giunta@factorial.co",
        },
    },

    "TELEKOM": {
        "active": True,
        "leadership": {
            "director": {"email": "laura.proefrock@factorial.co", "name": "Laura Proefrock", "role": "Partnerships Director DACH"},
            "tl_pae": {"email": "gabriel.lichtenstein@factorial.co", "name": "Gabriel Lichtenstein", "role": "Team Lead Partner Sales DACH"},
            "tl_pbd": {"email": "fiona.durr@factorial.co", "name": "Fiona Dürr", "role": "Partner Business Developer Team Lead"},
        },
        # Nota: hay deals TELEKOM en Sales Pipeline gestionados por DS Alemania
        # (Andy Guasch, Niklas Hildermann) → se mapearan con direct_sales_de
        "pbd": {
            "fiona.durr@factorial.co",
            "enrique.gautier@factorial.co",
            "johanna.henrich@factorial.co",
            "chiang.nguyen@factorial.co",
            "alexander.ulrich@factorial.co",
        },
        "pae": {
            "gabriel.lichtenstein@factorial.co",
            "leonhard.zeus@factorial.co",
            "enrique.gautier@factorial.co",
            "katrin.virtbauer@factorial.co",
            "stefan.platt@factorial.co",
            "lior.shechori@factorial.co",
            "jonas.tretter@factorial.co",
        },
    },

    # ====================================================================
    # SANTANDER CHANNEL — equipo México (antes "Mexico")
    # Deals con partner association → team del partner (ej: "Santander Mexico")
    # Deals sin partner → team = "Santander Channel"
    # ====================================================================

    "Santander Channel": {
        "active": False,
        "leadership": {
            "director_1": {"email": "francesc.terns@factorial.co", "name": "Francesc Terns", "role": "Channel Manager Mexico"},
            "director_2": {"email": "ernesto.blanco@factorial.co", "name": "Ernesto Blanco Sierra", "role": "Director Mexico"},
        },
        "pbd": {
            "diego.hernandez@factorial.co",
            "marta.ruiz@factorial.co",
        },
        "pae": {
            "diana.bernal@factorial.co",
            "ernesto.blanco@factorial.co",
            "cristian.ramos@factorial.co",
            "daniela.orozco@factorial.co",
            "diego.hernandez@factorial.co",
            "xavier.fortuny@factorial.co",
            "eduardo.mahr@factorial.co",
            "fabiola.villalobos@factorial.co",
        },
    },
}

# --- 2b. Direct Sales España ---

DIRECT_SALES_ES = {
    "sales_director": {
        "email": "antoni.grau@factorial.co",
        "name": "Antoni Grau Zorita",
        "role": "Sales Director",
    },
    "teams": {
        "DS Mireia": {
            "active": False,
            "tl": "mireia.bach@factorial.co",
            "tl_name": "Mireia Bach Ruiz",
            "role": "AE OB Senior Manager Spain",
            "subteams": {
                "DS Rubén": {
                    "tl": "ruben.mariscal@factorial.co",
                    "tl_name": "Rubén Mariscal",
                    "ae": {
                        "blanca.orti@factorial.co",
                        "arnau.palos@factorial.co",
                        "nil.oleaga@factorial.co",
                        "iban.cordobes@factorial.co",
                        "camila.aldana@factorial.co",
                        "miquel.criado@factorial.co",
                        "tatiana.baltatescu@factorial.co",
                    },
                },
                "DS Andrea C": {
                    "tl": "andrea.castanar@factorial.co",
                    "tl_name": "Andrea Castañar Esteban",
                    "ae": {
                        "m.gracia@factorial.co",
                        "gerard.tarradas@factorial.co",
                        "nuria.gisbert@factorial.co",
                        "abel.exposito@factorial.co",
                        "denis.peramos@factorial.co",
                    },
                },
            },
            "ae": {
                "josep.fora@factorial.co",
                "andreu.aloguin@factorial.co",
            },
        },
        "DS Tania": {
            "active": False,
            "tl": "tania.diaz@factorial.co",
            "tl_name": "Tania Diaz Soto",
            "ae": {
                "alejandro.moreno@factorial.co",
                "carlota.alvarez@factorial.co",
                "edgar.ybarguengoitia@factorial.co",
                "guillermo.ferrer@factorial.co",
                "sabri.blaybel@factorial.co",
                "sonia.jimenez@factorial.co",
            },
        },
        "DS Luis": {
            "active": False,
            "tl": "l.rodriguez@factorial.co",
            "tl_name": "Luis Rodriguez de Luz",
            "ae": {
                "jordi.reina@factorial.co",
                "daniela.hernandez@factorial.co",
                "iker.gordo@factorial.co",
                "irene.orra@factorial.co",
                "maria.reina@factorial.co",
                "nuria.delacerda@factorial.co",
                "amadeo.cuellar@factorial.co",
                "alvaro.figuerola@factorial.co",
            },
        },
        "DS Pilar": {
            "active": False,
            "tl": "pilar.elizaga@factorial.co",
            "tl_name": "Maria del Pilar Elizaga",
            "ae": {
                "alejandra.denobregas@factorial.co",
                "andrea.alonso@factorial.co",
                "cristina.tarres@factorial.co",
                "david.donaire@factorial.co",
                "julia.flaque@factorial.co",
                "lucia.detorres@factorial.co",
                "manuel.conesa@factorial.co",
            },
        },
        "DS Caterina": {
            "active": False,
            "tl": "caterina.peraire@factorial.co",
            "tl_name": "Caterina Peraire Lores",
            "ae": {
                "alberto.toboso@factorial.co",
                "ignacio.catasus@factorial.co",
                "jordi.miravet@factorial.co",
                "teresa.santamaria@factorial.co",
            },
        },
    },
}

# --- 2c. XL Sales (Iberia) ---

XL_SALES = {
    "active": False,
    "country_manager": {
        "email": "ariadna.isla@factorial.co",
        "name": "Ariadna Isla Dominguez",
        "role": "XL Country Manager IBERIA",
    },
    "ae": {
        "ariadna.isla@factorial.co",
        "lorena.tapia@factorial.co",
        "gerard.ghneim@factorial.co",
        "juan.ruiz@factorial.co",
        "gloria.nunez@factorial.co",
        "andre.reis@factorial.co",
    },
    "sdr": {
        "oriol.gubau@factorial.co",
        "karen.andrade@factorial.co",
        "jacobo.enriquez@factorial.co",
        "sebastian.boudet@factorial.co",
    },
}

MANAGER_EMAILS = {
    "domenica.galarza@factorial.co",
    "oriol.delmoral@factorial.co",
    "alex.martinez@factorial.co",
    "guillem.catalan@factorial.co",
    "albert.fernandez@factorial.co",
    "samuel.fernandez@factorial.co",
    "lucas.siroo@factorial.co",
    "marc.macia@factorial.co",
    "marc.sorensen@factorial.co",
}


# ============================================================================
# 3. PARTNER IDENTITY — como identificamos cada partner
# ============================================================================

PARTNER_IDENTITY = {
    "Santander": {
        # partner_names: como aparece en HubSpot partner_name y dealnames (lowercase)
        "partner_names": {"santander", "banco santander", "santander bank", "santander espana"},
        "partner_domains": {"gruposantander.es", "gruposantander.com", "santander.com", "bancosantander.es", "santander.es"},
        "prompt_partner_label": "Banco Santander / Telefonica",
        "lang": "es",
        "lang_file": "lang_es_startup.txt",
        "tz": "Europe/Madrid",
    },
    "Telefonica": {
        "partner_names": {"telefonica", "telefónica", "telefonica espana", "telefónica españa", "movistar"},
        "partner_domains": {"telefonica.com", "telefonica.es", "movistar.es"},
        "prompt_partner_label": "Banco Santander / Telefonica",
        "lang": "es",
        "lang_file": "lang_es_startup.txt",
        "tz": "Europe/Madrid",
    },
    "TIM": {
        "partner_names": {"tim", "tim italia", "telecom italia"},
        "partner_domains": {"sa.telecomitalia.it", "telecomitalia.it", "tim.com"},
        "prompt_partner_label": "TIM",
        "lang": "it",
        "lang_file": "lang_it.txt",
        "tz": "Europe/Rome",
    },
    "TELEKOM": {
        "partner_names": {"telekom", "deutsche telekom", "t-mobile"},
        "partner_domains": {"telekom.de"},
        "prompt_partner_label": "TELEKOM",
        "lang": "en",
        "lang_file": "lang_en.txt",
        "tz": "Europe/Berlin",
    },
    "Santander Mexico": {
        "partner_names": {"santander mexico", "santander mx", "santander méxico"},
        "partner_domains": {"gruposantander.es", "gruposantander.com", "santander.com"},
        "prompt_partner_label": "Santander Mexico",
        "lang": "es",
        "lang_file": "lang_es_startup.txt",
        "tz": "America/Mexico_City",
    },
    "Santander Channel": {
        "partner_names": set(),
        "partner_domains": set(),
        "prompt_partner_label": "Santander Channel",
        "lang": "es",
        "lang_file": "lang_es_startup.txt",
        "tz": "America/Mexico_City",
    },
}

# Direct Sales y XL no tienen partner, pero si tienen lang y tz
DS_IDENTITY = {
    "direct_sales_es": {
        "lang": "es",
        "lang_file": "lang_es_startup.txt",
        "tz": "Europe/Madrid",
    },
}

XL_IDENTITY = {
    "xl_sales": {
        "lang": "es",
        "lang_file": "lang_es_startup.txt",
        "tz": "Europe/Madrid",
    },
}


# ============================================================================
# 4. HUBSPOT DEAL SEARCH — como encontrar deals de cada equipo
#
# Cada entrada describe QUE queries hacer en HubSpot Search API para
# encontrar los deals de ese equipo. Separado del orgchart.
# ============================================================================

# --- 4a. Pipeline ID ↔ nombre ---

# Todos los pipelines de HubSpot: ID ↔ nombre
HUBSPOT_PIPELINE_IDS = {
    # --- Venta nueva (los que procesamos) ---
    "11834984": "Partners Distribution",
    "684767384": "SDR Partner Opportunities Pipeline",
    "default": "Sales Pipeline",
    "9048177": "OB SDR Pipeline",
    "831558698": "IB SDR Pipeline",
    "685413816": "XL Account Pipeline",
    "3576083668": "XL SDR Pipeline",
    "824790797": "IT AE Pipeline",
    "3612610753": "IT SDR Pipeline",
    # --- Post-venta / no procesamos (excluidos) ---
    "12669399": "Upselling Pipeline",
    "120778282": "Onboarding Pipeline",
    "84352288": "Churn Pipeline",
    "14163264": "Partner Acquisition",
    "823385946": "BR SDR Pipeline - Outbound",
    "85850465": "Brazil Sales Pipeline",
    "3508829384": "Consultants Pipeline",
    "3721428207": "Hubspot Shared Pipeline",
}

HUBSPOT_PIPELINE_NAMES = {v: k for k, v in HUBSPOT_PIPELINE_IDS.items()}

# Pipelines que NUNCA procesamos — no son venta nueva.
# Se filtran antes de cualquier busqueda o routing.
EXCLUDE_PIPELINE_IDS = {
    "12669399",     # Upselling Pipeline
    "120778282",    # Onboarding Pipeline
    "84352288",     # Churn Pipeline
    "14163264",     # Partner Acquisition
    "823385946",    # BR SDR Pipeline - Outbound
    "85850465",     # Brazil Sales Pipeline
    "3508829384",   # Consultants Pipeline
    "3721428207",   # Hubspot Shared Pipeline
}

# --- 4b. Pipelines por tipo ---

# Pipelines donde deals son SIEMPRE del partner (partner_name manda)
PARTNER_PIPELINES = ["Partners Distribution", "SDR Partner Opportunities Pipeline"]

# Pipelines donde el owner manda (DS, XL, o PAE partner en ventas directas)
OWNER_PIPELINES = [
    "Sales Pipeline", "OB SDR Pipeline", "IB SDR Pipeline",
    "XL Account Pipeline", "XL SDR Pipeline",
    "IT AE Pipeline", "IT SDR Pipeline",
]

ALL_ACTIVE_PIPELINES = PARTNER_PIPELINES + OWNER_PIPELINES

# IDs de los pipelines activos (para queries HubSpot que usan IDs, no nombres)
ACTIVE_PIPELINE_IDS = [pid for pid in HUBSPOT_PIPELINE_IDS if pid not in EXCLUDE_PIPELINE_IDS]

# --- 4b. Sync strategy ---
#
# Dos modos:
#   INCREMENTAL (default, cada hora):
#     Busca solo deals con hs_lastmodifieddate >= last_sync.
#     Volumen: ~300-500 deals/hora. ~5-10 API calls. <3 segundos.
#     hs_lastmodifieddate se actualiza con: stage change, owner change,
#     amount change, call/email/meeting loggeado, asociacion de contacto.
#
#   FULL (primera vez o semanal):
#     Busca TODOS los deals activos. ~35k deals. ~23 API calls con batch.
#
# En ambos modos, la busqueda es en 3 fases:
#
# FASE 1 — PARTNER DEALS (1 API call con batch)
#   Query: partner_name IN [Santander, Telefonica, TIM, Deutsche Telekom]
#   Todos los active pipelines (no solo Partners Dist).
#   Un deal de Santander en Sales Pipeline tambien se encuentra aqui.
#   Batch: 4 filterGroups OR en 1 sola query.
#
# FASE 2 — MEXICO (1 API call)
#   Query: current_hubspot_team__string_ = 'Partners - PBD LATAM'
#   Mexico no tiene partner_name fiable (muchos NULL).
#   No se puede buscar por owner (Marta Ruiz y Xavier son compartidos con Sant ES).
#   Volumen: ~141 deals (full) / ~5-10 (incremental)
#
# FASE 3 — OWNER DEALS (batch por owner_id, ~21 API calls)
#   Query: hubspot_owner_id IN [nuestros AEs] por pipeline.
#   Captura: DS (~19,136), XL (~5,487), PAEs con deals sin partner_name.
#   Batch: 5 owner_ids por filterGroup, max 5 filterGroups por query.
#   Dedup: excluye deal_ids ya encontrados en Fase 1/2.
#   Volumen: ~24,600 deals (full) / ~200-300 (incremental)
#
# Despues de encontrar: get_deal_team() categoriza cada deal.

SYNC_STRATEGY = {
    "default_mode": "incremental",
    "full_sync_interval_hours": 168,    # full sync semanal
    "incremental_lookback_minutes": 70, # 70 min para no perder deals entre runs de 60 min
}

# --- Core trigger ---
# hs_lastmodifieddate: para ENCONTRAR deals que cambiaron (query a HubSpot)
# notes_last_updated: para DECIDIR si activar el CORE (comparar con Supabase)
#   Se actualiza con: call, email, meeting, nota, task (automatico por HubSpot)
#   Si notes_last_updated del deal en HubSpot > last_activity_hs en Supabase
#   → hay contenido nuevo → context_stale = True → CORE procesa
#   Si solo hs_lastmodifieddate cambio pero notes_last_updated no
#   → fue metadata (stage, amount, owner) → solo sync, no CORE
CORE_TRIGGER = {
    "search_property": "hs_lastmodifieddate",   # para encontrar deals modificados
    "activity_property": "notes_last_updated",   # para decidir si activar CORE
    "supabase_column": "last_activity_hs",       # columna en Supabase para comparar
}

# --- Partner object mapping (HubSpot custom object → team) ---

PARTNER_OBJECT_TYPE_ID = "2-3229093"

# HubSpot Partner object ID → team name
PARTNER_OBJECT_MAP = {
    "4767807590":    "Santander",       # Santander
    "401845373146":  "Santander Mexico",# Santander México
    "28079747484":   "Santander",       # Santander PT
    "4767660726":    "Telefonica",      # Telefonica
    "25968646986":   "TIM",             # TIM
    "25359694224":   "TELEKOM",         # Deutsche Telekom
    "34458760336":   "MEO",             # MEO / Altice
}

# HubSpot Partner object ID → partner display name
PARTNER_NAMES = {
    "4767807590":    "Santander",
    "401845373146":  "Santander México",
    "28079747484":   "Santander PT",
    "4767660726":    "Telefonica",
    "25968646986":   "TIM",
    "25359694224":   "Deutsche Telekom",
    "34458760336":   "MEO / Altice",
}

# --- 4c. HubSpot owner ID por email (para busqueda by_owner) ---

HUBSPOT_OWNER_IDS = {
    "abel.exposito@factorial.co": {"id": "81684298", "name": "Abel Expósito Roselló"},
    "albert.fernandez@factorial.co": {"id": "309581666", "name": "Albert Fernandez"},
    "alberto.toboso@factorial.co": {"id": "86980984", "name": "Alberto Toboso"},
    "alejandra.denobregas@factorial.co": {"id": "1911202931", "name": "Alejandra De Nóbregas"},
    "alejandro.moreno@factorial.co": {"id": "34637474", "name": "Alejandro Moreno Luna"},
    "alejandro.soto@factorial.co": {"id": "32980021", "name": "Alejandro Soto Velasco"},
    "alessandro.cardinale@factorial.co": {"id": "89052244", "name": "Alessandro Cardinale"},
    "alex.martinez@factorial.co": {"id": "79352699", "name": "Alex Martinez"},
    "alexander.ulrich@factorial.co": {"id": "86686795", "name": "Alexander Ulrich"},
    "alvaro.figuerola@factorial.co": {"id": "32980189", "name": "Álvaro Figuerola Ocáriz"},
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
    "jordi.miravet@factorial.co": {"id": "85521548", "name": "Jordi Miravet"},
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
    "m.gracia@factorial.co": {"id": "734068887", "name": "María Gracia Guerra"},
    "manuel.conesa@factorial.co": {"id": "84984311", "name": "Manuel Conesa"},
    "marco.falaschetti@factorial.co": {"id": "187721367", "name": "Marco Falaschetti"},
    "maria.masoliver@factorial.co": {"id": "32147470", "name": "María Masoliver"},
    "maria.reina@factorial.co": {"id": "1358098012", "name": "Maria Reina Caballero"},
    "marta.ruiz@factorial.co": {"id": "554655901", "name": "Marta Ruiz Sánchez"},
    "miljan.nojkic@factorial.co": {"id": "34212992", "name": "Miljan Nojkic"},
    "miquel.criado@factorial.co": {"id": "32708305", "name": "Miquel Criado"},
    "mireia.bach@factorial.co": {"id": "103459488", "name": "Mireia Bach"},
    "nerea.urien@factorial.co": {"id": "645417472", "name": "Nerea Urien Meizoso"},
    "nicolas.gonzalez@factorial.co": {"id": "84394154", "name": "Nicolás González-Tarrío"},
    "nil.oleaga@factorial.co": {"id": "82847426", "name": "Nil Oleaga"},
    "nunzio.fumo@factorial.co": {"id": "343525024", "name": "Nunzio Fumo"},
    "nuria.delacerda@factorial.co": {"id": "80763157", "name": "Nuria De La Cerda Sánchez"},
    "nuria.gisbert@factorial.co": {"id": "78959985", "name": "Nuria Gisbert Martínez"},
    "oriol.gubau@factorial.co": {"id": "673801091", "name": "Oriol Gubau"},
    "paula.gil@factorial.co": {"id": "81867010", "name": "Paula Gil"},
    "pilar.elizaga@factorial.co": {"id": "86980707", "name": "Maria del Pilar Elizaga"},
    "pol.bartolome@factorial.co": {"id": "105443852", "name": "Pol Bartolomé"},
    "roberto.moran@factorial.co": {"id": "105445464", "name": "Roberto Morán"},
    "ruben.mariscal@factorial.co": {"id": "490300827", "name": "Rubén Mariscal"},
    "sabri.blaybel@factorial.co": {"id": "121160834", "name": "Sabri Blaybel"},
    "sebastian.boudet@factorial.co": {"id": "84394220", "name": "Sebastian Boudet"},
    "sonia.jimenez@factorial.co": {"id": "82431538", "name": "Sonia Jimenez Ruiz"},
    "stefan.platt@factorial.co": {"id": "86980969", "name": "Stefan Platt"},
    "tania.diaz@factorial.co": {"id": "146400912", "name": "Tania Diaz Soto"},
    "tatiana.baltatescu@factorial.co": {"id": "33868827", "name": "Tatiana Baltatescu"},
    "teresa.santamaria@factorial.co": {"id": "390628148", "name": "Teresa Santamaria"},
    "xavier.fortuny@factorial.co": {"id": "76824216", "name": "Xavier Fortuny"},
    # No encontrados en HubSpot:
    # "camila.aldana@factorial.co": ???
}

HUBSPOT_ACCOUNT_ID = "4960096"


# ============================================================================
# 5. DEAL STAGES — single source of truth
#
# HubSpot tiene 93 stage IDs unicos pero solo 39 labels.
# Cada pipeline tiene sus propios IDs para el mismo stage
# (ej: "Meeting Booked" tiene 7 IDs diferentes, uno por pipeline).
# Mapeamos por LABEL porque es lo que usamos en el codigo.
# STAGE_ID_TO_LABEL convierte IDs raw a labels cuando es necesario.
#
# Categorias funcionales: cada stage pertenece a UNA sola categoria.
# Los sets compuestos (ACTIVE_STAGES, etc.) son uniones de categorias.
# ============================================================================

# --- Stage ID → Label (93 IDs → 39 labels) ---
# Cuando HubSpot devuelve un ID raw en vez del label, usamos este mapping.
STAGE_ID_TO_LABEL = {
    # Partners Distribution
    "35070729": "New Deals", "4977567965": "To reschedule",
    "35070730": "Demo Booked", "5366023400": "MEDDPICC Criteria Validation Started",
    "35070731": "Factorial Project Alignment started", "35118878": "Economical Alignment Started",
    "35118879": "Contract Sent", "104503991": "Closed - pending finance validation",
    "35118880": "Closed Won", "1008401982": "On Hold", "35119283": "Closed Lost",
    # SDR Partner Opportunities
    "1002830265": "Pre-qualified", "1002830336": "Attempting to contact",
    "1002830337": "Associating the partner", "1002830338": "Engaged",
    "1002830339": "Demo Booked", "1002830340": "Nurturing",
    "1002830341": "Opportunity lost", "1002829480": "To reschedule",
    # Sales Pipeline
    "f26b487d-e715-49c8-add3-9fa86aef79da": "To reschedule",
    "96e820da-7bc1-4ea3-81a2-bc533ed26934": "Meeting Booked",
    "49b7ad85-a23e-426c-9b3b-d44607d1c3af": "Discovery",
    "appointmentscheduled": "Product Alignment",
    "qualifiedtobuy": "Pricing & Packaging",
    "15738025": "Contracting", "51389338": "Closed - pending finance validation",
    "closedwon": "Closed won", "closedlost": "Closed lost",
    # OB SDR Pipeline
    "25761461": "New", "25761462": "Research & Outreach",
    "25761463": "Connected - Not Engaged", "26471690": "Engaged",
    "25761464": "Meeting Booked", "25761536": "To Reschedule",
    "27564328": "Hot Nurturing", "25761465": "Long Nurturing",
    "25761537": "Opportunity lost",
    # IB SDR Pipeline
    "1232383505": "New Qualified Opportunity", "1232383506": "Attempted to contact",
    "1232383507": "Engaged", "1232383508": "Meeting Booked",
    "1232383509": "To Reschedule", "1232383510": "Nurturing",
    "1232383511": "Opportunity Lost ",
    # XL Account Pipeline
    "1115587680": "Demo request from Prospect", "1003800944": "New",
    "1003800946": "Outreach", "1003800947": "Engaged",
    "4899425492": "Opportunity Lost", "1226596617": "Meeting Booked",
    "4899362020": "To Reschedule", "1003685894": "Discovery",
    "4897330392": "Sales Nurturing", "1003685895": "Product Alignment",
    "1003685896": "Pricing & Packaging", "1003685897": "Contracting",
    "1003800948": "Closed Pending Payment", "1003800949": "Closed Won",
    "1003800950": "Closed Lost",
    # XL SDR Pipeline
    "4899425498": "New", "4899425499": "Research & Outreach",
    "4899425500": "Connected - Not Engaged", "4899425501": "Engaged",
    "4899425502": "Meeting Booked", "4899425503": "To reschedule",
    "4899425504": "Hot Nurturing", "4899425505": "Long Nurturing",
    "4899425506": "Opportunity Lost",
    # IT AE Pipeline
    "1220339227": "Demo request from Prospect", "1220339228": "New",
    "1220339229": "Outreach", "1220339230": "Engaged",
    "5043758307": "Meeting Booked", "5043750115": "To Reschedule",
    "1220339231": "Discovery", "1220339232": "Product Alignment",
    "1220339233": "Pricing & Packaging", "1220382581": "Contracting",
    "1220382582": "Closed Pending Payment", "1220382583": "Closed Won",
    "1220382584": "Closed Lost", "5043748053": "Opportunity Lost",
    "5043748049": "Sales Nurturing",
    # IT SDR Pipeline
    "5467457780": "Demo Request from Prospect", "4969938161": "New",
    "4969938162": "Research & Outreach", "4969938163": "Connected - Not Engaged",
    "4969938164": "Engaged", "4969938165": "Meeting Booked",
    "4969938166": "To reschedule", "4969938167": "Hot Nurturing",
    "4969938168": "Long Nurturing", "4969938169": "Opportunity Lost",
    # Excluded pipelines (stages que existen en Upselling, Churn, Partner Acquisition)
    "12669405": "Closed Won - Finance Only",    # Upselling Pipeline
    "4965266651": "Contract negotiation (Ongoing) ",  # Churn Pipeline
    "14163265": "Meeting scheduled",            # Partner Acquisition
    "63255406": "Pricing and Packaging",        # Upselling Pipeline
    # Legacy (ya no existen en HubSpot pero deals viejos en Supabase los tienen)
    # "Economical Allignment Started" — typo corregido, sin ID
    # "FPA" — alias interno, sin ID en HubSpot
}

# --- Categorias funcionales (cada stage en UNA sola) ---

STAGE_PROSPECTING = frozenset({
    "New", "New Deals", "New Qualified Opportunity",
    "Research & Outreach", "Outreach", "Connected - Not Engaged",
    "Pre-qualified", "Attempting to contact", "Attempted to contact",
    "Associating the partner", "Engaged",
    "Demo request from Prospect", "Demo Request from Prospect",
})

STAGE_NURTURING = frozenset({
    "Nurturing", "Sales Nurturing", "Hot Nurturing", "Long Nurturing",
    "On Hold",
})

STAGE_DEMO = frozenset({
    "Demo Booked", "Meeting Booked", "Meeting scheduled","To reschedule", "To Reschedule",
})

STAGE_EVALUATION = frozenset({
    "Factorial Project Alignment started", "Product Alignment", "Discovery",
    "MEDDPICC Criteria Validation Started",
})

STAGE_CLOSING = frozenset({
    "Economical Alignment Started", "Economical Allignment Started",
    "Pricing and Packaging", "Pricing & Packaging",
    "Contract Sent", "Contracting",
    "Contract negotiation (Ongoing) ",
})

STAGE_WON = frozenset({
    "Closed Won", "Closed won", "Closed Won - Finance Only",
    "Closed Pending Payment", "Closed - pending finance validation",
})

STAGE_LOST = frozenset({
    "Closed Lost", "Closed lost",
    "Opportunity lost", "Opportunity Lost", "Opportunity Lost ",
})

# --- Sets compuestos (uniones de categorias) ---

# Todos los stages activos que procesamos en el CORE
ACTIVE_STAGES = STAGE_PROSPECTING | STAGE_NURTURING | STAGE_DEMO | STAGE_EVALUATION | STAGE_CLOSING

# Stages PBD (pre-demo + nurturing): donde generamos BANT snapshot
PBD_STAGES = STAGE_PROSPECTING | STAGE_DEMO | STAGE_NURTURING

# Stages post-demo donde el deal tiene traccion (para pipeline review, weekly reports)
ADVANCED_STAGES = STAGE_EVALUATION | STAGE_CLOSING

# Primera demo (para clasificar meetings y briefings)
FIRST_DEMO_STAGES = STAGE_DEMO | frozenset({"FPA"})

# Follow-up / evaluation (post-demo)
FOLLOWUP_STAGES = STAGE_EVALUATION

# Closing (pricing + contract)
CLOSING_STAGES = STAGE_CLOSING

# Closed (todas las variantes)
CLOSED_ALL = STAGE_WON | STAGE_LOST

# Won/Lost en lowercase (para comparacion case-insensitive)
CLOSED_WON_LOWER = frozenset(s.lower() for s in STAGE_WON)
CLOSED_LOST_LOWER = frozenset(s.lower() for s in STAGE_LOST)
CLOSED_ALL_LOWER = CLOSED_WON_LOWER | CLOSED_LOST_LOWER

# Stalled (para followup classifier)
STALLED_STAGES_LOWER = frozenset({"on hold", "to reschedule"})

# Followup inactive: deals que el followup classifier trata como "ya no activos"
# Es CLOSED + NURTURING (deals cerrados o en nurturing no necesitan followup)
FOLLOWUP_INACTIVE_LOWER = CLOSED_ALL_LOWER | frozenset(s.lower() for s in STAGE_NURTURING)

# Stages de pipelines excluidos (onboarding, churn, etc. — lowercase para comparacion)
ONBOARDING_STAGES_LOWER = frozenset({
    "onboarding completed - converted", "onboarding completed - pending conversion",
    "onboarding failed", "onboarding on hold",
})
CHURN_STAGES_LOWER = frozenset({
    "churned (closed)", "retained (closed)", "preventive churn risk (new)",
    "requested churn (new)", "(do not use) churn confirmed",
})
MISC_EXCLUDE_STAGES_LOWER = frozenset({
    "product related process (ongoing)", "pending approval because low joined rate",
    "wrongly created ticket (closed)", "spam",
    "(do not use) pending post-mortem analysis", "(do not use) action plan",
    "> 75% sessions done", "51-75% sessions done", "26-50% sessions done",
    "≤ 25% sessions done", "1st session scheduled", "client pending to launch",
})

# Stages a excluir en sync_deals (no son venta nueva activa)
STAGES_EXCLUDE_FROM_SYNC_LOWER = (
    CLOSED_ALL_LOWER | ONBOARDING_STAGES_LOWER | CHURN_STAGES_LOWER | MISC_EXCLUDE_STAGES_LOWER
)

# Equipos con demo evaluation activa (audit de calidad de la primera demo)
DEMO_EVAL_ACTIVE_TEAMS = {"Santander", "Telefonica", "TIM", "TELEKOM"}

# No-show (deal sale de Demo Booked a estos)
NO_SHOW_STAGES = frozenset({"To reschedule", "To Reschedule", "On Hold", "Nurturing"})

# Stage display: label (HubSpot original), short (nombre limpio), abbr (badge compacto)
# Keyed by stage label (que es lo que usamos en el codigo).
# Stages con mismo display pero diferente label en HubSpot comparten short/abbr.
STAGE_DISPLAY: dict[str, dict[str, str]] = {
    # PROSPECTING
    "New":                              {"short": "New",                "abbr": "NEW"},
    "New Deals":                        {"short": "New Deals",         "abbr": "ND"},
    "New Qualified Opportunity":        {"short": "New Qualified",     "abbr": "NQ"},
    "Research & Outreach":              {"short": "Research",          "abbr": "R&O"},
    "Outreach":                         {"short": "Outreach",          "abbr": "OUT"},
    "Pre-qualified":                    {"short": "Pre-qualified",     "abbr": "PQ"},
    "Attempting to contact":            {"short": "Attempting",        "abbr": "ATC"},
    "Attempted to contact":             {"short": "Attempted",         "abbr": "ATC"},
    "Associating the partner":          {"short": "Assoc. Partner",    "abbr": "AP"},
    "Connected - Not Engaged":          {"short": "Connected",         "abbr": "CNE"},
    "Engaged":                          {"short": "Engaged",           "abbr": "ENG"},
    "Demo request from Prospect":       {"short": "Demo Request",      "abbr": "DRP"},
    "Demo Request from Prospect":       {"short": "Demo Request",      "abbr": "DRP"},
    "Opportunity detected":             {"short": "Opp. Detected",     "abbr": "OD"},
    "Client Contacted":                 {"short": "Contacted",         "abbr": "CC"},
    # NURTURING
    "Nurturing":                        {"short": "Nurturing",         "abbr": "NUR"},
    "Sales Nurturing":                  {"short": "Sales Nurturing",   "abbr": "SN"},
    "Hot Nurturing":                    {"short": "Hot Nurturing",     "abbr": "HN"},
    "Long Nurturing":                   {"short": "Long Nurturing",    "abbr": "LN"},
    "On Hold":                          {"short": "On Hold",           "abbr": "OH"},
    "To reschedule":                    {"short": "To Reschedule",     "abbr": "TR"},
    "To Reschedule":                    {"short": "To Reschedule",     "abbr": "TR"},
    # DEMO
    "Demo Booked":                      {"short": "Demo Booked",       "abbr": "DB"},
    "Meeting Booked":                   {"short": "Meeting Booked",    "abbr": "MB"},
    "Meeting scheduled":                {"short": "Meeting Scheduled", "abbr": "MS"},
    # EVALUATION
    "Factorial Project Alignment started": {"short": "Product Alignment", "abbr": "FPA"},
    "Product Alignment":                {"short": "Product Alignment", "abbr": "PA"},
    "Discovery":                        {"short": "Discovery",         "abbr": "DIS"},
    "MEDDPICC Criteria Validation Started": {"short": "MEDDPICC",      "abbr": "MCV"},
    # CLOSING
    "Economical Allignment Started":    {"short": "Econ. Alignment",   "abbr": "EA"},
    "Economical Alignment Started":     {"short": "Econ. Alignment",   "abbr": "EA"},
    "Pricing and Packaging":            {"short": "Pricing",           "abbr": "P&P"},
    "Pricing & Packaging":              {"short": "Pricing",           "abbr": "P&P"},
    "Contract Sent":                    {"short": "Contract Sent",     "abbr": "CS"},
    "Contracting":                      {"short": "Contracting",       "abbr": "CTR"},
    "Contract negotiation (Ongoing) ":  {"short": "Contract Negot.",   "abbr": "CN"},
    # WON
    "Closed Won":                       {"short": "Won",               "abbr": "WON"},
    "Closed won":                       {"short": "Won",               "abbr": "WON"},
    "Closed Won - Finance Only":        {"short": "Won (Finance)",     "abbr": "WON"},
    "Closed Pending Payment":           {"short": "Pending Payment",   "abbr": "PP"},
    "Closed - pending finance validation": {"short": "Pending Valid.", "abbr": "PFV"},
    # LOST
    "Closed Lost":                      {"short": "Lost",              "abbr": "LOST"},
    "Closed lost":                      {"short": "Lost",              "abbr": "LOST"},
    "Opportunity lost":                 {"short": "Lost",              "abbr": "LOST"},
    "Opportunity Lost":                 {"short": "Lost",              "abbr": "LOST"},
    "Opportunity Lost ":                {"short": "Lost",              "abbr": "LOST"},
}

# Categoria → briefing prompt key (que prompt cargar para preparar una reunion)
STAGE_CATEGORY_BRIEFING = {
    "demo": "pae_brief_first_demo_multisector",
    "evaluation": "pae_brief_followup_meddic_multisector",
    "closing": "pae_brief_pricing_closing_multisector",
}


# ============================================================================
# 7. MODJO TAGS — clasificacion de calls
#
# Tags que Modjo pone en las calls grabadas.
# Agrupadas por categoria para filtros, UI, y routing de audit.
# TAG_TO_PROMPT mapea cada tag al prompt que usa el audit actual.
# Cuando tengamos el mega-prompt universal, TAG_TO_PROMPT desaparece
# y el agente decide solo basandose en el transcript + tag como pista.
# ============================================================================

# --- Todas las tags por categoria ---

TAGS_PARTNERS_PBD = {
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

TAGS_PARTNERS_PAE = {
    "Partners - PAE Demo",
    "Partners - PAE Follow Up",
    "Partners - PAE Follow Up Meeting",
    "Partners - PAE Closing Call",
    "Partners - PAE Closing Meeting",
    "Partners - PAE Other",
}

TAGS_DIRECT_SALES = {
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

TAGS_PARTNER_MGMT = {
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

TAGS_SKIP = {
    "OB - Onboarding", "OB - Discovery", "OB - Final Call", "OB - Risk of Churn",
    "CX - AM Upsell Follow up", "CX - AM Discovery", "CX - AM Demo",
    "CX - Payroll Consultancy", "CX - AM Regular Meeting",
    "CX - AM Engagement Call", "CX - AM QBR", "CX - Handover",
    "INTERNAL - Meeting/Training",
    "PRODUCT - DOCUMENTS - Distribution",
    "Platform - CIAM - Security Settings",
}

TAGS_METADATA = {"Possible Rejected"}

# Sets derivados
ALL_AUDIT_TAGS = TAGS_PARTNERS_PBD | TAGS_PARTNERS_PAE | TAGS_DIRECT_SALES
ALL_KNOWN_TAGS = ALL_AUDIT_TAGS | TAGS_PARTNER_MGMT | TAGS_SKIP | TAGS_METADATA
PBD_TAGS = TAGS_PARTNERS_PBD
PAE_TAGS = TAGS_PARTNERS_PAE

HANDOVER_TRIGGER_TAG = "91. Partners - PBD Demo Scheduled"

# --- Multi-tag: reglas de resolucion ---
#
# Cuando una call tiene 2+ tags:
# 1. Dedup aliases (misma tag con nombre diferente)
# 2. Eliminar TAGS_METADATA (Possible Rejected es info, no tipo de call)
# 3. Si queda tag 91 (Demo Scheduled) → siempre gana
# 4. Prioridad: PAE > PBD > DS > Partner Mgmt

TAG_ALIASES = {
    "Partners - PBD Demo Scheduled Call": "91. Partners - PBD Demo Scheduled",
    "Partners - PBD Partner Call": "991. Partners - PBD Partner Call",
}

TAG_CATEGORY_PRIORITY = ["partners_pae", "partners_pbd", "direct_sales", "partner_mgmt"]

# --- Sin tag: como inferir ---
#
# 29% de calls Modjo no tienen tag (3,276 calls con transcript).
# Estrategia:
#   1. Si tiene deal_id → usar get_stage_category(deal_stage) para inferir tipo
#   2. Si tiene rol (PBD/PAE) pero no deal → audit con prompt untagged.txt
#      (el prompt ya clasifica solo: prospect call / partner coordination / other)
#   3. Si no tiene rol ni deal → audit generico con untagged.txt
NO_TAG_STRATEGY = "infer_from_context"

# --- Tag → prompt file (sistema actual) ---
#
# Cada tag apunta al prompt que usa el audit.
# DS tags reusan prompts de Partners (misma mecanica de call).
# Tags sin prompt usan untagged.txt (el agente infiere solo).
# Se eliminara cuando tengamos el mega-prompt universal.

TAG_TO_PROMPT: dict[str, str] = {
    # Partners PBD
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
    # Partners PAE
    "Partners - PAE Demo": "pae/demo.txt",
    "Partners - PAE Follow Up": "pae/follow_up.txt",
    "Partners - PAE Follow Up Meeting": "pae/follow_up.txt",
    "Partners - PAE Closing Call": "pae/closing.txt",
    "Partners - PAE Closing Meeting": "pae/closing.txt",
    "Partners - PAE Other": None,  # → untagged.txt
    # Direct Sales SDR (reusan prompts PBD — misma mecanica)
    "1. SDR - Demo Scheduled Call": "pbd/91.txt",
    "2. SDR - Positive Champion Call Connected": "pbd/92.txt",
    "3. SDR - Negative Champion Call Connected": "pbd/94.txt",
    "4. SDR - Gatekeeper Call Connected": "pbd/93.txt",
    "7. SDR - No Answer": "pbd/97.txt",
    # Direct Sales AE (reusan prompts PAE)
    "AE - Discovery Meeting": "pae/demo.txt",
    "AE - Follow Up": "pae/follow_up.txt",
    "AE - Closing Call": "pae/closing.txt",
    "Follow up Meeting": "pae/follow_up.txt",
    # Partner management → untagged (el agente infiere)
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

# Tag → audit level (full = BANT/MEDDIC completo, light = resumen rapido)
TAG_AUDIT_LEVEL: dict[str, str] = {
    # Partners PBD
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
    # Partners PAE
    "Partners - PAE Demo": "full_pae",
    "Partners - PAE Follow Up": "full_pae",
    "Partners - PAE Follow Up Meeting": "full_pae",
    "Partners - PAE Closing Call": "full_pae",
    "Partners - PAE Closing Meeting": "full_pae",
    "Partners - PAE Other": "light",
    # Direct Sales SDR
    "1. SDR - Demo Scheduled Call": "full_pbd",
    "2. SDR - Positive Champion Call Connected": "full_pbd",
    "3. SDR - Negative Champion Call Connected": "full_pbd",
    "4. SDR - Gatekeeper Call Connected": "light",
    "7. SDR - No Answer": "light",
    # Direct Sales AE
    "AE - Discovery Meeting": "full_pae",
    "AE - Follow Up": "full_pae",
    "AE - Closing Call": "full_pae",
    "Follow up Meeting": "full_pae",
}

LEVEL_PRIORITY = {"full_pae": 1, "full_pbd": 2, "light": 3, "light_pae": 3}


# ============================================================================
# 8. SLACK
#
# Channels por email (no por nombre — los nombres cambian, los emails no).
# Solo personas con channel asignado reciben notificaciones.
# Si no tiene channel → no se le notifica (no aparece en SLACK_ACTIVE).
# Para añadir: buscar channel ID en Slack y añadir aquí.
# ============================================================================

FALLBACK_SLACK_CHANNEL = "C0ATY3V8CN4"

# Channels por equipo (TL reports)
SLACK_TEAM_CHANNELS = {
    "Santander":  {"tl_channel": "C0B36RD537X"},
    "Telefonica": {"tl_channel": "C0B33QJLF8B"},
    "TIM":        {"tl_channel": "C0B9QCWDCQ4"},
    "TELEKOM":    {"tl_channel": "C0B9QCWDCQ4"},
    # DS y XL: añadir cuando se creen los canales
}


# Channels individuales por email (para demo prep, followup, alerts)
# Solo personas con channel aquí reciben notificaciones individuales.
SLACK_CHANNELS: dict[str, str] = {
    # --- Directors ---
    "joan.balana@factorial.co": "C0B36RD537X",         # Partner Sales Director ES
    # "antoni.grau@factorial.co": "",                   # Sales Director DS España
    # "ariadna.isla@factorial.co": "",                  # XL Country Manager IBERIA
    # "andrea.galimberti@factorial.co": "",             # Director Partnerships Italy
    # "laura.proefrock@factorial.co": "",               # Partnerships Director DACH

    # --- TLs Partners ---
    "roberto.moran@factorial.co": "C0B36RD537X",       # TL PAE Santander
    "carlos.sanchez@factorial.co": "C0B33QJLF8B",      # TL PAE Telefonica
    # "nunzio.fumo@factorial.co": "",                   # TL PAE TIM
    # "gabriel.lichtenstein@factorial.co": "",           # TL PAE TELEKOM

    # --- TLs Direct Sales ---
    # "mireia.bach@factorial.co": "",                   # TL DS Mireia
    # "tania.diaz@factorial.co": "",                    # TL DS Tania
    # "l.rodriguez@factorial.co": "",                   # TL DS Luis
    # "pilar.elizaga@factorial.co": "",                 # TL DS Pilar
    # "caterina.peraire@factorial.co": "",              # TL DS Caterina
    # "ruben.mariscal@factorial.co": "",                # Sub-TL DS Rubén
    # "andrea.castanar@factorial.co": "",               # Sub-TL DS Andrea C

    # --- PAEs Santander ---
    "xavier.fortuny@factorial.co": "C0B1CNJTPMZ",
    "jose.donis@factorial.co": "C0B24A51PNE",
    "pol.bartolome@factorial.co": "C0B33Q2T7FV",
    "beatriz.bravo@factorial.co": "C0B8BKTS1CL",
    "joan.lorenzo@factorial.co": "C0B2UMVT5NK",
    "eduardo.zafra@factorial.co": "",                   # TODO: buscar channel

    # --- PAEs Telefonica ---
    "david.clemente@factorial.co": "C0B33QDE4KD",
    "nerea.urien@factorial.co": "C0B2UMRUV2T",
    "alejandro.soto@factorial.co": "C0B36Q1EX9T",

    # --- PAEs TIM ---
    # "emilio.fabbro@factorial.co": "",
    # "marco.falaschetti@factorial.co": "",
    # "giovanni.laghi@factorial.co": "",
    # "edoardo.rapezzi@factorial.co": "",
    # "christian.lombardo@factorial.co": "",
    # "giuditta.giunta@factorial.co": "",

    # --- PAEs TELEKOM ---
    # "leonhard.zeus@factorial.co": "",
    # "katrin.virtbauer@factorial.co": "",
    # "stefan.platt@factorial.co": "",
    # "enrique.gautier@factorial.co": "",
    # "jonas.tretter@factorial.co": "",
}

# Personas con channel activo (reciben notificaciones)
SLACK_ACTIVE = {email for email, ch in SLACK_CHANNELS.items() if ch}


# ============================================================================
# 8. EB ALERTS
#
# Se dispara cuando un deal entra en el trigger_stage.
# Claude clasifica si el Economic Buyer está identificado/involucrado.
# El resultado se envia al channel del equipo definido aqui.
# ============================================================================

EB_ALERTS = {
    # Se dispara UNA vez cuando el deal entra en este stage
    "trigger_stage": "Economical Alignment Started",

    # Canal Slack del TL por equipo. Si un equipo no esta aqui, no recibe alert.
    # Para activar un equipo nuevo: anadir entry con su channel ID.
    "channels": {
        "Santander": "C0B1VPPG1F1",
        "Telefonica": "C0B1VPPG1F1",
        "TIM": "C0BA1MU9S1J",
        "TELEKOM": "C0B9QCWDCQ4",
    },
    "fallback_channel": "C0ATY3V8CN4",

    # Emoji por equipo (para Slack messages)
    "emoji": {
        "Santander": ":Santander:",
        "Telefonica": ":telefonica:",
        "TIM": ":tim:",
        "TELEKOM": ":telekom:",
    },

    # Claude clasifica el EB status → color + header para Slack
    "classifications": {
        "IDENTIFIED_INVOLVED": {
            "color": "#2eb886",
            "header": "Deal sent to P&P with EB IDENTIFIED & INVOLVED",
        },
        "IDENTIFIED_NOT_INVOLVED": {
            "color": "#daa038",
            "header": "Deal sent to P&P with EB IDENTIFIED BUT NOT INVOLVED",
        },
        "NOT_IDENTIFIED": {
            "color": "#e01e5a",
            "header": "Deal sent to P&P with EB NOT IDENTIFIED",
        },
    },
}

# Equipos que reciben EB alerts (los que tienen channel definido)
EB_ALERT_ACTIVE_TEAMS = set(EB_ALERTS["channels"].keys())


# ============================================================================
# 9. HUBSPOT PROPERTIES
#
# Lista maestra de TODAS las properties que pedimos a HubSpot en sync_deals.
# Cada property tiene 3 valores:
#   - label: nombre visible en HubSpot
#   - column: nombre de la columna en Supabase
# La key del dict es el internal name de HubSpot (lo que usa la API).
# Columnas marcadas "NOT IN SUPA" se crearan en la migracion.
# ============================================================================

HS_DEAL_PROPS = {
    # --- Deal info ---
    "hs_object_id":                          {"label": "Record ID",                      "column": "deal_id"},
    "dealname":                              {"label": "Deal Name",                      "column": "deal_name"},
    "amount":                                {"label": "Amount",                         "column": "amount"},
    "dealstage":                             {"label": "Deal Stage",                     "column": "deal_stage"},
    "pipeline":                              {"label": "Pipeline",                       "column": "pipeline_name"},
    "closedate":                             {"label": "Close Date",                     "column": "close_date"},
    "createdate":                            {"label": "Create Date",                    "column": "createdate"},
    "hs_lastmodifieddate":                   {"label": "Last Modified Date",             "column": "last_hs_modified"},
    # --- Owner / team ---
    # hubspot_owner_id y created_by son IDs numericos. Se guardan como ID + se resuelven
    # a nombre via HUBSPOT_OWNER_IDS (dict lookup en memoria, coste 0).
    # pae/pbd son las columnas con el nombre resuelto (ya existen en Supabase).
    "hubspot_owner_id":                      {"label": "Deal owner",                     "column": "hs_owner_id"},             # NOT IN SUPA — ID del PAE/AE actual
    "created_by":                            {"label": "Deal created by",                "column": "hs_created_by"},           # NOT IN SUPA — ID del PBD creador
    # → pae (text, ya en Supa) = nombre resuelto desde hubspot_owner_id
    # → pbd (text, ya en Supa) = nombre resuelto desde created_by
    "hs_all_owner_ids":                      {"label": "All owner IDs",                  "column": "hs_all_owner_ids"},        # NOT IN SUPA
    "current_hubspot_team__string_":         {"label": "Current Hubspot team (string)",  "column": "hs_team_string"},          # NOT IN SUPA
    "hubspot_team_id":                          {"label": "HubSpot team",                   "column": "hs_team_id"},          # NOT IN SUPA
    # --- Provenance ---
    "partner_name":                          {"label": "Partner name",                   "column": "partner_name"},            # NOT IN SUPA
    "marketing_lead_form_campaign_on_deal":  {"label": "Marketing_lead_form_campaign_on_deal", "column": "hs_campaign"},        # NOT IN SUPA
    "hs_analytics_source":                   {"label": "Original Traffic Source",         "column": "hs_source"},               # NOT IN SUPA
    # --- Forecast ---
    "hs_manual_forecast_category":           {"label": "Forecast category",              "column": "forecast_category"},
    "hs_forecast_probability":               {"label": "Forecast probability",           "column": "rep_probability"},
    "hs_deal_stage_probability":             {"label": "Deal probability",               "column": "stage_probability_hs"},
    # --- Activity ---
    "notes_last_contacted":                  {"label": "Last Contacted",                 "column": "last_contacted_hs"},
    "notes_last_updated":                    {"label": "Last Activity Date",             "column": "last_activity_hs"},        # NOT IN SUPA
    "num_associated_contacts":               {"label": "Number of Associated Contacts",  "column": "contact_count"},
    "num_contacted_notes":                   {"label": "Number of times contacted",      "column": "num_times_contacted"},     # NOT IN SUPA
    "num_notes":                             {"label": "Number of Sales Activities",     "column": "num_sales_activities"},    # NOT IN SUPA
    "hs_next_step":                          {"label": "Next step",                      "column": "rep_next_step"},
    "hs_latest_meeting_activity":            {"label": "Latest meeting activity",        "column": "last_meeting_hs"},         # NOT IN SUPA
    # --- Meetings ---
    "first_meeting_at":                      {"label": "First meeting at",               "column": "first_meeting_at"},
    "hs_next_meeting_start_time":            {"label": "Next Meeting Start Time",        "column": "hs_next_meeting_start_time"},
    # --- Close status ---
    "closed_lost_reason":                    {"label": "Primary Closed Lost Reason",     "column": "closed_lost_reason"},
    "hs_is_closed_won":                      {"label": "Is Closed Won",                  "column": "is_closed_won"},           # NOT IN SUPA
    "hs_is_closed":                          {"label": "Is Deal Closed?",                "column": "is_closed"},               # NOT IN SUPA
    "closed_lost_stage_date":                {"label": "Closed lost stage date",         "column": "closed_lost_date"},        # NOT IN SUPA
    "sqo_date":                              {"label": "SQO date partners",              "column": "sqo_date"},                # NOT IN SUPA
    # --- Company size ---
    "revised_number_of_emloyeess":           {"label": "Revised number of employees",    "column": "num_employees"},           # NOT IN SUPA
    "numero_de_empleados":                   {"label": "Número de Empleados",            "column": "num_employees_custom"},    # NOT IN SUPA
    # --- Champion ---
    "champion_name":                         {"label": "Champion name",                  "column": "champion"},                # NOT IN SUPA
}

# --- Properties de meetings asociados al deal → tabla deal_meetings ---
# Ademas de estas properties, el pipeline tambien escribe:
#   deal_id (uuid)       — resuelto: UUID del deal en Supabase
#   hs_deal_id (text)    — HubSpot deal ID
#   hs_meeting_id (text) — HubSpot meeting ID (upsert key, on_conflict)
HS_MEETING_PROPS_SYNC = {
    "hs_meeting_start_time":  {"label": "Meeting start time",     "column": "meeting_start"},
    "hs_meeting_end_time":    {"label": "Meeting end time",       "column": "meeting_end"},
    "hs_meeting_title":       {"label": "Meeting name",           "column": "title"},
    "hs_meeting_outcome":     {"label": "Meeting outcome",        "column": "outcome"},
}

# --- Properties de objetos asociados al deal (para context builder) ---
# No van a tabla — se usan en memoria para construir deal_context (texto).
# column = None porque no se guardan directamente.

HS_EMAIL_PROPS = {
    "hs_timestamp":           {"label": "Activity date",          "column": None},
    "hs_createdate":          {"label": "HubSpot Create Date",    "column": None},
    "hs_email_direction":     {"label": "Email Direction",        "column": None},
    "hs_email_from_email":    {"label": "Email From Address",     "column": None},
    "hs_email_subject":       {"label": "Email subject",          "column": None},
    "hs_email_text":          {"label": "Text",                   "column": None},
    "hs_email_html":          {"label": "Email body",             "column": None},
}

HS_NOTE_PROPS = {
    "hs_timestamp":           {"label": "Activity date",          "column": None},
    "hs_createdate":          {"label": "HubSpot Create Date",    "column": None},
    "hs_note_body":           {"label": "Note body",              "column": None},
    "hubspot_owner_id":       {"label": "Deal owner",             "column": None},
}

HS_CALL_PROPS = {
    "hs_timestamp":           {"label": "Activity date",          "column": None},
    "hs_call_body":           {"label": "Call notes",             "column": None},
    "hs_call_duration":       {"label": "Call duration",          "column": None},
    "hs_call_title":          {"label": "Call Title",             "column": None},
    "hubspot_owner_id":       {"label": "Deal owner",             "column": None},
}

HS_MEETING_PROPS = {
    "hs_timestamp":               {"label": "Activity date",              "column": None},
    "hs_meeting_title":           {"label": "Meeting name",               "column": None},
    "hs_meeting_body":            {"label": "Meeting description",        "column": None},
    "hs_internal_meeting_notes":  {"label": "Internal Meeting Notes",     "column": None},
    "hs_meeting_start_time":      {"label": "Meeting start time",         "column": None},
    "hs_meeting_end_time":        {"label": "Meeting end time",           "column": None},
    "hs_meeting_outcome":         {"label": "Meeting outcome",            "column": None},
    "hubspot_owner_id":           {"label": "Deal owner",                 "column": None},
    "hs_attendee_owner_ids":      {"label": "HubSpot attendee owner IDs", "column": None},
}

# --- Stage date properties ---
# hs_v2_date_entered/exited_{stage_id} → supabase column
# Cada pipeline tiene sus propios stage IDs. Solo se rellena para deals de ese pipeline.

HS_PIPELINE_DATE_MAP = {
    # SDR Partner Opportunities Pipeline (id=684767384)
    "hs_v2_date_entered_1002830265": {"label": 'Date entered "Pre-qualified (SDR Partner Opportunities Pipeline)"', "column": "sdr_prequalified_entered"},
    "hs_v2_date_exited_1002830265": {"label": 'Date exited "Pre-qualified (SDR Partner Opportunities Pipeline)"', "column": "sdr_prequalified_exited"},
    "hs_v2_date_entered_1002830336": {"label": 'Date entered "Attempting to contact (SDR Partner Opportunities Pipeline)"', "column": "sdr_attempting_to_contact_entered"},
    "hs_v2_date_exited_1002830336": {"label": 'Date exited "Attempting to contact (SDR Partner Opportunities Pipeline)"', "column": "sdr_attempting_to_contact_exited"},
    "hs_v2_date_entered_1002830337": {"label": 'Date entered "Associating the partner (SDR Partner Opportunities Pipeline)"', "column": "sdr_associating_the_partner_entered"},
    "hs_v2_date_exited_1002830337": {"label": 'Date exited "Associating the partner (SDR Partner Opportunities Pipeline)"', "column": "sdr_associating_the_partner_exited"},
    "hs_v2_date_entered_1002830338": {"label": 'Date entered "Engaged (SDR Partner Opportunities Pipeline)"', "column": "sdr_engaged_entered"},
    "hs_v2_date_exited_1002830338": {"label": 'Date exited "Engaged (SDR Partner Opportunities Pipeline)"', "column": "sdr_engaged_exited"},
    "hs_v2_date_entered_1002830339": {"label": 'Date entered "Demo Booked (SDR Partner Opportunities Pipeline)"', "column": "sdr_demo_booked_entered"},
    "hs_v2_date_exited_1002830339": {"label": 'Date exited "Demo Booked (SDR Partner Opportunities Pipeline)"', "column": "sdr_demo_booked_exited"},
    "hs_v2_date_entered_1002830340": {"label": 'Date entered "Nurturing (SDR Partner Opportunities Pipeline)"', "column": "sdr_nurturing_entered"},
    "hs_v2_date_exited_1002830340": {"label": 'Date exited "Nurturing (SDR Partner Opportunities Pipeline)"', "column": "sdr_nurturing_exited"},
    "hs_v2_date_entered_1002830341": {"label": 'Date entered "Opportunity lost (SDR Partner Opportunities Pipeline)"', "column": "sdr_opportunity_lost_entered"},
    "hs_v2_date_exited_1002830341": {"label": 'Date exited "Opportunity lost (SDR Partner Opportunities Pipeline)"', "column": "sdr_opportunity_lost_exited"},
    "hs_v2_date_entered_1002829480": {"label": 'Date entered "To reschedule (SDR Partner Opportunities Pipeline)"', "column": "sdr_to_reschedule_entered"},
    "hs_v2_date_exited_1002829480": {"label": 'Date exited "To reschedule (SDR Partner Opportunities Pipeline)"', "column": "sdr_to_reschedule_exited"},
    # Partners Distribution Pipeline (id=11834984)
    "hs_v2_date_entered_35070729": {"label": 'Date entered "New Deals (Partners Distribution)"', "column": "dist_new_deals_entered"},
    "hs_v2_date_exited_35070729": {"label": 'Date exited "New Deals (Partners Distribution)"', "column": "dist_new_deals_exited"},
    "hs_v2_date_entered_35070730": {"label": 'Date entered "Demo Booked (Partners Distribution)"', "column": "dist_demo_booked_entered"},
    "hs_v2_date_exited_35070730": {"label": 'Date exited "Demo Booked (Partners Distribution)"', "column": "dist_demo_booked_exited"},
    "hs_v2_date_entered_35070731": {"label": 'Date entered "Factorial Project Alignment started (Partners Distribution)"', "column": "dist_product_alignment_entered"},
    "hs_v2_date_exited_35070731": {"label": 'Date exited "Factorial Project Alignment started (Partners Distribution)"', "column": "dist_product_alignment_exited"},
    "hs_v2_date_entered_35070732": {"label": '? — Entered', "column": "dist_do_not_use_entered"},
    "hs_v2_date_exited_35070732": {"label": '? — Exited', "column": "dist_do_not_use_exited"},
    "hs_v2_date_entered_35118878": {"label": 'Date entered "Economical Alignment Started (Partners Distribution)"', "column": "dist_pricing_and_packaging_entered"},
    "hs_v2_date_exited_35118878": {"label": 'Date exited "Economical Alignment Started (Partners Distribution)"', "column": "dist_pricing_and_packaging_exited"},
    "hs_v2_date_entered_35118879": {"label": 'Date entered "Contract Sent (Partners Distribution)"', "column": "dist_contracting_entered"},
    "hs_v2_date_exited_35118879": {"label": 'Date exited "Contract Sent (Partners Distribution)"', "column": "dist_contracting_exited"},
    "hs_v2_date_entered_104503991": {"label": 'Date entered "Closed - pending finance validation (Partners Distribution)"', "column": "dist_closed_pending_payment_entered"},
    "hs_v2_date_exited_104503991": {"label": 'Date exited "Closed - pending finance validation (Partners Distribution)"', "column": "dist_closed_pending_payment_exited"},
    "hs_v2_date_entered_35118880": {"label": 'Date entered "Closed Won (Partners Distribution)"', "column": "dist_closed_won_entered"},
    "hs_v2_date_exited_35118880": {"label": 'Date exited "Closed Won (Partners Distribution)"', "column": "dist_closed_won_exited"},
    "hs_v2_date_entered_1008401982": {"label": 'Date entered "On Hold (Partners Distribution)"', "column": "dist_on_hold_entered"},
    "hs_v2_date_exited_1008401982": {"label": 'Date exited "On Hold (Partners Distribution)"', "column": "dist_on_hold_exited"},
    "hs_v2_date_entered_35119283": {"label": 'Date entered "Closed Lost (Partners Distribution)"', "column": "dist_closed_lost_entered"},
    "hs_v2_date_exited_35119283": {"label": 'Date exited "Closed Lost (Partners Distribution)"', "column": "dist_closed_lost_exited"},
    "hs_v2_date_entered_4977567965": {"label": 'Date entered "To reschedule (Partners Distribution)"', "column": "dist_to_reschedule_entered"},
    "hs_v2_date_exited_4977567965": {"label": 'Date exited "To reschedule (Partners Distribution)"', "column": "dist_to_reschedule_exited"},
    "hs_v2_date_entered_5366023400": {"label": 'Date entered "MEDDPICC Criteria Validation Started (Partners Distribution)"', "column": "dist_meddpicc_validation_entered"},
    "hs_v2_date_exited_5366023400": {"label": 'Date exited "MEDDPICC Criteria Validation Started (Partners Distribution)"', "column": "dist_meddpicc_validation_exited"},
    # Sales Pipeline (id=default)
    "hs_v2_date_entered_96e820da_7bc1_4ea3_81a2_bc533ed26934_2127198906": {"label": 'Date entered "Meeting Booked (Sales Pipeline)"', "column": "sales_meeting_booked_entered"},
    "hs_v2_date_exited_96e820da_7bc1_4ea3_81a2_bc533ed26934_2127198906": {"label": 'Date exited "Meeting Booked (Sales Pipeline)"', "column": "sales_meeting_booked_exited"},
    "hs_v2_date_entered_49b7ad85_a23e_426c_9b3b_d44607d1c3af_2009251351": {"label": 'Date entered "Discovery (Sales Pipeline)"', "column": "sales_discovery_entered"},
    "hs_v2_date_exited_49b7ad85_a23e_426c_9b3b_d44607d1c3af_2009251351": {"label": 'Date exited "Discovery (Sales Pipeline)"', "column": "sales_discovery_exited"},
    "hs_v2_date_entered_f26b487d_e715_49c8_add3_9fa86aef79da_127692047": {"label": 'Date entered "To reschedule (Sales Pipeline)"', "column": "sales_to_reschedule_entered"},
    "hs_v2_date_exited_f26b487d_e715_49c8_add3_9fa86aef79da_127692047": {"label": 'Date exited "To reschedule (Sales Pipeline)"', "column": "sales_to_reschedule_exited"},
    "hs_v2_date_entered_appointmentscheduled": {"label": 'Date entered "Product Alignment (Sales Pipeline)"', "column": "sales_product_alignment_entered"},
    "hs_v2_date_exited_appointmentscheduled": {"label": 'Date exited "Product Alignment (Sales Pipeline)"', "column": "sales_product_alignment_exited"},
    "hs_v2_date_entered_qualifiedtobuy": {"label": 'Date entered "Pricing & Packaging (Sales Pipeline)"', "column": "sales_pricing_and_packaging_entered"},
    "hs_v2_date_exited_qualifiedtobuy": {"label": 'Date exited "Pricing & Packaging (Sales Pipeline)"', "column": "sales_pricing_and_packaging_exited"},
    "hs_v2_date_entered_15738025": {"label": 'Date entered "Contracting (Sales Pipeline)"', "column": "sales_contracting_entered"},
    "hs_v2_date_exited_15738025": {"label": 'Date exited "Contracting (Sales Pipeline)"', "column": "sales_contracting_exited"},
    "hs_v2_date_entered_51389338": {"label": 'Date entered "Closed - pending finance validation (Sales Pipeline)"', "column": "sales_closed_pending_payment_entered"},
    "hs_v2_date_exited_51389338": {"label": 'Date exited "Closed - pending finance validation (Sales Pipeline)"', "column": "sales_closed_pending_payment_exited"},
    "hs_v2_date_entered_closedwon": {"label": 'Date entered "Closed won (Sales Pipeline)"', "column": "sales_closed_won_entered"},
    "hs_v2_date_exited_closedwon": {"label": 'Date exited "Closed won (Sales Pipeline)"', "column": "sales_closed_won_exited"},
    "hs_v2_date_entered_closedlost": {"label": 'Date entered "Closed lost (Sales Pipeline)"', "column": "sales_closed_lost_entered"},
    "hs_v2_date_exited_closedlost": {"label": 'Date exited "Closed lost (Sales Pipeline)"', "column": "sales_closed_lost_exited"},
    # OB SDR Pipeline (id=9048177)
    "hs_v2_date_entered_25761461": {"label": 'Date entered "New (OB SDR Pipeline)"', "column": "ob_new_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_25761461": {"label": 'Date exited "New (OB SDR Pipeline)"', "column": "ob_new_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_25761462": {"label": 'Date entered "Research & Outreach (OB SDR Pipeline)"', "column": "ob_research_outreach_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_25761462": {"label": 'Date exited "Research & Outreach (OB SDR Pipeline)"', "column": "ob_research_outreach_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_25761463": {"label": 'Date entered "Connected - Not Engaged (OB SDR Pipeline)"', "column": "ob_connected_not_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_25761463": {"label": 'Date exited "Connected - Not Engaged (OB SDR Pipeline)"', "column": "ob_connected_not_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_26471690": {"label": 'Date entered "Engaged (OB SDR Pipeline)"', "column": "ob_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_26471690": {"label": 'Date exited "Engaged (OB SDR Pipeline)"', "column": "ob_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_25761464": {"label": 'Date entered "Meeting Booked (OB SDR Pipeline)"', "column": "ob_meeting_booked_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_25761464": {"label": 'Date exited "Meeting Booked (OB SDR Pipeline)"', "column": "ob_meeting_booked_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_25761536": {"label": 'Date entered "To Reschedule (OB SDR Pipeline)"', "column": "ob_to_reschedule_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_25761536": {"label": 'Date exited "To Reschedule (OB SDR Pipeline)"', "column": "ob_to_reschedule_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_27564328": {"label": 'Date entered "Hot Nurturing (OB SDR Pipeline)"', "column": "ob_hot_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_27564328": {"label": 'Date exited "Hot Nurturing (OB SDR Pipeline)"', "column": "ob_hot_nurturing_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_25761465": {"label": 'Date entered "Long Nurturing (OB SDR Pipeline)"', "column": "ob_long_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_25761465": {"label": 'Date exited "Long Nurturing (OB SDR Pipeline)"', "column": "ob_long_nurturing_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_25761537": {"label": 'Date entered "Opportunity lost (OB SDR Pipeline)"', "column": "ob_opportunity_lost_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_25761537": {"label": 'Date exited "Opportunity lost (OB SDR Pipeline)"', "column": "ob_opportunity_lost_exited"},  # NOT IN SUPA
    # IB SDR Pipeline (id=831558698)
    "hs_v2_date_entered_1232383505": {"label": 'Date entered "New Qualified Opportunity (IB SDR Pipeline)"', "column": "ib_new_qualified_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1232383505": {"label": 'Date exited "New Qualified Opportunity (IB SDR Pipeline)"', "column": "ib_new_qualified_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1232383506": {"label": 'Date entered "Attempted to contact (IB SDR Pipeline)"', "column": "ib_attempted_contact_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1232383506": {"label": 'Date exited "Attempted to contact (IB SDR Pipeline)"', "column": "ib_attempted_contact_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1232383507": {"label": 'Date entered "Engaged (IB SDR Pipeline)"', "column": "ib_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1232383507": {"label": 'Date exited "Engaged (IB SDR Pipeline)"', "column": "ib_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1232383508": {"label": 'Date entered "Meeting Booked (IB SDR Pipeline)"', "column": "ib_meeting_booked_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1232383508": {"label": 'Date exited "Meeting Booked (IB SDR Pipeline)"', "column": "ib_meeting_booked_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1232383509": {"label": 'Date entered "To Reschedule (IB SDR Pipeline)"', "column": "ib_to_reschedule_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1232383509": {"label": 'Date exited "To Reschedule (IB SDR Pipeline)"', "column": "ib_to_reschedule_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1232383510": {"label": 'Date entered "Nurturing (IB SDR Pipeline)"', "column": "ib_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1232383510": {"label": 'Date exited "Nurturing (IB SDR Pipeline)"', "column": "ib_nurturing_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1232383511": {"label": 'Date entered "Opportunity Lost  (IB SDR Pipeline)"', "column": "ib_opportunity_lost_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1232383511": {"label": 'Date exited "Opportunity Lost  (IB SDR Pipeline)"', "column": "ib_opportunity_lost_exited"},  # NOT IN SUPA
    # XL Account Pipeline (id=685413816)
    "hs_v2_date_entered_1115587680": {"label": 'Date entered "Demo request from Prospect (XL Account Pipeline)"', "column": "xl_demo_request_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1115587680": {"label": 'Date exited "Demo request from Prospect (XL Account Pipeline)"', "column": "xl_demo_request_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003800944": {"label": 'Date entered "New (XL Account Pipeline)"', "column": "xl_new_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003800944": {"label": 'Date exited "New (XL Account Pipeline)"', "column": "xl_new_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003800946": {"label": 'Date entered "Outreach (XL Account Pipeline)"', "column": "xl_outreach_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003800946": {"label": 'Date exited "Outreach (XL Account Pipeline)"', "column": "xl_outreach_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003800947": {"label": 'Date entered "Engaged (XL Account Pipeline)"', "column": "xl_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003800947": {"label": 'Date exited "Engaged (XL Account Pipeline)"', "column": "xl_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425492": {"label": 'Date entered "Opportunity Lost (XL Account Pipeline)"', "column": "xl_opportunity_lost_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425492": {"label": 'Date exited "Opportunity Lost (XL Account Pipeline)"', "column": "xl_opportunity_lost_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1226596617": {"label": 'Date entered "Meeting Booked (XL Account Pipeline)"', "column": "xl_meeting_booked_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1226596617": {"label": 'Date exited "Meeting Booked (XL Account Pipeline)"', "column": "xl_meeting_booked_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899362020": {"label": 'Date entered "To Reschedule (XL Account Pipeline)"', "column": "xl_to_reschedule_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899362020": {"label": 'Date exited "To Reschedule (XL Account Pipeline)"', "column": "xl_to_reschedule_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003685894": {"label": 'Date entered "Discovery (XL Account Pipeline)"', "column": "xl_discovery_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003685894": {"label": 'Date exited "Discovery (XL Account Pipeline)"', "column": "xl_discovery_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4897330392": {"label": 'Date entered "Sales Nurturing (XL Account Pipeline)"', "column": "xl_sales_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4897330392": {"label": 'Date exited "Sales Nurturing (XL Account Pipeline)"', "column": "xl_sales_nurturing_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003685895": {"label": 'Date entered "Product Alignment (XL Account Pipeline)"', "column": "xl_product_alignment_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003685895": {"label": 'Date exited "Product Alignment (XL Account Pipeline)"', "column": "xl_product_alignment_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003685896": {"label": 'Date entered "Pricing & Packaging (XL Account Pipeline)"', "column": "xl_pricing_packaging_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003685896": {"label": 'Date exited "Pricing & Packaging (XL Account Pipeline)"', "column": "xl_pricing_packaging_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003685897": {"label": 'Date entered "Contracting (XL Account Pipeline)"', "column": "xl_contracting_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003685897": {"label": 'Date exited "Contracting (XL Account Pipeline)"', "column": "xl_contracting_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003800948": {"label": 'Date entered "Closed Pending Payment (XL Account Pipeline)"', "column": "xl_closed_pending_payment_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003800948": {"label": 'Date exited "Closed Pending Payment (XL Account Pipeline)"', "column": "xl_closed_pending_payment_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003800949": {"label": 'Date entered "Closed Won (XL Account Pipeline)"', "column": "xl_closed_won_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003800949": {"label": 'Date exited "Closed Won (XL Account Pipeline)"', "column": "xl_closed_won_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1003800950": {"label": 'Date entered "Closed Lost (XL Account Pipeline)"', "column": "xl_closed_lost_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1003800950": {"label": 'Date exited "Closed Lost (XL Account Pipeline)"', "column": "xl_closed_lost_exited"},  # NOT IN SUPA
    # XL SDR Pipeline (id=3576083668)
    "hs_v2_date_entered_4899425498": {"label": 'Date entered "New (XL SDR Pipeline)"', "column": "xlsdr_new_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425498": {"label": 'Date exited "New (XL SDR Pipeline)"', "column": "xlsdr_new_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425499": {"label": 'Date entered "Research & Outreach (XL SDR Pipeline)"', "column": "xlsdr_research_outreach_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425499": {"label": 'Date exited "Research & Outreach (XL SDR Pipeline)"', "column": "xlsdr_research_outreach_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425500": {"label": 'Date entered "Connected - Not Engaged (XL SDR Pipeline)"', "column": "xlsdr_connected_not_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425500": {"label": 'Date exited "Connected - Not Engaged (XL SDR Pipeline)"', "column": "xlsdr_connected_not_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425501": {"label": 'Date entered "Engaged (XL SDR Pipeline)"', "column": "xlsdr_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425501": {"label": 'Date exited "Engaged (XL SDR Pipeline)"', "column": "xlsdr_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425502": {"label": 'Date entered "Meeting Booked (XL SDR Pipeline)"', "column": "xlsdr_meeting_booked_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425502": {"label": 'Date exited "Meeting Booked (XL SDR Pipeline)"', "column": "xlsdr_meeting_booked_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425503": {"label": 'Date entered "To reschedule (XL SDR Pipeline)"', "column": "xlsdr_to_reschedule_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425503": {"label": 'Date exited "To reschedule (XL SDR Pipeline)"', "column": "xlsdr_to_reschedule_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425504": {"label": 'Date entered "Hot Nurturing (XL SDR Pipeline)"', "column": "xlsdr_hot_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425504": {"label": 'Date exited "Hot Nurturing (XL SDR Pipeline)"', "column": "xlsdr_hot_nurturing_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425505": {"label": 'Date entered "Long Nurturing (XL SDR Pipeline)"', "column": "xlsdr_long_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425505": {"label": 'Date exited "Long Nurturing (XL SDR Pipeline)"', "column": "xlsdr_long_nurturing_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4899425506": {"label": 'Date entered "Opportunity Lost (XL SDR Pipeline)"', "column": "xlsdr_opportunity_lost_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4899425506": {"label": 'Date exited "Opportunity Lost (XL SDR Pipeline)"', "column": "xlsdr_opportunity_lost_exited"},  # NOT IN SUPA
    # IT AE Pipeline (id=824790797)
    "hs_v2_date_entered_1220339227": {"label": 'Date entered "Demo request from Prospect (IT AE Pipeline)"', "column": "itae_demo_request_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220339227": {"label": 'Date exited "Demo request from Prospect (IT AE Pipeline)"', "column": "itae_demo_request_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220339228": {"label": 'Date entered "New (IT AE Pipeline)"', "column": "itae_new_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220339228": {"label": 'Date exited "New (IT AE Pipeline)"', "column": "itae_new_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220339229": {"label": 'Date entered "Outreach (IT AE Pipeline)"', "column": "itae_outreach_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220339229": {"label": 'Date exited "Outreach (IT AE Pipeline)"', "column": "itae_outreach_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220339230": {"label": 'Date entered "Engaged (IT AE Pipeline)"', "column": "itae_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220339230": {"label": 'Date exited "Engaged (IT AE Pipeline)"', "column": "itae_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_5043758307": {"label": 'Date entered "Meeting Booked (IT AE Pipeline)"', "column": "itae_meeting_booked_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_5043758307": {"label": 'Date exited "Meeting Booked (IT AE Pipeline)"', "column": "itae_meeting_booked_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_5043750115": {"label": 'Date entered "To Reschedule (IT AE Pipeline)"', "column": "itae_to_reschedule_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_5043750115": {"label": 'Date exited "To Reschedule (IT AE Pipeline)"', "column": "itae_to_reschedule_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220339231": {"label": 'Date entered "Discovery (IT AE Pipeline)"', "column": "itae_discovery_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220339231": {"label": 'Date exited "Discovery (IT AE Pipeline)"', "column": "itae_discovery_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220339232": {"label": 'Date entered "Product Alignment (IT AE Pipeline)"', "column": "itae_product_alignment_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220339232": {"label": 'Date exited "Product Alignment (IT AE Pipeline)"', "column": "itae_product_alignment_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220339233": {"label": 'Date entered "Pricing & Packaging (IT AE Pipeline)"', "column": "itae_pricing_packaging_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220339233": {"label": 'Date exited "Pricing & Packaging (IT AE Pipeline)"', "column": "itae_pricing_packaging_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220382581": {"label": 'Date entered "Contracting (IT AE Pipeline)"', "column": "itae_contracting_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220382581": {"label": 'Date exited "Contracting (IT AE Pipeline)"', "column": "itae_contracting_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220382582": {"label": 'Date entered "Closed Pending Payment (IT AE Pipeline)"', "column": "itae_closed_pending_payment_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220382582": {"label": 'Date exited "Closed Pending Payment (IT AE Pipeline)"', "column": "itae_closed_pending_payment_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220382583": {"label": 'Date entered "Closed Won (IT AE Pipeline)"', "column": "itae_closed_won_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220382583": {"label": 'Date exited "Closed Won (IT AE Pipeline)"', "column": "itae_closed_won_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_1220382584": {"label": 'Date entered "Closed Lost (IT AE Pipeline)"', "column": "itae_closed_lost_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_1220382584": {"label": 'Date exited "Closed Lost (IT AE Pipeline)"', "column": "itae_closed_lost_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_5043748053": {"label": 'Date entered "Opportunity Lost (IT AE Pipeline)"', "column": "itae_opportunity_lost_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_5043748053": {"label": 'Date exited "Opportunity Lost (IT AE Pipeline)"', "column": "itae_opportunity_lost_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_5043748049": {"label": 'Date entered "Sales Nurturing (IT AE Pipeline)"', "column": "itae_sales_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_5043748049": {"label": 'Date exited "Sales Nurturing (IT AE Pipeline)"', "column": "itae_sales_nurturing_exited"},  # NOT IN SUPA
    # IT SDR Pipeline (id=3612610753)
    "hs_v2_date_entered_5467457780": {"label": 'Date entered "Demo Request from Prospect (IT SDR Pipeline)"', "column": "itsdr_demo_request_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_5467457780": {"label": 'Date exited "Demo Request from Prospect (IT SDR Pipeline)"', "column": "itsdr_demo_request_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938161": {"label": 'Date entered "New (IT SDR Pipeline)"', "column": "itsdr_new_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938161": {"label": 'Date exited "New (IT SDR Pipeline)"', "column": "itsdr_new_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938162": {"label": 'Date entered "Research & Outreach (IT SDR Pipeline)"', "column": "itsdr_research_outreach_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938162": {"label": 'Date exited "Research & Outreach (IT SDR Pipeline)"', "column": "itsdr_research_outreach_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938163": {"label": 'Date entered "Connected - Not Engaged (IT SDR Pipeline)"', "column": "itsdr_connected_not_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938163": {"label": 'Date exited "Connected - Not Engaged (IT SDR Pipeline)"', "column": "itsdr_connected_not_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938164": {"label": 'Date entered "Engaged (IT SDR Pipeline)"', "column": "itsdr_engaged_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938164": {"label": 'Date exited "Engaged (IT SDR Pipeline)"', "column": "itsdr_engaged_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938165": {"label": 'Date entered "Meeting Booked (IT SDR Pipeline)"', "column": "itsdr_meeting_booked_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938165": {"label": 'Date exited "Meeting Booked (IT SDR Pipeline)"', "column": "itsdr_meeting_booked_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938166": {"label": 'Date entered "To reschedule (IT SDR Pipeline)"', "column": "itsdr_to_reschedule_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938166": {"label": 'Date exited "To reschedule (IT SDR Pipeline)"', "column": "itsdr_to_reschedule_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938167": {"label": 'Date entered "Hot Nurturing (IT SDR Pipeline)"', "column": "itsdr_hot_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938167": {"label": 'Date exited "Hot Nurturing (IT SDR Pipeline)"', "column": "itsdr_hot_nurturing_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938168": {"label": 'Date entered "Long Nurturing (IT SDR Pipeline)"', "column": "itsdr_long_nurturing_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938168": {"label": 'Date exited "Long Nurturing (IT SDR Pipeline)"', "column": "itsdr_long_nurturing_exited"},  # NOT IN SUPA
    "hs_v2_date_entered_4969938169": {"label": 'Date entered "Opportunity Lost (IT SDR Pipeline)"', "column": "itsdr_opportunity_lost_entered"},  # NOT IN SUPA
    "hs_v2_date_exited_4969938169": {"label": 'Date exited "Opportunity Lost (IT SDR Pipeline)"', "column": "itsdr_opportunity_lost_exited"},  # NOT IN SUPA
}

# Listas de internal names para pasar a HubSpot API
HS_ALL_DEAL_PROPS = list(HS_DEAL_PROPS.keys()) + list(HS_PIPELINE_DATE_MAP.keys())
HS_ALL_EMAIL_PROPS = list(HS_EMAIL_PROPS.keys())
HS_ALL_NOTE_PROPS = list(HS_NOTE_PROPS.keys())
HS_ALL_CALL_PROPS = list(HS_CALL_PROPS.keys())
HS_ALL_MEETING_PROPS = list(HS_MEETING_PROPS.keys())
HS_ALL_MEETING_SYNC_PROPS = list(HS_MEETING_PROPS_SYNC.keys())

# Mapping rapido: hs_internal_name → supabase_column (para upsert)
# Solo properties que van a tabla (column != None)
HS_TO_SUPABASE = {k: v["column"] for k, v in HS_DEAL_PROPS.items()}
HS_TO_SUPABASE.update({k: v["column"] for k, v in HS_PIPELINE_DATE_MAP.items()})
HS_TO_SUPABASE_MEETINGS = {k: v["column"] for k, v in HS_MEETING_PROPS_SYNC.items()}


# ============================================================================
# 11. DOMAINS
# ============================================================================

FACTORIAL_DOMAINS = frozenset({"factorial.co", "factorial.com", "factorialhr.com"})

GENERIC_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.es",
    "hotmail.com", "hotmail.es", "outlook.com", "outlook.es",
    "live.com", "icloud.com", "me.com", "protonmail.com",
    "aol.com", "mail.com", "zoho.com", "yandex.com", "tutanota.com",
    "msn.com", "gmx.com",
})

ISP_DOMAINS = frozenset({
    # España
    "telefonica.net", "movistar.es", "orange.es",
    "vodafone.es", "jazztel.es", "ono.com",
    "terra.es", "terra.com", "wanadoo.es",
    # Italia
    "libero.it", "alice.it", "tin.it", "virgilio.it",
    "tiscali.it", "fastwebnet.it", "pec.it",
    # Alemania
    "t-online.de", "web.de", "gmx.de", "freenet.de",
    "arcor.de", "vodafone.de",
})

MISC_IGNORE_DOMAINS = frozenset({
    "seg-social.es", "aeat.es", "gob.es",
    "empresite.eleconomista.es", "empresia.es", "einforma.com",
    "icab.cat", "icab.es", "docs.hackerone.com", "visitandorra.com",
    "hormail.com", "cmheia.com", "omeie.com",
    "yopmail.com", "mailinator.com", "guerrillamail.com",
})


# ============================================================================
# 12. CALENDAR
# ============================================================================

INTERNAL_MEETING_KEYWORDS = [
    "weekly", "daily", "1:1", "1 to 1", "sync", "sincro",
    "standup", "stand-up", "retro", "planning", "sprint", "partner sales team",
]

# PAEs/AEs con Google Calendar API conectado.
# Solo estos se sincronizan — el resto se salta para no perder tiempo en API calls que fallan.
# Para activar un rep nuevo: añadir su email aquí.
CALENDAR_ACTIVE_REPS: set[str] = {
    # Santander
    "xavier.fortuny@factorial.co",
    "jose.donis@factorial.co",
    "pol.bartolome@factorial.co",
    "roberto.moran@factorial.co",
    "beatriz.bravo@factorial.co",
    "joan.lorenzo@factorial.co",
    "joan.balana@factorial.co",
    "eduardo.zafra@factorial.co",
    # Telefonica
    "david.clemente@factorial.co",
    "nerea.urien@factorial.co",
    "carlos.sanchez@factorial.co",
    "alejandro.soto@factorial.co",
    # TIM
    "nunzio.fumo@factorial.co",
    "emilio.fabbro@factorial.co",
    "marco.falaschetti@factorial.co",
    "giovanni.laghi@factorial.co",
    "edoardo.rapezzi@factorial.co",
    "christian.lombardo@factorial.co",
    "giuditta.giunta@factorial.co",
    # TELEKOM
    "gabriel.lichtenstein@factorial.co",
    "leonhard.zeus@factorial.co",
    "katrin.virtbauer@factorial.co",
    "stefan.platt@factorial.co",
    "enrique.gautier@factorial.co",
    "jonas.tretter@factorial.co",
    # DS / XL: añadir cuando se conecten
}


# ============================================================================
# 13. ATLAS CONFIG — todo lo que atlas.py necesita
# ============================================================================

ATLAS_CONFIG = {
    # Prompts
    "base_prompt_path": "company/base.txt",
    "prompt_path": "core/atlas/system.txt",

    # HubSpot properties que pedimos para companies
    "hs_company_props": [
        "name", "industry", "numberofemployees", "country",
        "website", "description", "city", "state", "annualrevenue",
    ],

    # HubSpot properties que pedimos para deals (subset — no necesita stage dates)
    "hs_deal_props": [
        "dealname", "dealstage", "amount", "closedate", "createdate",
        "hs_manual_forecast_category", "hubspot_owner_id",
        "hs_is_closed_won", "hs_is_closed",
    ],

    # HubSpot properties que pedimos para contacts
    "hs_contact_props": ["firstname", "lastname", "email", "jobtitle", "phone"],

    # HubSpot company property → Supabase atlas column (lo que guardamos directo)
    "hs_to_supabase": {
        "name": "company_name",
        "industry": "industry",
        "numberofemployees": "company_size",
        "country": "country",
        "website": "website",
        "description": "description",
    },

    # Campos que genera Claude → Supabase atlas column
    "claude_to_supabase": {
        "deal_history": "deal_history",
        "contacts_map": "contacts_map",
        "company_context": "company_context",
        "company_card": "company_card",       # jsonb
        "deal_insights": "deal_insights",     # jsonb
    },

    # Campos que genera el pipeline → Supabase atlas column
    "generated_columns": {
        "company_info": "company_info",             # texto formateado de company
        "deals_breakdown": "deals_breakdown",       # texto formateado de deals
        "contacts_breakdown": "contacts_breakdown", # texto formateado de contacts
        "sibling_crm_ids": "sibling_crm_ids",       # array de CRM IDs
        "last_generated": "last_generated",         # timestamp
    },

    # Tabla de Supabase
    "table": "atlas",

    # Columna en tabla deals que linkea al atlas (company association de HubSpot)
    "deal_column": "crm_id",
    "deal_fk_column": "atlas_id",

    # Labels para formatear company info en el prompt (HS property → label visible)
    "company_labels": {
        "name": "Nombre",
        "industry": "Industria",
        "numberofemployees": "Empleados",
        "annualrevenue": "Revenue anual",
        "country": "País",
        "city": "Ciudad",
        "website": "Web",
        "description": "Descripción",
    },

    # HubSpot association types
    "hs_assoc_deals": "deals",
    "hs_assoc_contacts": "contacts",

    # HubSpot company search property (para siblings)
    "hs_domain_prop": "domain",

    # Properties del deal que se usan para formateo (keys del JSON de HubSpot)
    "deal_format_fields": {
        "name": "dealname",
        "stage": "dealstage",
        "amount": "amount",
        "close_date": "closedate",
        "create_date": "createdate",
        "forecast": "hs_manual_forecast_category",
        "owner_id": "hubspot_owner_id",
        "is_closed_won": "hs_is_closed_won",
        "is_closed": "hs_is_closed",
    },

    # Properties del contact que se usan para formateo
    "contact_format_fields": {
        "firstname": "firstname",
        "lastname": "lastname",
        "email": "email",
        "jobtitle": "jobtitle",
        "phone": "phone",
    },
}


# ============================================================================
# 13b. INTELLIGENCE CONFIG — todo lo que intelligence.py necesita
# ============================================================================

INTELLIGENCE_CONFIG = {
    # ── Prompts ──────────────────────────────────────────────────────────────
    "system_prompt_path": "core/intelligence/system.txt",
    "product_catalog_path": "core/intelligence/product_catalog.txt",
    "base_prompt_path": "company/base.txt",
    "channel_prompts": {
        "partners": "company/channels/partners.txt",
        "direct_sales_es": "company/channels/direct_sales.txt",
        "xl_sales": "company/channels/xl.txt",
    },
    "role_prompts": {
        "PBD": "company/roles/pbd.txt",
        "PAE": "company/roles/pae.txt",
        "SDR": "company/roles/sdr.txt",
        "AE": "company/roles/ae.txt",
        "PDM": "company/roles/pdm.txt",
    },

    # ── Tablas Supabase ──────────────────────────────────────────────────────
    "deals_table": "deals",
    "calls_table": "calls",
    "emails_table": "emails",
    "notes_table": "notes",
    "atlas_table": "atlas",
    "pbd_audits_table": "pbd_audits",
    "pae_audits_table": "pae_audits",
    "snapshot_table": "front_deal_snapshots",
    "pbd_snapshot_table": "pbd_snapshots",
    "product_signals_table": "deal_product_signals",

    # ── Upsert keys ──────────────────────────────────────────────────────────
    "audits_upsert_key": "call_ref",
    "snapshot_upsert_key": "hs_deal_id,snapshot_date",
    "pbd_snapshot_upsert_key": "hs_deal_id,snapshot_date",

    # ── Deteccion de comunicaciones nuevas (regex sobre deal_context) ────────
    "context_call_pattern": r"\[call:(\S+)\]",
    "context_hs_pattern": r"\[hs:(\S+)\]",

    # ── Audit: columnas de metadata (pipeline copia de call, no de Claude) ──
    "audit_metadata_cols": {
        "call_ref": "id",
        "call_id": "call_id",
        "deal_ref": "deal_id",
        "crm_id": "crm_id",
        "hs_deal_id": "hs_deal_id",
        "owner_name": "owner_nombre",
    },

    # ── Audit: campos que Claude produce ────────────────────────────────────
    "audit_common_cols": [
        "win_rate_score", "forecast_flag", "partner_leverage_score",
        "lead_temperature", "discovery_level", "discovery_topics",
        "discovery_breakdown", "improvement_items_json",
        "deal_context", "deal_status", "biggest_gap",
        "next_call_objective", "tl_note", "top_coaching_flag",
        "next_action_rep", "hard_question", "objections",
        "rep_strengths", "buying_signals", "blockers", "tag_validation",
    ],
    "audit_bant_pillars": ["budget", "authority", "need", "timing"],
    "audit_meddic_pillars": [
        "metrics", "economic_buyer", "decision_criteria",
        "decision_process", "champion", "competition",
    ],
    "audit_script_cols": [
        "script_opener", "script_industry_pivot", "script_close", "two_slot_close",
    ],

    # ── Snapshot: metadata copiada de deals (no Claude) ─────────────────────
    "snapshot_metadata_from_deal": {
        "deal_name": "deal_name",
        "crm_id": "crm_id",
        "deal_age": "deal_age_days",
        "stage": "deal_stage",
        "mrr": "amount",
        "hs_forecast_category": "forecast_category",
        "pbd": "pbd",
        "pae": "pae",
    },

    # ── Snapshot: campos que Claude produce ─────────────────────────────────
    "snapshot_claude_cols": [
        "deal_summary", "deal_assessment",
        "m_accumulate", "m_score",
        "e_accumulate", "e_score",
        "dc_accumulate", "dc_score",
        "dp_accumulate", "dp_score",
        "i_accumulate", "i_score",
        "c_accumulate", "c_score",
        "comp_accumulate", "comp_score",
        "objections", "buyer_signals", "live_blockers",
        "improvements", "deal_strengths",
        "next_step", "action_signal",
        "howto_label", "howto_body",
    ],

    # ── PBD Snapshot: campos BANT ───────────────────────────────────────────
    "pbd_snapshot_cols": [
        "bant_b_status", "bant_b_evidence",
        "bant_a_status", "bant_a_evidence",
        "bant_n_status", "bant_n_evidence",
        "bant_t_status", "bant_t_evidence",
        "pbd_summary",
    ],

    # ── Context entry: formato para append a deals.deal_context ──────────────
    "deal_context_col": "deal_context",
    "deal_context_rpc": "append_deal_context",
    "deal_context_rpc_params": {"deal_id": "p_deal_id", "text": "p_text"},
    "context_stale_col": "context_stale",

    # ── Columnas de FK para queries ─────────────────────────────────────────
    "fk_deal_id": "deal_id",           # calls/emails/notes → deal UUID
    "fk_crm_id": "crm_id",            # atlas lookup
    "fk_hs_deal_id": "hs_deal_id",    # snapshot lookup
    "fk_snapshot_date": "snapshot_date",

    # ── Columnas de la tabla calls ──────────────────────────────────────────
    "call_col_id": "id",
    "call_col_call_id": "call_id",
    "call_col_hs_call_id": "hs_call_id",
    "call_col_fecha": "fecha",
    "call_col_owner_email": "owner_email",
    "call_col_owner_nombre": "owner_nombre",
    "call_col_rol": "rol",
    "call_col_tags": "tags",
    "call_col_duracion": "duracion_segundos",
    "call_col_transcript": "transcript",
    "call_col_titulo": "titulo",
    "call_col_created_at": "created_at",

    # ── Columnas de la tabla emails ─────────────────────────────────────────
    "email_col_engagement_id": "hs_engagement_id",
    "email_col_date": "date",
    "email_col_direction": "direction",
    "email_col_from": "from_email",
    "email_col_subject": "subject",
    "email_col_body_clean": "body_clean",
    "email_col_body": "body",

    # ── Columnas de la tabla notes ──────────────────────────────────────────
    "note_col_engagement_id": "hs_engagement_id",
    "note_col_date": "date",
    "note_col_owner": "owner",
    "note_col_content": "content",

    # ── Columnas de la tabla deals (lectura) ────────────────────────────────
    "deal_col_id": "id",
    "deal_col_deal_id": "deal_id",
    "deal_col_deal_name": "deal_name",
    "deal_col_stage": "deal_stage",
    "deal_col_amount": "amount",
    "deal_col_age": "deal_age_days",
    "deal_col_close_date": "close_date",
    "deal_col_forecast_cat": "forecast_category",
    "deal_col_pbd": "pbd",
    "deal_col_pae": "pae",
    "deal_col_team": "team",
    "deal_col_crm_id": "crm_id",

    # ── Columnas de escritura snapshot/pbd ──────────────────────────────────
    "write_deal_id": "deal_id",
    "write_hs_deal_id": "hs_deal_id",
    "write_snapshot_date": "snapshot_date",
    "write_pbd_col": "pbd",

    # ── Atlas columns (lectura) ─────────────────────────────────────────────
    "atlas_col_company_context": "company_context",
    "atlas_col_company_card": "company_card",

    # ── Product intel columns ───────────────────────────────────────────────
    "product_col_deal_id": "deal_id",
    "product_col_snapshot_date": "snapshot_date",
    "product_col_products": "products_discussed",
    "product_col_upsell": "upsell_opportunity",
    "product_col_pitch": "pitch_quality",
    "product_upsert_key": "deal_id,snapshot_date",

    # ── HubSpot engagement properties (para fetch de associations) ──────────
    "hs_email_props": [
        "hs_timestamp", "hs_createdate", "hs_email_direction",
        "hs_email_from_email", "hs_email_subject",
        "hs_email_text", "hs_email_html",
    ],
    "hs_note_props": [
        "hs_timestamp", "hs_createdate", "hs_note_body", "hubspot_owner_id",
    ],
    "hs_call_props": [
        "hs_timestamp", "hs_call_body", "hs_call_duration",
        "hs_call_title", "hubspot_owner_id",
    ],
    "hs_meeting_props": [
        "hs_timestamp", "hs_meeting_title", "hs_meeting_body",
        "hs_internal_meeting_notes", "hs_meeting_start_time",
        "hs_meeting_end_time", "hs_meeting_outcome", "hubspot_owner_id",
    ],

    # ── Modjo ───────────────────────────────────────────────────────────────
    "modjo_link_pattern": r"app\.modjo\.ai/call-details/(\d+)",

    # ── Calls upsert ────────────────────────────────────────────────────────
    "calls_upsert_key": "call_id",

    # ── Thresholds ──────────────────────────────────────────────────────────
    "max_comms_per_batch": 15,
    "transcript_pending_hours": 24,
    "min_transcript_length": 200,

    # ── Filtros de exclusion ─────────────────────────────────────────────
    "deal_name_exclude_patterns": ["session"],
}


# ============================================================================
# 14. SYNC CONFIG — todo lo que sync.py necesita (tables, properties, on_conflict)
# ============================================================================

SYNC_CONFIG = {
    # Tablas de Supabase
    "deals_table": "deals",
    "deals_upsert_key": "deal_id",
    "meetings_table": "deal_meetings",
    "meetings_upsert_key": "hs_meeting_id",
    "meetings_col_deal_id": "hs_deal_id",
    "meetings_col_meeting_id": "hs_meeting_id",

    # HubSpot property para stage (para filtrar stages excluidos)
    "hs_dealstage_prop": "dealstage",

    # HubSpot property names usados en queries de búsqueda
    "hs_partner_name_prop": "partner_name",
    "hs_team_string_prop": "current_hubspot_team__string_",
    "hs_owner_id_prop": "hubspot_owner_id",
    "hs_pipeline_prop": "pipeline",
    "hs_object_id_prop": "hs_object_id",

    # Properties del deal que se leen para resolver (no para guardar — esas están en HS_DEAL_PROPS)
    "hs_created_by_prop": "created_by",

    # Columnas de Supabase que sync escribe (además de HS_TO_SUPABASE)
    "col_pae": "pae",
    "col_pbd": "pbd",
    "col_team": "team",
    "col_last_synced": "last_synced",
    "col_context_stale": "context_stale",
    "col_deal_id": "deal_id",
}


# ============================================================================
# 15. THRESHOLDS
# ============================================================================

MAX_DEALS_PER_CYCLE = 100
CORE_TIMEOUT_MINUTES = 55
UPSERT_BATCH_SIZE = 500
MIN_TRANSCRIPT_LENGTH = 100
MIN_TRANSCRIPT_FOR_AUDIT = 200
TRANSCRIPT_TIMEOUT_HOURS = 48
MAX_DEALS_PER_DOMAIN = 5
CALENDAR_CLEANUP_DAYS = 7
MIN_PIPELINE_REVIEW_PROBABILITY = 46
MRR_TOP_DEAL_THRESHOLD = 3000
HUBSPOT_MIN_REQUEST_INTERVAL = 0.2
HUBSPOT_MAX_RETRIES = 5
HUBSPOT_RETRYABLE_CODES = {401, 429, 500, 502, 503}
CLAUDE_MAX_RETRIES = 3
CLAUDE_DEFAULT_MAX_TOKENS = 16000
CLAUDE_RETRY_BACKOFF_BASE = 10
MAX_MODJO_WORKERS = 2
MODJO_RATE_LIMIT_WAIT = 310
MODJO_LOOKBACK_HOURS = 2
DEMO_EXIT_DATE_TOLERANCE_DAYS = 3
MIN_TRAJECTORIES_FOR_PATTERNS = 10

MAX_TOKENS_AUDIT = 16000
MAX_TOKENS_SNAPSHOT = 16000
MAX_TOKENS_FORECAST_V1 = 2000
MAX_TOKENS_FORECAST_V2 = 2000
MAX_TOKENS_PBD_BANT = 16000
MAX_TOKENS_ATLAS = 16000
MAX_TOKENS_BRIEFING = 4000
MAX_TOKENS_EMAIL_DRAFT = 4000
MAX_TOKENS_EB_ANALYZE = 1000
MAX_TOKENS_EB_CLASSIFY = 400
MAX_TOKENS_EB_COACHING = 200
MAX_TOKENS_FOLLOWUP = 12000
MAX_TOKENS_FOLLOWUP_CLASSIFY = 500
MAX_TOKENS_TRAJECTORY_LESSONS = 1000
MAX_TOKENS_PATTERNS = 16000
MAX_TOKENS_DEMO_EVAL = 16000


# ============================================================================
# 14. FORECAST CONFIG — todo lo que forecast.py necesita
# ============================================================================

FORECAST_CONFIG = {
    # Prompt
    "system_prompt_path": "core/forecast/system.txt",

    # Tablas (las que NO están en INTELLIGENCE_CONFIG)
    "trajectories_table": "deal_trajectories",
    "patterns_table": "learned_patterns",
    "calibration_table": "calibration_log",

    # Columnas que Claude produce → se escriben al snapshot
    "claude_cols": [
        "closes_this_month", "closes_next_month",
        "forecast_confidence", "forecast_reasoning",
        "forecast_risks", "forecast_accelerators",
        "forecast_pushable", "push_action", "push_action_reasoning",
        "deal_momentum", "claudio_close_date", "close_date_reasoning",
    ],

    # Campos raw de Claude que alimentan la fórmula (no se guardan directamente)
    "formula_input_fields": ["deal_killer", "deal_killer_value", "bs", "lb"],

    # Columnas calculadas por Python → se escriben al snapshot
    "computed_cols": ["close_probability", "claudio_forecast"],

    # MEDDIC weights para la fórmula de probability
    "meddic_weights": {
        "C": 0.12, "E": 0.22, "DP": 0.18, "DC": 0.18,
        "I": 0.13, "M": 0.05, "Comp": 0.12,
    },

    # Campos del snapshot que se pasan como input al prompt
    "snapshot_input_cols": [
        "deal_summary", "deal_assessment",
        "m_score", "e_score", "dc_score", "dp_score",
        "i_score", "c_score", "comp_score",
        "buyer_signals", "live_blockers", "objections",
        "next_step", "action_signal",
        "closes_this_month", "forecast_confidence",
        "forecast_reasoning", "push_action", "deal_momentum",
    ],

    # Thresholds
    "max_similar_won": 5,
    "max_similar_lost": 5,
    "max_trajectory_snapshots": 15,
    "max_patterns": 10,
    "max_calibration_entries": 5,
    "max_deal_context_chars": 5000,
}



# ============================================================================
# 15. PARSER CONFIG — todo lo que parser.py necesita
# ============================================================================

PARSER_CONFIG = {
    "table": "deal_ui",
    "upsert_key": "deal_id",

    # Stage → macro_stage para agrupar en pipeline view
    "macro_stage_map": {
        "Pre-qualified": "prospecting",
        "Attempting to contact": "prospecting",
        "Attempted to contact": "prospecting",
        "Research & Outreach": "prospecting",
        "Associating the partner": "prospecting",
        "Connected - Not Engaged": "prospecting",
        "New": "prospecting",
        "New Deals": "prospecting",
        "Opportunity detected": "prospecting",
        "Engaged": "qualifying",
        "Factorial Project Alignment started": "demo",
        "Demo Booked": "demo",
        "Meeting Booked": "demo",
        "Meeting scheduled": "demo",
        "Product Alignment": "demo",
        "Discovery": "demo",
        "To reschedule": "demo",
        "To Reschedule": "demo",
        "MEDDPICC Criteria Validation Started": "evaluating",
        "Economical Allignment Started": "closing",
        "Economical Alignment Started": "closing",
        "Pricing and Packaging": "closing",
        "Pricing & Packaging": "closing",
        "Contract Sent": "closing",
        "Contracting": "closing",
        "On Hold": "onhold",
        "Nurturing": "nurturing",
        "Sales Nurturing": "nurturing",
        "Hot Nurturing": "nurturing",
        "Long Nurturing": "nurturing",
    },

    # Días sin contacto para considerar deal stale, por macro_stage
    "stale_thresholds": {
        "prospecting": 21,
        "qualifying": 14,
        "demo": 10,
        "evaluating": 14,
        "closing": 7,
        "nurturing": 30,
        "onhold": 45,
    },
    "stale_default": 14,

    # Action tag detection keywords
    "action_tags": {
        "CALL": ["[CALL]", "llamar", "call", "chiamare", "anrufen"],
        "EMAIL": ["[EMAIL]", "email", "enviar", "escribir", "scrivere", "send"],
        "ROI": ["[ROI]", "roi", "business case"],
        "SLIDES": ["[SLIDES]", "slides", "presentación", "deck"],
        "BATTLECARD": ["[BATTLECARD]", "battlecard", "comparativa"],
    },
    "action_default_type": "PREP",

    # Date parsing
    "day_names": {
        "lunes": 0, "martes": 1, "miércoles": 2, "jueves": 3,
        "viernes": 4, "sábado": 5, "domingo": 6,
    },
    "month_names": {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    },
    "default_followup_days": 3,
    "max_next_steps": 5,
    "signal_max_chars": 80,

    # Probability → score (0-5) para badge visual
    "score_divisor": 20,

    # Momentum → arrow para tabla forecast
    "momentum_arrows": {
        "accelerating": "▲",
        "stable": "→",
        "decelerating": "▼",
        "stalled": "▼",
    },
}


# ============================================================================
# 15b. WEEKLY CONFIG — todo lo que el weekly run necesita
# ============================================================================

WEEKLY_CONFIG = {
    "patterns_table": "learned_patterns",
    "patterns_prompt_path": "weekly/patterns.txt",
    "trajectories_table": "deal_trajectories",
    "min_trajectories": 10,

    # Statistical pattern keys
    "stat_pattern_types": {
        "temporal_month_end": "Porcentaje de deals que cierran en los últimos 5 días del mes",
        "temporal_quarter_end": "Porcentaje de deals que cierran en el último mes del quarter",
        "stage_velocity": "Media de días por stage antes de cerrar",
        "size_close_time": "Tiempo medio de cierre por rango de MRR",
        "win_rate_by_team": "Win rate por equipo",
        "loss_reasons": "Top razones de pérdida con frecuencia",
    },

    # MRR ranges for size patterns
    "mrr_ranges": [
        {"label": "<500€", "min": 0, "max": 500},
        {"label": "500-1000€", "min": 500, "max": 1000},
        {"label": "1000-3000€", "min": 1000, "max": 3000},
        {"label": ">3000€", "min": 3000, "max": 999999},
    ],
}


# ============================================================================
# 15c. MONTHLY CONFIG — todo lo que el monthly run necesita
# ============================================================================

MONTHLY_CONFIG = {
    "calibration_table": "calibration_log",
    "snapshot_table": "front_deal_snapshots",
    "deals_table": "deals",

    # Columns
    "deal_col_id": "id",
    "deal_col_deal_name": "deal_name",
    "deal_col_stage": "deal_stage",
    "deal_col_close_date": "close_date",

    # Closed stages (reuse)
    "closed_won_stages": list(STAGE_WON),
    "closed_lost_stages": list(STAGE_LOST),
}


# ============================================================================
# 15d. HOURLY CONFIG — todo lo que el hourly run necesita
# ============================================================================

HOURLY_CONFIG = {
    # Meeting detection sources
    "deals_meeting_col": "hs_next_meeting_start_time",
    "deal_meetings_table": "deal_meetings",
    "deal_meetings_start_col": "meeting_start",
    "deal_meetings_deal_col": "deal_id",
    "calendar_meetings_table": "calendar_meetings",
    "calendar_meetings_start_col": "meeting_start",
    "calendar_meetings_deal_col": "deal_id",
    "calendar_meetings_resolved_col": "resolved",

    # Briefings
    "briefings_table": "briefings",
    "briefing_prompt_base": "hourly/briefing/base.txt",
    "briefing_prompts": {
        "pae_brief_first_demo_multisector": "hourly/briefing/first_demo.txt",
        "pae_brief_followup_meddic_multisector": "hourly/briefing/followup_meddic.txt",
        "pae_brief_pricing_closing_multisector": "hourly/briefing/pricing_closing.txt",
    },

    # Email drafts
    "email_drafts_table": "email_drafts",
    "email_draft_prompt": "hourly/email_draft.txt",
}


# ============================================================================
# 15c. DAILY CONFIG — todo lo que el daily run necesita
# ============================================================================

DAILY_CONFIG = {
    # Trajectories
    "trajectories_table": "deal_trajectories",
    "trajectories_prompt_path": "daily/trajectory.txt",
    "trajectories_max_per_run": 20,
    "closed_stages": list(CLOSED_ALL),
    "on_hold_stages": ["On Hold"],

    # Closed deal detection — daily checks Supabase (active stage) vs HubSpot (closed)
    "hs_dealstage_prop": "dealstage",

    # Deal Analysis (post-mortem)
    "analysis_table": "deal_analysis",
    "analysis_prompt_path": "daily/deal_analysis.txt",
    "analysis_max_per_run": 20,

    # FK columns en trajectories y analysis tables
    "fk_deal_id": "deal_id",

    # Snapshot history for trajectory compilation
    "snapshot_trajectory_cols": [
        "snapshot_date", "close_probability",
        "m_score", "e_score", "dc_score", "dp_score", "i_score", "c_score", "comp_score",
        "buyer_signals", "live_blockers", "next_step", "deal_assessment", "action_signal",
    ],
}


# ============================================================================
# 16. API ENDPOINTS
# ============================================================================

HUBSPOT_BASE_URL = "https://api.hubapi.com"
HUBSPOT_APP_URL = "https://app.hubspot.com"                       # Para links a deals en Slack messages
MODJO_BASE_URL = "https://api.modjo.ai/v1"
SLACK_BASE_URL = "https://slack.com/api"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
# Azure Claude endpoint va en .env (AZURE_CLAUDE_ENDPOINT)
# Supabase URL va en .env (SUPABASE_URL)


# ============================================================================
# 17. DERIVED SETS — generados automaticamente del orgchart
# ============================================================================

ALL_PBD_EMAILS: set[str] = set()
ALL_PAE_EMAILS: set[str] = set()
ALL_REP_EMAILS: set[str] = set()
ALL_PARTNER_NAMES: set[str] = set()
ALL_PARTNER_DOMAINS: set[str] = set()
ALL_DS_EMAILS: set[str] = set()
_EMAIL_TO_TEAM: dict[str, str] = {}
_EMAIL_TO_TEAMS: dict[str, list[str]] = {}


def _collect_ae_emails(team_dict: dict) -> set[str]:
    emails = set()
    emails |= team_dict.get("ae", set())
    if "tl" in team_dict:
        emails.add(team_dict["tl"])
    for sub in team_dict.get("subteams", {}).values():
        emails |= _collect_ae_emails(sub)
    return emails


for _name, _team in PARTNERS_ORGCHART.items():
    ALL_PBD_EMAILS |= _team.get("pbd", set())
    ALL_PAE_EMAILS |= _team.get("pae", set())
    ALL_REP_EMAILS |= _team.get("pbd", set()) | _team.get("pae", set())
    pi = PARTNER_IDENTITY.get(_name, {})
    ALL_PARTNER_NAMES |= pi.get("partner_names", set())
    ALL_PARTNER_DOMAINS |= pi.get("partner_domains", set())
    for email in _team.get("pbd", set()) | _team.get("pae", set()):
        _EMAIL_TO_TEAM[email] = _name
        _EMAIL_TO_TEAMS.setdefault(email, []).append(_name)
    # Subteams (Mexico, etc.) — sus miembros tambien pertenecen al team padre
    for _sub in _team.get("subteams", {}).values():
        for email in _sub.get("pbd", set()) | _sub.get("pae", set()):
            ALL_REP_EMAILS.add(email)
            if email not in _EMAIL_TO_TEAM:
                _EMAIL_TO_TEAM[email] = _name
            _EMAIL_TO_TEAMS.setdefault(email, []).append(_name)
        # Leadership dentro de subteams (ej: Francesc Terns en Mexico)
        for _role in _sub.get("leadership", {}).values():
            _ld_email = _role.get("email")
            if _ld_email and _ld_email not in _EMAIL_TO_TEAM:
                _EMAIL_TO_TEAM[_ld_email] = _name
                _EMAIL_TO_TEAMS.setdefault(_ld_email, []).append(_name)
                ALL_REP_EMAILS.add(_ld_email)
    # Leadership (directors, TLs) — tambien cierran deals
    for _role in _team.get("leadership", {}).values():
        _ld_email = _role.get("email")
        if _ld_email and _ld_email not in _EMAIL_TO_TEAM:
            _EMAIL_TO_TEAM[_ld_email] = _name
            _EMAIL_TO_TEAMS.setdefault(_ld_email, []).append(_name)
            ALL_REP_EMAILS.add(_ld_email)

# DS Sales Director
_ds_director_email = DIRECT_SALES_ES.get("sales_director", {}).get("email")
if _ds_director_email:
    _EMAIL_TO_TEAM[_ds_director_email] = "DS España"
    _EMAIL_TO_TEAMS.setdefault(_ds_director_email, []).append("DS España")
    ALL_REP_EMAILS.add(_ds_director_email)

for _name, _ds_team in DIRECT_SALES_ES.get("teams", {}).items():
    ds_emails = _collect_ae_emails(_ds_team)
    ALL_DS_EMAILS |= ds_emails
    ALL_REP_EMAILS |= ds_emails
    for email in ds_emails:
        _EMAIL_TO_TEAM[email] = _name
        _EMAIL_TO_TEAMS.setdefault(email, []).append(_name)

ALL_XL_EMAILS = XL_SALES.get("ae", set()) | XL_SALES.get("sdr", set())
ALL_REP_EMAILS |= ALL_XL_EMAILS
for _email in ALL_XL_EMAILS:
    _EMAIL_TO_TEAM[_email] = "XL"
    _EMAIL_TO_TEAMS.setdefault(_email, []).append("XL")

ALL_TARGET_EMAILS = ALL_REP_EMAILS | MANAGER_EMAILS

# Equipos activos — solo estos se procesan en el CORE.
# Sync deals coge TODOS los deals, pero audit/snapshot/forecast solo para equipos activos.
# Para activar un equipo: cambiar "active": False → True en el orgchart.
ACTIVE_TEAMS: set[str] = set()
for _name, _team in PARTNERS_ORGCHART.items():
    if _team.get("active", False):
        ACTIVE_TEAMS.add(_name)
for _name, _ds_team in DIRECT_SALES_ES.get("teams", {}).items():
    if _ds_team.get("active", False):
        ACTIVE_TEAMS.add(_name)
if XL_SALES.get("active", False):
    ACTIVE_TEAMS.add("XL")

IGNORE_DOMAINS_ATLAS = GENERIC_EMAIL_DOMAINS | ISP_DOMAINS | FACTORIAL_DOMAINS | ALL_PARTNER_DOMAINS | MISC_IGNORE_DOMAINS
IGNORE_DOMAINS_CALENDAR = FACTORIAL_DOMAINS | ALL_PARTNER_DOMAINS | GENERIC_EMAIL_DOMAINS

# Reverse lookups
_OWNER_ID_TO_EMAIL = {v["id"]: email for email, v in HUBSPOT_OWNER_IDS.items()}
_EMAIL_TO_NAME = {email: v["name"] for email, v in HUBSPOT_OWNER_IDS.items()}


# ============================================================================
# 18. HELPER FUNCTIONS
# ============================================================================

def get_stage_short(stage: str) -> str:
    """Devuelve el nombre limpio del stage. Fallback al stage original."""
    return STAGE_DISPLAY.get(stage, {}).get("short", stage)


def get_stage_abbr(stage: str) -> str:
    """Devuelve la abreviatura del stage. Fallback a las primeras 3 letras."""
    return STAGE_DISPLAY.get(stage, {}).get("abbr", stage[:3].upper())


def get_stage_category(stage: str) -> str | None:
    """Devuelve la categoria del stage: prospecting/demo/evaluation/closing/nurturing/won/lost."""
    if stage in STAGE_PROSPECTING: return "prospecting"
    if stage in STAGE_DEMO: return "demo"
    if stage in STAGE_EVALUATION: return "evaluation"
    if stage in STAGE_CLOSING: return "closing"
    if stage in STAGE_NURTURING: return "nurturing"
    if stage in STAGE_WON: return "won"
    if stage in STAGE_LOST: return "lost"
    return None


def get_briefing_prompt(stage: str) -> str | None:
    """Devuelve el prompt key para el briefing pre-meeting segun el stage del deal."""
    cat = get_stage_category(stage)
    if cat in STAGE_CATEGORY_BRIEFING:
        return STAGE_CATEGORY_BRIEFING[cat]
    return None


def get_output_lang(team_name: str) -> str:
    """Devuelve la instruccion de idioma para inyectar en prompts."""
    pi = PARTNER_IDENTITY.get(team_name, {})
    lang = pi.get("lang", OUTPUT_LANG_DEFAULT)
    return OUTPUT_LANGUAGES.get(lang, OUTPUT_LANGUAGES[OUTPUT_LANG_DEFAULT])


def get_tz(team_name: str, subteam: str | None = None) -> ZoneInfo:
    pi = PARTNER_IDENTITY.get(team_name, {})
    if subteam and "subteams" in pi:
        sub_tz = pi["subteams"].get(subteam, {}).get("tz")
        if sub_tz:
            return TIMEZONES[sub_tz]
    tz_key = pi.get("tz")
    if tz_key:
        return TIMEZONES[tz_key]
    return TZ_DEFAULT


def get_subteam(email: str) -> str | None:
    return _EMAIL_TO_TEAM.get(email)


def get_role(email: str, tags: list[str] | None = None) -> str | None:
    in_pbd = email in ALL_PBD_EMAILS
    in_pae = email in ALL_PAE_EMAILS
    if in_pbd and not in_pae:
        return "PBD"
    if in_pae and not in_pbd:
        return "PAE"
    if in_pbd and in_pae:
        return "PAE" if tags and any(t in PAE_TAGS for t in tags) else "PBD"
    if email in ALL_DS_EMAILS or email in ALL_XL_EMAILS:
        return "AE"
    return None


def get_org(email: str) -> str | None:
    team_name = get_subteam(email)
    if team_name:
        if team_name in PARTNERS_ORGCHART:
            return "partners"
        if team_name in DIRECT_SALES_ES.get("teams", {}):
            return "direct_sales_es"
        if team_name == "XL":
            return "xl_sales"
    return None


def get_partner_label(email: str) -> str:
    team_name = get_subteam(email)
    if team_name:
        pi = PARTNER_IDENTITY.get(team_name, {})
        return pi.get("prompt_partner_label", "Unknown Partner")
    return "Unknown Partner"


def get_lang_file(email: str) -> str:
    team_name = get_subteam(email)
    if team_name:
        pi = PARTNER_IDENTITY.get(team_name, {})
        return pi.get("lang_file", "lang_en.txt")
    return "lang_en.txt"


def get_tl_channel(team_name: str) -> str:
    sc = SLACK_TEAM_CHANNELS.get(team_name, {})
    return sc.get("tl_channel", FALLBACK_SLACK_CHANNEL)


def get_eb_alert_channel(team_name: str) -> str:
    return EB_ALERTS["channels"].get(team_name, EB_ALERTS["fallback_channel"])


def get_slack_channel(email: str) -> str | None:
    """Devuelve el channel individual de una persona, o None si no tiene."""
    return SLACK_CHANNELS.get(email)


def get_slack_channel_by_name(name: str) -> str | None:
    """Busca channel por nombre de display (para pipelines que tienen nombre, no email)."""
    for email, info in HUBSPOT_OWNER_IDS.items():
        if info["name"] == name and email in SLACK_CHANNELS:
            return SLACK_CHANNELS[email]
    return None


def get_deal_team(partner_id: str | None, owner_email: str | None) -> str | None:
    """Assign team via partner association ID or owner email."""
    if partner_id and partner_id in PARTNER_OBJECT_MAP:
        return PARTNER_OBJECT_MAP[partner_id]
    if owner_email:
        teams = _EMAIL_TO_TEAMS.get(owner_email, [])
        if teams:
            return teams[0]
    return None


def get_owner_ids_for_team(team_name: str) -> list[str]:
    """Devuelve los HubSpot owner_ids de todos los miembros de un equipo."""
    if team_name in PARTNERS_ORGCHART:
        emails = PARTNERS_ORGCHART[team_name].get("pbd", set()) | PARTNERS_ORGCHART[team_name].get("pae", set())
    elif team_name in DIRECT_SALES_ES.get("teams", {}):
        emails = _collect_ae_emails(DIRECT_SALES_ES["teams"][team_name])
    elif team_name == "XL":
        emails = XL_SALES.get("ae", set()) | XL_SALES.get("sdr", set())
    else:
        return []
    return [HUBSPOT_OWNER_IDS[e]["id"] for e in emails if e in HUBSPOT_OWNER_IDS]


def get_email_by_owner_id(owner_id: str) -> str | None:
    """Convierte HubSpot owner_id a email."""
    return _OWNER_ID_TO_EMAIL.get(owner_id)


def get_display_name(email: str) -> str:
    """Devuelve el nombre de display de una persona. Fallback al email."""
    return _EMAIL_TO_NAME.get(email, email)
