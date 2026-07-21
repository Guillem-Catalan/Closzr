import { useState, useEffect } from "react";
import type { OrgPerson } from "./useOrgchart";
import { Avatar, getInitials, fmtMRR } from "../components";

const ROLES = ["Manager", "Country_Manager", "Head", "Director", "TL", "AE", "PAE", "PBD", "PDM", "SDR"];

export default function PersonPanel({
  person,
  saving,
  onSave,
  onClose,
}: {
  person: OrgPerson;
  saving: boolean;
  onSave: (email: string, changes: Partial<OrgPerson>) => Promise<boolean>;
  onClose: () => void;
}) {
  const [name, setName] = useState(person.full_name);
  const [role, setRole] = useState(person.role);
  const [targetMrr, setTargetMrr] = useState(String(person.target_mrr || 0));
  const [active, setActive] = useState(person.is_active);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setName(person.full_name);
    setRole(person.role);
    setTargetMrr(String(person.target_mrr || 0));
    setActive(person.is_active);
    setSaved(false);
  }, [person.email]);

  const dirty =
    name !== person.full_name ||
    role !== person.role ||
    Number(targetMrr) !== (person.target_mrr || 0) ||
    active !== person.is_active;

  async function handleSave() {
    const changes: Partial<OrgPerson> = {};
    if (name !== person.full_name) changes.full_name = name;
    if (role !== person.role) changes.role = role;
    if (Number(targetMrr) !== (person.target_mrr || 0)) changes.target_mrr = Number(targetMrr);
    if (active !== person.is_active) changes.is_active = active;

    const ok = await onSave(person.email, changes);
    if (ok) setSaved(true);
  }

  return (
    <div className="cz-person-panel">
      <div className="cz-person-panel__header">
        <Avatar initials={getInitials(person.full_name)} size={48} name={person.full_name} />
        <button className="cz-btn-soft cz-person-panel__close" onClick={onClose} title="Cerrar">
          ✕
        </button>
      </div>

      <div className="cz-person-panel__fields">
        <label className="cz-field">
          <span className="cz-field__label">Nombre</span>
          <input className="cz-field__input" value={name} onChange={e => setName(e.target.value)} />
        </label>

        <label className="cz-field">
          <span className="cz-field__label">Email</span>
          <input className="cz-field__input" value={person.email} readOnly disabled />
        </label>

        <label className="cz-field">
          <span className="cz-field__label">Rol</span>
          <select className="cz-native-select" value={role} onChange={e => setRole(e.target.value)}>
            {ROLES.map(r => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>

        <label className="cz-field">
          <span className="cz-field__label">Equipo</span>
          <input className="cz-field__input" value={person.team_name} readOnly disabled />
        </label>

        <label className="cz-field">
          <span className="cz-field__label">Reports to</span>
          <input className="cz-field__input" value={person.reports_to || "—"} readOnly disabled />
        </label>

        <label className="cz-field">
          <span className="cz-field__label">Target MRR</span>
          <div className="cz-field__row">
            <input
              className="cz-field__input"
              type="number"
              min={0}
              step={100}
              value={targetMrr}
              onChange={e => setTargetMrr(e.target.value)}
            />
            <span className="cz-field__hint">{fmtMRR(Number(targetMrr))}</span>
          </div>
        </label>

        <label className="cz-field">
          <span className="cz-field__label">HubSpot Owner ID</span>
          <input className="cz-field__input" value={person.hs_owner_id || "—"} readOnly disabled />
        </label>

        <label className="cz-field cz-field--toggle">
          <span className="cz-field__label">Activo</span>
          <button
            className={`cz-toggle ${active ? "cz-toggle--on" : ""}`}
            onClick={() => setActive(a => !a)}
            type="button"
          >
            <span className="cz-toggle__knob" />
          </button>
        </label>
      </div>

      <div className="cz-person-panel__actions">
        <button className="cz-btn-primary" disabled={!dirty || saving} onClick={handleSave}>
          {saving ? "Guardando..." : "Guardar"}
        </button>
        {saved && !dirty && <span className="cz-person-panel__saved">✓ Guardado</span>}
      </div>
    </div>
  );
}
