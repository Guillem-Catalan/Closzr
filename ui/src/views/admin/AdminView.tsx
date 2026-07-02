import { useState, useEffect } from "react";
import { Icon, Chip, Avatar, getInitials } from "../components";
import { supabase } from "../../data/supabase";
import type { TabScope } from "../../permissions";
import { ALL_TABS, ADMIN_ROLES, ADMIN_SCOPES, getAllTeamNames } from "../../display";

type UserRow = {
  id: string;
  email: string;
  name: string;
  team: string;
  role: string;
  visible_teams: string[];
  visible_reps: string[];
  tab_permissions: Record<string, TabScope>;
  last_login: string | null;
};

const ROLES = ADMIN_ROLES;
const SCOPES = ADMIN_SCOPES;
const CONFIG_TEAMS = getAllTeamNames();

function UserEditor({ user, onSave, onCancel }: { user: UserRow; onSave: (u: UserRow) => void; onCancel: () => void }) {
  const [u, setU] = useState<UserRow>({ ...user, visible_teams: [...new Set(user.visible_teams || [])] });

  const setField = (k: keyof UserRow, v: any) => setU(prev => ({ ...prev, [k]: v }));
  const setTabPerm = (tab: string, field: string, value: any) => {
    setU(prev => ({
      ...prev,
      tab_permissions: {
        ...prev.tab_permissions,
        [tab]: { ...(prev.tab_permissions[tab] || { enabled: true, scope: "all" }), [field]: value },
      },
    }));
  };

  const toggleTeam = (team: string) => {
    const teams = u.visible_teams || [];
    setField("visible_teams", teams.includes(team) ? teams.filter(t => t !== team) : [...teams, team]);
  };

  return (
    <div style={{ padding: "20px 22px", background: "var(--card-2)", borderBottom: "1px solid var(--line)", display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div>
          <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Nombre</span>
          <input value={u.name} onChange={e => setField("name", e.target.value)} style={{ width: "100%", padding: "8px 12px", border: "1px solid var(--line-ink)", borderRadius: "var(--r-sm)", fontSize: 14 }} />
        </div>
        <div>
          <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>Rol</span>
          <select value={u.role} onChange={e => setField("role", e.target.value)} className="cz-native-select" style={{ width: "100%" }}>
            {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </div>

      <div>
        <span className="eyebrow" style={{ display: "block", marginBottom: 6 }}>Equipos visibles</span>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {CONFIG_TEAMS.map(t => (
            <button key={t} onClick={() => toggleTeam(t)} style={{
              padding: "5px 12px", borderRadius: "var(--r-pill)", fontSize: 13, fontWeight: 600,
              border: "1px solid " + ((u.visible_teams || []).includes(t) ? "var(--indigo)" : "var(--line-ink)"),
              background: (u.visible_teams || []).includes(t) ? "var(--indigo-tint)" : "white",
              color: (u.visible_teams || []).includes(t) ? "var(--indigo)" : "var(--ink-2)",
              cursor: "pointer",
            }}>{t}</button>
          ))}
        </div>
      </div>

      <div>
        <span className="eyebrow" style={{ display: "block", marginBottom: 6 }}>Permisos por pestaña</span>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
          {ALL_TABS.map(tab => {
            const perm = u.tab_permissions?.[tab.key] || { enabled: true, scope: "all" };
            return (
              <div key={tab.key} className="cz-card" style={{ padding: "12px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 700 }}>{tab.label}</span>
                  <button onClick={() => setTabPerm(tab.key, "enabled", !perm.enabled)} style={{
                    width: 36, height: 20, borderRadius: 99, border: "none", cursor: "pointer",
                    background: perm.enabled ? "var(--green)" : "var(--line-ink)",
                    position: "relative",
                  }}>
                    <span style={{
                      position: "absolute", top: 2, left: perm.enabled ? 18 : 2,
                      width: 16, height: 16, borderRadius: 99, background: "white",
                      transition: "left .15s", boxShadow: "var(--sh-xs)",
                    }} />
                  </button>
                </div>
                {perm.enabled && (
                  <select value={perm.scope} onChange={e => setTabPerm(tab.key, "scope", e.target.value)} className="cz-native-select" style={{ width: "100%", fontSize: 12 }}>
                    {SCOPES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
        <button className="cz-btn-soft" onClick={onCancel}>Cancelar</button>
        <button className="cz-btn-primary" onClick={() => onSave({ ...u, visible_teams: [...new Set(u.visible_teams || [])] })}>Guardar</button>
      </div>
    </div>
  );
}

export default function AdminView() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [filterRole, setFilterRole] = useState("");
  const [filterTeam, setFilterTeam] = useState("");

  useEffect(() => {
    supabase.from("users").select("*").order("created_at").then(({ data }) => {
      setUsers((data || []).map((u: any) => ({ ...u, visible_teams: [...new Set(u.visible_teams || [])] })));
      setLoading(false);
    });
  }, []);

  const handleSave = async (u: UserRow) => {
    const { error } = await supabase.from("users").update({
      name: u.name,
      role: u.role,
      visible_teams: [...new Set(u.visible_teams || [])],
      visible_reps: u.visible_reps,
      tab_permissions: u.tab_permissions,
    }).eq("id", u.id);

    if (!error) {
      setUsers(prev => prev.map(p => p.id === u.id ? u : p));
      setEditingId(null);
    }
  };

  const filtered = users.filter(u => {
    if (filterRole && u.role !== filterRole) return false;
    if (filterTeam && !(u.visible_teams || []).includes(filterTeam)) return false;
    return true;
  });

  if (loading) return <p style={{ color: "var(--ink-3)", padding: 40 }}>Cargando usuarios...</p>;

  return (
    <div className="cz-fc">
      <div className="cz-toolbar" style={{ marginBottom: 16 }}>
        <div className="cz-tb-title">
          <h2 className="display">Admin</h2>
          <span className="cz-tb-meta">{filtered.length} de {users.length} usuarios</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          <select value={filterRole} onChange={e => setFilterRole(e.target.value)} className="cz-native-select" style={{ fontSize: 13 }}>
            <option value="">Todos los roles</option>
            {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <select value={filterTeam} onChange={e => setFilterTeam(e.target.value)} className="cz-native-select" style={{ fontSize: 13 }}>
            <option value="">Todos los equipos</option>
            {CONFIG_TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      <div className="cz-card" style={{ padding: 0, overflow: "hidden" }}>
        {filtered.map(u => (
          <div key={u.id}>
            <div style={{
              display: "grid", gridTemplateColumns: "40px 1fr 100px 1fr 90px 40px",
              gap: 12, padding: "12px 18px", alignItems: "center",
              borderBottom: "1px solid var(--line-2)", cursor: "pointer",
              background: editingId === u.id ? "var(--indigo-tint-2)" : "transparent",
            }} onClick={() => setEditingId(editingId === u.id ? null : u.id)}>
              <Avatar initials={getInitials(u.name || u.email)} size={32} name={u.name} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{u.name || u.email}</div>
                <div style={{ fontSize: 12, color: "var(--ink-3)" }}>{u.email}</div>
              </div>
              <div><Chip tone={u.role === "Admin" ? "indigo" : u.role === "Manager" ? "violet" : u.role === "Director" ? "violet" : u.role === "TL" ? "blue" : "ink"}>{u.role}</Chip></div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {(u.visible_teams || []).map(t => <Chip key={t} tone="ink" style={{ fontSize: 10, padding: "1px 6px" }}>{t}</Chip>)}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-3)" }}>{u.last_login ? new Date(u.last_login).toLocaleDateString("es-ES") : "nunca"}</div>
              <div><Icon name="chevDown" size={14} style={{ color: "var(--ink-3)", transform: editingId === u.id ? "none" : "rotate(-90deg)", transition: "transform .18s" }} /></div>
            </div>
            {editingId === u.id && (
              <UserEditor user={u} onSave={handleSave} onCancel={() => setEditingId(null)} />
            )}
          </div>
        ))}
        {filtered.length === 0 && (
          <p style={{ padding: 20, color: "var(--ink-3)", textAlign: "center" }}>No hay usuarios con estos filtros</p>
        )}
      </div>
    </div>
  );
}
