import { useState, useEffect } from "react";
import { Icon, Chip, Avatar, getInitials } from "../components";
import { supabase } from "../../data/supabase";
import { ALL_TABS, ALL_ROLES, ROLE_LABELS, ACCESS_LEVELS, SCOPE_OPTIONS, KNOWN_PARTNERS } from "../../display";
import type { Scope } from "../../permissions";

type OrgRow = {
  email: string;
  full_name: string;
  role: string;
  access_level: string;
  team_name: string;
  channel: string;
  visible_partners: string[];
  scope_general: Scope;
  scope_alerts: Scope;
  scope_pipeline: Scope;
  scope_benchmark: Scope;
  scope_performance: Scope;
  scope_forecast: Scope;
  scope_one_one: Scope;
  scope_team_analytics: Scope;
  scope_orgchart: Scope;
  scope_uplift: Scope;
  scope_insights: Scope;
  scope_admin: Scope;
  scope_partners: Scope;
  updated_at: string | null;
};

const SCOPE_COLS = ALL_TABS.map(t => `scope_${t.key}` as const);

const ACCESS_TONE: Record<string, string> = {
  admin: "indigo", manager: "violet", visitor: "amber", tree: "ink",
};

function PersonEditor({ person, onSave, onCancel }: { person: OrgRow; onSave: (p: OrgRow) => void; onCancel: () => void }) {
  const [p, setP] = useState<OrgRow>({ ...person });

  const set = (k: keyof OrgRow, v: any) => setP(prev => ({ ...prev, [k]: v }));

  const togglePartner = (partner: string) => {
    const current = p.visible_partners || [];
    set("visible_partners", current.includes(partner) ? current.filter(x => x !== partner) : [...current, partner]);
  };

  return (
    <div style={{ padding: "20px 22px", background: "var(--card-2)", borderBottom: "1px solid var(--line)", display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Row 1: Access level + Role */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div>
          <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Access Level</span>
          <select value={p.access_level} onChange={e => set("access_level", e.target.value)} className="cz-native-select" style={{ width: "100%" }}>
            {Object.entries(ACCESS_LEVELS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </div>
        <div>
          <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Rol</span>
          <select value={p.role} onChange={e => set("role", e.target.value)} className="cz-native-select" style={{ width: "100%" }}>
            {ALL_ROLES.map(r => <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>)}
          </select>
        </div>
      </div>

      {/* Row 2: Partners */}
      <div>
        <span className="eyebrow" style={{ display: "block", marginBottom: 6 }}>Partners visibles</span>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {KNOWN_PARTNERS.map(partner => {
            const active = (p.visible_partners || []).includes(partner);
            return (
              <button key={partner} onClick={() => togglePartner(partner)} style={{
                padding: "5px 12px", borderRadius: "var(--r-pill)", fontSize: 13, fontWeight: 600,
                border: "1px solid " + (active ? "var(--indigo)" : "var(--line-ink)"),
                background: active ? "var(--indigo-tint)" : "white",
                color: active ? "var(--indigo)" : "var(--ink-2)",
                cursor: "pointer",
              }}>{partner}</button>
            );
          })}
        </div>
      </div>

      {/* Row 3: Scopes per view */}
      <div>
        <span className="eyebrow" style={{ display: "block", marginBottom: 6 }}>Scope por vista</span>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
          {ALL_TABS.map(tab => {
            const col = `scope_${tab.key}` as keyof OrgRow;
            const val = (p[col] as string) || "none";
            return (
              <div key={tab.key} className="cz-card" style={{ padding: "12px 14px" }}>
                <span style={{ fontSize: 13, fontWeight: 700, display: "block", marginBottom: 6 }}>{tab.label}</span>
                <select value={val} onChange={e => set(col, e.target.value)} className="cz-native-select" style={{ width: "100%", fontSize: 12 }}>
                  {SCOPE_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
            );
          })}
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
        <button className="cz-btn-soft" onClick={onCancel}>Cancelar</button>
        <button className="cz-btn-primary" onClick={() => onSave(p)}>Guardar</button>
      </div>
    </div>
  );
}

export default function AdminView() {
  const [people, setPeople] = useState<OrgRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingEmail, setEditingEmail] = useState<string | null>(null);
  const [filterRole, setFilterRole] = useState("");
  const [filterTeam, setFilterTeam] = useState("");
  const [filterAccess, setFilterAccess] = useState("");

  useEffect(() => {
    supabase
      .from("orgchart")
      .select("email,full_name,role,access_level,team_name,channel,visible_partners," + SCOPE_COLS.join(",") + ",updated_at")
      .order("full_name")
      .then(({ data }) => {
        setPeople((data || []) as unknown as OrgRow[]);
        setLoading(false);
      });
  }, []);

  const handleSave = async (p: OrgRow) => {
    const updates: Record<string, unknown> = {
      role: p.role,
      access_level: p.access_level,
      visible_partners: p.visible_partners || [],
    };
    for (const col of SCOPE_COLS) {
      updates[col] = (p as any)[col] || "none";
    }

    const { error } = await supabase.from("orgchart").update(updates).eq("email", p.email);
    if (!error) {
      setPeople(prev => prev.map(x => x.email === p.email ? p : x));
      setEditingEmail(null);
    }
  };

  const teams = [...new Set(people.map(p => p.team_name))].sort();

  const filtered = people.filter(p => {
    if (filterRole && p.role !== filterRole) return false;
    if (filterTeam && p.team_name !== filterTeam) return false;
    if (filterAccess && p.access_level !== filterAccess) return false;
    return true;
  });

  if (loading) return <p style={{ color: "var(--ink-3)", padding: 40 }}>Cargando personas...</p>;

  return (
    <div className="cz-fc">
      <div className="cz-toolbar" style={{ marginBottom: 16 }}>
        <div className="cz-tb-title">
          <h2 className="display">Admin</h2>
          <span className="cz-tb-meta">{filtered.length} de {people.length} personas</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          <select value={filterAccess} onChange={e => setFilterAccess(e.target.value)} className="cz-native-select" style={{ fontSize: 13 }}>
            <option value="">Todos los niveles</option>
            {Object.entries(ACCESS_LEVELS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
          <select value={filterRole} onChange={e => setFilterRole(e.target.value)} className="cz-native-select" style={{ fontSize: 13 }}>
            <option value="">Todos los roles</option>
            {ALL_ROLES.map(r => <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>)}
          </select>
          <select value={filterTeam} onChange={e => setFilterTeam(e.target.value)} className="cz-native-select" style={{ fontSize: 13 }}>
            <option value="">Todos los equipos</option>
            {teams.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      <div className="cz-card" style={{ padding: 0, overflow: "hidden" }}>
        {filtered.map(p => (
          <div key={p.email}>
            <div style={{
              display: "grid", gridTemplateColumns: "40px 1fr 90px 90px 1fr 40px",
              gap: 12, padding: "12px 18px", alignItems: "center",
              borderBottom: "1px solid var(--line-2)", cursor: "pointer",
              background: editingEmail === p.email ? "var(--indigo-tint-2)" : "transparent",
            }} onClick={() => setEditingEmail(editingEmail === p.email ? null : p.email)}>
              <Avatar initials={getInitials(p.full_name || p.email)} size={32} name={p.full_name} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{p.full_name || p.email}</div>
                <div style={{ fontSize: 12, color: "var(--ink-3)" }}>{p.email}</div>
              </div>
              <div><Chip tone={ACCESS_TONE[p.access_level] || "ink"}>{ACCESS_LEVELS[p.access_level] || p.access_level}</Chip></div>
              <div><Chip tone="ink">{ROLE_LABELS[p.role] || p.role}</Chip></div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                <Chip tone="ink" style={{ fontSize: 10, padding: "1px 6px" }}>{p.team_name}</Chip>
                {(p.visible_partners || []).map(partner => (
                  <Chip key={partner} tone="blue" style={{ fontSize: 10, padding: "1px 6px" }}>{partner}</Chip>
                ))}
              </div>
              <div><Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: editingEmail === p.email ? "none" : "rotate(-90deg)", transition: "transform .18s" }} /></div>
            </div>
            {editingEmail === p.email && (
              <PersonEditor person={p} onSave={handleSave} onCancel={() => setEditingEmail(null)} />
            )}
          </div>
        ))}
        {filtered.length === 0 && (
          <p style={{ padding: 20, color: "var(--ink-3)", textAlign: "center" }}>No hay personas con estos filtros</p>
        )}
      </div>
    </div>
  );
}
