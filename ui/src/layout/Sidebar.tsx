import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { Icon, Avatar, getInitials } from "../views/components";
import { usePermissions, isTabEnabled } from "../permissions";
import { NAV_GROUPS } from "./nav-items";

/* ── Context ── */
type SidebarState = { expanded: boolean; toggle: () => void };
const Ctx = createContext<SidebarState>({ expanded: true, toggle: () => {} });
export function useSidebar() { return useContext(Ctx); }

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [expanded, setExpanded] = useState(() => {
    try { return localStorage.getItem("cz-sidebar") !== "collapsed"; } catch { return true; }
  });

  const toggle = useCallback(() => {
    setExpanded(p => {
      const next = !p;
      try { localStorage.setItem("cz-sidebar", next ? "expanded" : "collapsed"); } catch {}
      return next;
    });
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") { e.preventDefault(); toggle(); }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [toggle]);

  return <Ctx.Provider value={{ expanded, toggle }}>{children}</Ctx.Provider>;
}

/* ── Collapsible group ── */
function NavGroup({ title, children }: { title?: string; children: ReactNode }) {
  const { expanded } = useSidebar();
  const [open, setOpen] = useState(true);

  if (!title) return <div className="cz-sb-group">{children}</div>;

  return (
    <div className="cz-sb-group">
      {expanded ? (
        <button className="cz-sb-label" onClick={() => setOpen(p => !p)}>
          <span>{title}</span>
          <Icon name="chevDown" size={14} style={{ transform: open ? "none" : "rotate(-90deg)", transition: "transform .2s ease" }} />
        </button>
      ) : (
        <div className="cz-sb-divider" />
      )}
      {(open || !expanded) && children}
    </div>
  );
}

/* ── Tooltip (icon mode) ── */
function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const { expanded } = useSidebar();
  if (expanded) return <>{children}</>;
  return (
    <div className="cz-sb-tooltip-wrap">
      {children}
      <div className="cz-sb-tooltip">{label}</div>
    </div>
  );
}

/* ── Sidebar ── */
interface SidebarProps {
  view: string;
  onNav: (v: string) => void;
}

export default function Sidebar({ view, onNav }: SidebarProps) {
  const { expanded, toggle } = useSidebar();
  const { profile } = usePermissions();
  const showAdmin = isTabEnabled(profile, "admin");
  const displayName = profile?.name || profile?.email?.split("@")[0] || "";
  const roleLabel = profile?.role || "";

  return (
    <aside className={"cz-sb" + (expanded ? "" : " collapsed")} data-state={expanded ? "expanded" : "collapsed"}>
      {/* Header */}
      <div className="cz-sb-header">
        <div className="cz-sb-brand">
          <span className="cz-logo">C</span>
          {expanded && <span className="cz-logo-full">Closzr</span>}
        </div>
        {expanded && <span className="cz-logo-sub">Sales Intelligence</span>}
      </div>

      {/* Content */}
      <nav className="cz-sb-content">
        {NAV_GROUPS.map((group, gi) => (
          <NavGroup key={gi} title={group.title}>
            {group.items
              .filter(item => item.soon || isTabEnabled(profile, item.slug))
              .map(item => (
                <Tooltip key={item.key} label={item.label}>
                  <button
                    className={"cz-sb-btn" + (view === item.key ? " active" : "") + (item.soon ? " soon" : "")}
                    onClick={() => !item.soon && onNav(item.key)}
                    data-active={view === item.key}
                  >
                    <Icon name={item.icon} size={18} />
                    {expanded && <span className="cz-sb-btn-label">{item.label}</span>}
                    {expanded && item.soon && <span className="cz-sb-badge">Soon</span>}
                  </button>
                </Tooltip>
              ))}
          </NavGroup>
        ))}
      </nav>

      {/* Footer */}
      <div className="cz-sb-footer">
        {showAdmin && (
          <Tooltip label="Users">
            <button
              className={"cz-sb-btn" + (view === "admin" ? " active" : "")}
              onClick={() => onNav("admin")}
              data-active={view === "admin"}
            >
              <Icon name="settings" size={18} />
              {expanded && <span className="cz-sb-btn-label">Users</span>}
            </button>
          </Tooltip>
        )}

        <div className="cz-sb-user">
          <Avatar initials={getInitials(displayName)} size={expanded ? 34 : 28} name={displayName} />
          {expanded && (
            <div className="cz-sb-user-info">
              <span className="cz-sb-user-name">{displayName}</span>
              <span className="cz-sb-user-role">
                {roleLabel}{profile?.subteam && profile.subteam !== "Unassigned" ? ` · ${profile.subteam}` : ""}
              </span>
            </div>
          )}
        </div>

        <button className="cz-sb-trigger" onClick={toggle} title={expanded ? "Collapse (⌘B)" : "Expand (⌘B)"}>
          <Icon name="chevRight" size={16} style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform .2s ease" }} />
        </button>
      </div>
    </aside>
  );
}
