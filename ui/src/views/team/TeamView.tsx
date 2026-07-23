import { useRef, useState, useEffect, useCallback } from "react";
import { usePermissions } from "../../permissions";
import { supabase } from "../../data/supabase";
import { useOrgchart } from "./useOrgchart";
import type { OrgPerson } from "./useOrgchart";
import { useDragCard } from "./useDragLine";
import type { DragResult } from "./useDragLine";
import OrgTree from "./OrgTree";
import PersonPanel from "./PersonPanel";
import ReassignWizard from "./ReassignWizard";
import { useReassign } from "./useReassign";
import { getInitials } from "../components";

const DRAG_THRESHOLD = 4;

export default function TeamView() {
  const { profile } = usePermissions();
  const email = profile?.email || "";
  const role = profile?.role || "PAE";

  const {
    groups,
    loading,
    selected,
    setSelected,
    updatePerson,
    saving,
    canEdit,
    editing,
    startEditing,
    discardChanges,
    pendingChanges,
    editScope,
    defaultExpanded,
    allRows,
    disconnected,
    disconnectPerson,
    reconnectChildren,
    addPerson,
    movePerson,
    commitChanges,
  } = useOrgchart(email, role);

  const [addParent, setAddParent] = useState<string | null>(null);
  const [addForm, setAddForm] = useState({ email: "", full_name: "", hs_owner_id: "" });
  const [addError, setAddError] = useState("");
  const [addLooking, setAddLooking] = useState(false);

  const reassign = useReassign();

  const [cutDialog, setCutDialog] = useState<{
    email: string; fullName: string; dealCount: number; loading: boolean;
  } | null>(null);

  const handleCutClick = useCallback(async (personEmail: string) => {
    const person = allRows.find((r: OrgPerson) => r.email === personEmail);
    if (!person) return;
    setCutDialog({ email: personEmail, fullName: person.full_name, dealCount: -1, loading: true });

    const { data, count } = await supabase
      .from("deal_ui")
      .select("deal_id", { count: "exact", head: true })
      .eq("pae", person.full_name)
      .in("macro_stage", ["demo", "evaluating", "closing"]);

    setCutDialog(prev => prev ? { ...prev, dealCount: count ?? 0, loading: false } : null);
  }, [allRows]);

  const handleCutConfirm = useCallback(() => {
    if (!cutDialog) return;
    disconnectPerson(cutDialog.email);
    setCutDialog(null);
  }, [cutDialog, disconnectPerson]);

  const handleCutReassign = useCallback(() => {
    if (!cutDialog) return;
    const person = allRows.find((r: OrgPerson) => r.email === cutDialog.email);
    if (!person) return;
    setCutDialog(null);
    reassign.openWizard();
    setTimeout(() => {
      reassign.selectPerson(cutDialog.email, person.team_name, person.full_name);
    }, 50);
  }, [cutDialog, allRows, reassign]);

  const [moveDialog, setMoveDialog] = useState<{
    targetEmail: string; newParentEmail: string;
  } | null>(null);
  const [saveDialog, setSaveDialog] = useState(false);
  const [saveConfirmStep, setSaveConfirmStep] = useState<"briefing" | "confirm">("briefing");
  const [saveError, setSaveError] = useState("");

  const handleAddClick = useCallback((parentEmail: string) => {
    setAddParent(parentEmail);
    setAddForm({ email: "", full_name: "", hs_owner_id: "" });
    setAddError("");
    setAddLooking(false);
  }, []);

  const lookupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleEmailChange = useCallback((value: string) => {
    setAddForm(f => ({ ...f, email: value }));
    setAddError("");

    if (lookupTimerRef.current) clearTimeout(lookupTimerRef.current);

    const trimmed = value.trim().toLowerCase();
    if (!trimmed || !trimmed.includes("@")) return;

    lookupTimerRef.current = setTimeout(async () => {
      setAddLooking(true);
      try {
        const { data } = await supabase.functions.invoke("orgchart-ops", {
          body: { action: "lookup", email: trimmed },
        });
        if (data?.found) {
          setAddForm(f => ({
            ...f,
            full_name: f.full_name || data.full_name || "",
            hs_owner_id: data.hs_owner_id || "",
          }));
        }
      } catch {}
      setAddLooking(false);
    }, 600);
  }, []);

  const handleAddSubmit = useCallback(() => {
    if (!addParent) return;
    const trimmedEmail = addForm.email.trim().toLowerCase();
    if (!trimmedEmail) { setAddError("El email es obligatorio."); return; }

    const existing = allRows.find((r: OrgPerson) => r.email === trimmedEmail);
    if (existing) {
      const tlRow = allRows.find((r: OrgPerson) => r.email === existing.reports_to);
      setAddError(
        `${existing.full_name} ya está en el equipo de ${existing.team_name}` +
        (tlRow ? ` bajo ${tlRow.full_name}` : "") +
        `. Habla con tu superior para gestionar el cambio.`
      );
      return;
    }

    const parent = allRows.find((r: OrgPerson) => r.email === addParent);
    const name = addForm.full_name.trim() || trimmedEmail.split("@")[0].replace(/[._-]/g, " ");
    addPerson({
      email: trimmedEmail,
      full_name: name,
      role: "AE",
      hs_owner_id: addForm.hs_owner_id || null,
      channel: parent?.channel || "",
      team_name: parent?.team_name || "",
      reports_to: addParent,
      target_mrr: 0,
    });
    setAddParent(null);
  }, [addParent, addForm, allRows, addPerson]);

  const handleMoveConfirm = useCallback(() => {
    if (!moveDialog) return;
    movePerson(moveDialog.targetEmail, moveDialog.newParentEmail);
    setMoveDialog(null);
  }, [moveDialog, movePerson]);

  const handleSaveClick = useCallback(() => {
    setSaveDialog(true);
    setSaveConfirmStep("briefing");
    setSaveError("");
  }, []);

  const handleSaveConfirm = useCallback(async () => {
    const ok = await commitChanges();
    if (ok) {
      setSaveDialog(false);
    } else {
      setSaveError("Error al guardar. Inténtalo de nuevo.");
    }
  }, [commitChanges]);

  const handleDragEnd = useCallback((result: DragResult) => {
    if (result.type === "move" && result.targetEmail) {
      setMoveDialog({ targetEmail: result.email, newParentEmail: result.targetEmail });
    } else if (result.type === "disconnect" && result.email) {
      reconnectChildren(result.email);
    }
  }, [reconnectChildren]);

  const { drag, onPointerDown } = useDragCard(handleDragEnd);

  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragging = useRef(false);
  const didDrag = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });
  const startMouse = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.ctrlKey || e.metaKey) {
        const delta = -e.deltaY * 0.01;
        setZoom(z => Math.max(0.2, Math.min(3, z + delta)));
      } else if (e.shiftKey) {
        setPan(p => ({ x: p.x - e.deltaY, y: p.y }));
      } else {
        setPan(p => ({ x: p.x - e.deltaX, y: p.y - e.deltaY }));
      }
    };

    const baseZoom = { current: 1 };
    const onGestureStart = (e: Event) => {
      e.preventDefault();
      setZoom(z => { baseZoom.current = z; return z; });
    };
    const onGestureChange = (e: Event) => {
      e.preventDefault();
      const ge = e as Event & { scale: number };
      setZoom(Math.max(0.2, Math.min(3, baseZoom.current * ge.scale)));
    };
    const onGestureEnd = (e: Event) => e.preventDefault();

    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("gesturestart", onGestureStart, { passive: false } as any);
    el.addEventListener("gesturechange", onGestureChange, { passive: false } as any);
    el.addEventListener("gestureend", onGestureEnd, { passive: false } as any);
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("gesturestart", onGestureStart);
      el.removeEventListener("gesturechange", onGestureChange);
      el.removeEventListener("gestureend", onGestureEnd);
    };
  }, []);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    dragging.current = true;
    didDrag.current = false;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    startMouse.current = { x: e.clientX, y: e.clientY };
  }, []);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging.current) return;
    const dx = e.clientX - lastMouse.current.x;
    const dy = e.clientY - lastMouse.current.y;
    const totalDx = Math.abs(e.clientX - startMouse.current.x);
    const totalDy = Math.abs(e.clientY - startMouse.current.y);

    if (totalDx > DRAG_THRESHOLD || totalDy > DRAG_THRESHOLD) {
      didDrag.current = true;
    }

    if (didDrag.current) {
      setPan(p => ({ x: p.x + dx, y: p.y + dy }));
    }
    lastMouse.current = { x: e.clientX, y: e.clientY };
  }, []);

  const stopDrag = useCallback(() => { dragging.current = false; }, []);

  const onClickCapture = useCallback((e: React.MouseEvent) => {
    if (didDrag.current) {
      e.stopPropagation();
      didDrag.current = false;
    }
  }, []);

  if (loading) {
    return (
      <div className="cz-team-view">
        <div className="cz-toolbar">
          <h2 className="cz-tb-title">Orgchart</h2>
        </div>
        <p style={{ color: "var(--ink-3)", padding: 24 }}>Cargando orgchart...</p>
      </div>
    );
  }

  const dragPerson = drag ? allRows.find((r: OrgPerson) => r.email === drag.email) : null;

  return (
    <div className={`cz-team-view${editing ? " cz-team-view--editing" : ""}`}>
      <div className={`cz-toolbar${editing ? " cz-toolbar--editing" : ""}`}>
        <h2 className="cz-tb-title">Orgchart</h2>

        {!editing && canEdit && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            <button className="cz-btn-soft" onClick={reassign.openWizard}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 10 20 15 15 20" />
                <path d="M4 4v7a4 4 0 004 4h12" />
              </svg>
              Reasignar
            </button>
            <button className="cz-btn-soft" onClick={startEditing}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
              Edit
            </button>
          </div>
        )}

        {editing && (
          <div className="cz-edit-actions">
            <button className="cz-btn-soft" onClick={discardChanges}>
              Cancelar
            </button>
            {pendingChanges.length > 0 && (
              <span className="cz-edit-badge">
                {pendingChanges.length} cambio{pendingChanges.length > 1 ? "s" : ""}
              </span>
            )}
            <button
              className="cz-btn-primary"
              disabled={pendingChanges.length === 0 || saving}
              onClick={handleSaveClick}
            >
              {saving ? "Aplicando..." : "Confirmar"}
            </button>
          </div>
        )}
      </div>

      <div className="cz-team-view__body">
        <div
          ref={containerRef}
          className="cz-team-view__tree"
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={stopDrag}
          onMouseLeave={stopDrag}
          onClickCapture={onClickCapture}
        >
          <div
            className="cz-team-view__canvas"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: "0 0",
            }}
          >
            <OrgTree
              groups={groups}
              selectedEmail={editing ? null : selected?.email || null}
              onSelect={editing ? () => {} : setSelected}
              editing={editing}
              editScope={editScope}
              defaultExpanded={defaultExpanded}
              disconnected={disconnected}
              dragEmail={drag?.email || null}
              onCardPointerDown={onPointerDown}
              onAddClick={handleAddClick}
              onCutClick={handleCutClick}
            />
          </div>
        </div>

        {selected && !editing && (
          <div className="cz-team-view__panel">
            <PersonPanel
              person={selected}
              saving={saving}
              onSave={updatePerson}
              onClose={() => setSelected(null)}
            />
          </div>
        )}
      </div>

      {drag && dragPerson && (
        <>
          {drag.targetEmail && (
            <svg className="cz-drag-svg">
              <path
                className="cz-drag-line"
                d={`M ${drag.x} ${drag.y} Q ${(drag.x + drag.targetX) / 2} ${Math.min(drag.y, drag.targetY) - 40} ${drag.targetX} ${drag.targetY}`}
              />
            </svg>
          )}
          <div className="cz-ot-ghost" style={{ left: drag.x + 14, top: drag.y - 16 }}>
            <span className="cz-ot-ghost__avatar">{getInitials(dragPerson.full_name)}</span>
            <span className="cz-ot-ghost__name">{dragPerson.full_name}</span>
          </div>
        </>
      )}

      {addParent && (
        <div className="cz-overlay" onClick={() => setAddParent(null)}>
          <div className="cz-edit-dialog cz-edit-dialog--form" onClick={e => e.stopPropagation()}>
            <h3 className="cz-edit-dialog__title">Añadir persona</h3>
            <p className="cz-edit-dialog__text">
              Se añadirá bajo {allRows.find((r: OrgPerson) => r.email === addParent)?.full_name || addParent}
            </p>

            {addError && <div className="cz-edit-dialog__error">{addError}</div>}

            <div className="cz-edit-dialog__fields">
              <label className="cz-field">
                <span className="cz-field__label">Email *</span>
                <input
                  className="cz-field__input"
                  type="email"
                  placeholder="nombre@empresa.com"
                  value={addForm.email}
                  onChange={e => handleEmailChange(e.target.value)}
                  autoFocus
                />
                {addLooking && <span className="cz-field__hint">Buscando en HubSpot...</span>}
                {addForm.hs_owner_id && <span className="cz-field__hint cz-field__hint--ok">HubSpot ID: {addForm.hs_owner_id}</span>}
              </label>
              <label className="cz-field">
                <span className="cz-field__label">Nombre {addForm.full_name ? "" : "(se auto-rellena)"}</span>
                <input
                  className="cz-field__input"
                  placeholder="Se buscará automáticamente"
                  value={addForm.full_name}
                  onChange={e => setAddForm(f => ({ ...f, full_name: e.target.value }))}
                />
              </label>
            </div>

            <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
              <button className="cz-edit-dialog__btn" onClick={() => setAddParent(null)}>
                Cancelar
              </button>
              <button className="cz-edit-dialog__btn cz-edit-dialog__btn--primary" onClick={handleAddSubmit}>
                Añadir
              </button>
            </div>
          </div>
        </div>
      )}

      {cutDialog && (
        <div className="cz-overlay" onClick={() => setCutDialog(null)}>
          <div className="cz-edit-dialog" onClick={e => e.stopPropagation()}>
            {cutDialog.loading ? (
              <>
                <h3 className="cz-edit-dialog__title">Comprobando deals...</h3>
                <p className="cz-edit-dialog__text">Verificando si {cutDialog.fullName} tiene deals activos</p>
              </>
            ) : cutDialog.dealCount > 0 ? (
              <>
                <div className="cz-edit-dialog__icon cz-edit-dialog__icon--warn">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                  </svg>
                </div>
                <h3 className="cz-edit-dialog__title">No se puede sacar del equipo</h3>
                <p className="cz-edit-dialog__text">
                  <strong>{cutDialog.fullName}</strong> tiene <strong>{cutDialog.dealCount} deal{cutDialog.dealCount > 1 ? "s" : ""} activo{cutDialog.dealCount > 1 ? "s" : ""}</strong>. Reasígnalos primero.
                </p>
                <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
                  <button className="cz-edit-dialog__btn" onClick={() => setCutDialog(null)}>Cancelar</button>
                  <button className="cz-edit-dialog__btn cz-edit-dialog__btn--primary" onClick={handleCutReassign}>
                    Reasignar deals
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="cz-edit-dialog__icon" style={{ background: "var(--red-tint)", color: "var(--red)" }}>
                  <span style={{ fontSize: 22 }}>✂️</span>
                </div>
                <h3 className="cz-edit-dialog__title">¿Quieres que deje el equipo?</h3>
                <p className="cz-edit-dialog__text">
                  <strong>{cutDialog.fullName}</strong> no tiene deals activos asignados. Se puede sacar del equipo de forma segura.
                </p>
                <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
                  <button className="cz-edit-dialog__btn" onClick={() => setCutDialog(null)}>Cancelar</button>
                  <button className="cz-edit-dialog__btn cz-edit-dialog__btn--warn" onClick={handleCutConfirm}>
                    Sí, que deje el equipo
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {saveDialog && (() => {
        const moves = pendingChanges.filter(c => c.type === "move") as { type: "move"; email: string; oldReportsTo: string | null; newReportsTo: string }[];
        const disconnects = pendingChanges.filter(c => c.type === "disconnect") as { type: "disconnect"; email: string }[];
        const adds = pendingChanges.filter(c => c.type === "add") as { type: "add"; person: Partial<OrgPerson> }[];
        const getName = (e: string) => allRows.find((r: OrgPerson) => r.email === e)?.full_name || e;
        const getTeam = (e: string) => allRows.find((r: OrgPerson) => r.email === e)?.team_name || "";

        if (saveConfirmStep === "briefing") return (
          <div className="cz-overlay" onClick={() => setSaveDialog(false)}>
            <div className="cz-edit-dialog cz-edit-dialog--briefing" onClick={e => e.stopPropagation()}>
              <h3 className="cz-edit-dialog__title">Resumen de cambios</h3>
              <div className="cz-confirm-briefing">
                {moves.map((m, i) => (
                  <div key={`m${i}`} className="cz-confirm-item">
                    <span className="cz-confirm-item__icon cz-confirm-item__icon--move">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="15 10 20 15 15 20"/><path d="M4 4v7a4 4 0 004 4h12"/></svg>
                    </span>
                    <span><strong>{getName(m.email)}</strong> → equipo de <strong>{getName(m.newReportsTo)}</strong>{getTeam(m.newReportsTo) ? ` (${getTeam(m.newReportsTo)})` : ""}</span>
                  </div>
                ))}
                {adds.map((a, i) => (
                  <div key={`a${i}`} className="cz-confirm-item">
                    <span className="cz-confirm-item__icon cz-confirm-item__icon--add">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    </span>
                    <span><strong>{a.person.full_name || a.person.email}</strong> se añade a <strong>{a.person.team_name}</strong></span>
                  </div>
                ))}
                {disconnects.map((d, i) => (
                  <div key={`d${i}`} className="cz-confirm-item">
                    <span className="cz-confirm-item__icon cz-confirm-item__icon--remove">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    </span>
                    <span><strong>{getName(d.email)}</strong> deja el equipo</span>
                  </div>
                ))}
              </div>
              {saveError && <div className="cz-edit-dialog__error">{saveError}</div>}
              <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
                <button className="cz-edit-dialog__btn" onClick={() => setSaveDialog(false)}>Cancelar</button>
                <button className="cz-edit-dialog__btn cz-edit-dialog__btn--primary" onClick={() => setSaveConfirmStep("confirm")}>
                  Confirmar cambios
                </button>
              </div>
            </div>
          </div>
        );

        return (
          <div className="cz-overlay" onClick={() => setSaveDialog(false)}>
            <div className="cz-edit-dialog" onClick={e => e.stopPropagation()}>
              <div className="cz-edit-dialog__icon cz-edit-dialog__icon--warn">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
              </div>
              <h3 className="cz-edit-dialog__title">¿Estás seguro?</h3>
              <p className="cz-edit-dialog__text">
                Se aplicarán {pendingChanges.length} cambio{pendingChanges.length > 1 ? "s" : ""} al orgchart de producción. Esta acción no se puede deshacer.
              </p>
              {saveError && <div className="cz-edit-dialog__error">{saveError}</div>}
              <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
                <button className="cz-edit-dialog__btn" onClick={() => setSaveConfirmStep("briefing")} disabled={saving}>Volver</button>
                <button className="cz-edit-dialog__btn cz-edit-dialog__btn--warn" onClick={handleSaveConfirm} disabled={saving}>
                  {saving ? "Aplicando..." : "Sí, aplicar cambios"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {reassign.open && (
        <ReassignWizard
          step={reassign.step}
          allRows={allRows}
          selectedEmail={reassign.selectedEmail}
          selectedFullName={reassign.selectedFullName}
          deals={reassign.deals}
          reps={reassign.reps}
          loadingDeals={reassign.loadingDeals}
          loadingReps={reassign.loadingReps}
          saving={reassign.saving}
          error={reassign.error}
          results={reassign.results}
          someAssigned={reassign.someAssigned}
          onSelectPerson={reassign.selectPerson}
          onAssignDeal={reassign.assignDeal}
          onGoBack={reassign.goBack}
          onGoToSummary={reassign.goToSummary}
          onGoToSafetyConfirm={reassign.goToSafetyConfirm}
          onConfirm={reassign.confirmReassign}
          onClose={reassign.closeWizard}
        />
      )}

      {moveDialog && (() => {
        const target = allRows.find((r: OrgPerson) => r.email === moveDialog.targetEmail);
        const newParent = allRows.find((r: OrgPerson) => r.email === moveDialog.newParentEmail);
        const oldParent = target ? allRows.find((r: OrgPerson) => r.email === target.reports_to) : null;
        return (
          <div className="cz-overlay" onClick={() => setMoveDialog(null)}>
            <div className="cz-edit-dialog" onClick={e => e.stopPropagation()}>
              <div className="cz-edit-dialog__icon cz-edit-dialog__icon--indigo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="15 10 20 15 15 20" />
                  <path d="M4 4v7a4 4 0 004 4h12" />
                </svg>
              </div>
              <h3 className="cz-edit-dialog__title">Mover persona</h3>
              <p className="cz-edit-dialog__text">
                Vas a mover a <strong>{target?.full_name || moveDialog.targetEmail}</strong>
                {oldParent ? ` del equipo de ${oldParent.full_name}` : ""}
                {" "}al equipo de <strong>{newParent?.full_name || moveDialog.newParentEmail}</strong>.
              </p>
              <div className="cz-edit-dialog__actions cz-edit-dialog__actions--row">
                <button className="cz-edit-dialog__btn" onClick={() => setMoveDialog(null)}>
                  Cancelar
                </button>
                <button className="cz-edit-dialog__btn cz-edit-dialog__btn--primary" onClick={handleMoveConfirm}>
                  Mover
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
