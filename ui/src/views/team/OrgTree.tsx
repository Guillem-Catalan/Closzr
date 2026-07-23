import { useState, useCallback, useRef, useEffect } from "react";
import type { OrgNode, OrgPerson, OrgGroup } from "./useOrgchart";
import { Avatar, getInitials } from "../components";

function HNode({
  node,
  selectedEmail,
  onSelect,
  expanded,
  onToggle,
  editing,
  editScope,
  disconnected,
  dragEmail,
  onCardPointerDown,
  onAddClick,
  onCutClick,
  isChild,
}: {
  node: OrgNode;
  selectedEmail: string | null;
  onSelect: (p: OrgPerson) => void;
  expanded: Set<string>;
  onToggle: (email: string) => void;
  editing: boolean;
  editScope?: Set<string>;
  disconnected?: Set<string>;
  dragEmail?: string | null;
  onCardPointerDown?: (e: React.PointerEvent, email: string) => void;
  onAddClick?: (parentEmail: string) => void;
  onCutClick?: (email: string) => void;
  isChild?: boolean;
}) {
  const isSelected = selectedEmail === node.email;
  const hasChildren = node.children.length > 0;
  const isExpanded = expanded.has(node.email);
  const isEditable = editing && editScope?.has(node.email);
  const isDisconnected = disconnected?.has(node.email);
  const isDragging = dragEmail === node.email;
  const showPlus = editing && isEditable && !isDisconnected;
  const showCut = editing && isEditable && !isDisconnected && isChild;

  const branchClass = [
    "cz-ot-branch",
    isDisconnected ? "cz-ot-branch--disconnected" : "",
  ].filter(Boolean).join(" ");

  const cardClass = [
    "cz-ot-card",
    isSelected ? "cz-ot-card--sel" : "",
    !node.is_active ? "cz-ot-card--off" : "",
    isEditable ? "cz-ot-card--editable" : "",
    isDisconnected ? "cz-ot-card--disconnected" : "",
    isDragging ? "cz-ot-card--dragging" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={branchClass}>
      {showCut && (
        <button
          className="cz-ot-cut"
          onClick={(e) => { e.stopPropagation(); onCutClick?.(node.email); }}
          title="Sacar del equipo"
        >✂️</button>
      )}
      <div
        className={cardClass}
        onClick={() => !editing && onSelect(node)}
        data-email={node.email}
        onPointerDown={isEditable ? (e) => onCardPointerDown?.(e, node.email) : undefined}
      >
        <Avatar initials={getInitials(node.full_name)} size={28} name={node.full_name} />
        <span className="cz-ot-card__name">{node.full_name}</span>
      </div>

      {showPlus && (
        <button
          className="cz-ot-plus"
          onClick={(e) => { e.stopPropagation(); onAddClick?.(node.email); }}
          title="Añadir persona"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      )}

      {hasChildren && !isExpanded && (
        <div className="cz-ot-badge" onClick={() => onToggle(node.email)}>
          {node.descendantCount}
        </div>
      )}

      {hasChildren && isExpanded && (
        <>
          <div className="cz-ot-collapse" onClick={() => onToggle(node.email)} title="Colapsar">
            {node.descendantCount}
          </div>
          <div className="cz-ot-children">
            {node.children.map(child => (
              <HNode
                key={child.email}
                node={child}
                selectedEmail={selectedEmail}
                onSelect={onSelect}
                expanded={expanded}
                onToggle={onToggle}
                editing={editing}
                editScope={editScope}
                disconnected={disconnected}
                dragEmail={dragEmail}
                onCardPointerDown={onCardPointerDown}
                onAddClick={onAddClick}
                onCutClick={onCutClick}
                isChild
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function OrgTree({
  groups,
  selectedEmail,
  onSelect,
  editing = false,
  editScope,
  defaultExpanded: defaultExpandedProp,
  disconnected,
  dragEmail,
  onCardPointerDown,
  onAddClick,
  onCutClick,
}: {
  groups: OrgGroup[];
  selectedEmail: string | null;
  onSelect: (p: OrgPerson) => void;
  editing?: boolean;
  editScope?: Set<string>;
  defaultExpanded?: Set<string> | null;
  disconnected?: Set<string>;
  dragEmail?: string | null;
  onCardPointerDown?: (e: React.PointerEvent, email: string) => void;
  onAddClick?: (parentEmail: string) => void;
  onCutClick?: (email: string) => void;
}) {
  const initialized = useRef(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!initialized.current && groups.length > 0) {
      initialized.current = true;
      if (defaultExpandedProp && defaultExpandedProp.size > 0) {
        setExpanded(new Set(defaultExpandedProp));
      } else {
        const initial = new Set<string>();
        for (const g of groups) {
          for (const root of g.roots) {
            if (root.children.length > 0) initial.add(root.email);
          }
        }
        setExpanded(initial);
      }
    }
  }, [groups, defaultExpandedProp]);

  const toggle = useCallback((email: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(email)) next.delete(email);
      else next.add(email);
      return next;
    });
  }, []);

  if (!groups.length) {
    return <p style={{ color: "var(--ink-3)", padding: 24 }}>No hay personas en tu equipo.</p>;
  }

  return (
    <div className="cz-ot-wrap">
      {groups.map(g => (
        <div key={g.label || "self"} className="cz-ot-group">
          {g.label && <h3 className="cz-ot-group__title">{g.label}</h3>}
          <div className="cz-ot-roots">
            {g.roots.map(root => (
              <HNode
                key={root.email}
                node={root}
                selectedEmail={selectedEmail}
                onSelect={onSelect}
                expanded={expanded}
                onToggle={toggle}
                editing={editing}
                editScope={editScope}
                disconnected={disconnected}
                dragEmail={dragEmail}
                onCardPointerDown={onCardPointerDown}
                onAddClick={onAddClick}
                onCutClick={onCutClick}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
