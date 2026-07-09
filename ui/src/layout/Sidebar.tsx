import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { Icon, Avatar, getInitials } from "../views/components";
import { usePermissions, isTabEnabled } from "../permissions";
import { NAV_ITEMS, type NavItem } from "./nav-items";

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

/* ── Tooltip (collapsed mode) ── */
function Tip({ label, children }: { label: string; children: ReactNode }) {
  const { expanded } = useSidebar();
  if (expanded) return <>{children}</>;
  return (
    <div className="cz-sb-tip-wrap">
      {children}
      <div className="cz-sb-tip">{label}</div>
    </div>
  );
}

/* ── Collapsible nav group ── */
function Collapsible({ item, view, onNav }: { item: NavItem; view: string; onNav: (v: string) => void }) {
  const { expanded: sidebarOpen } = useSidebar();
  const { profile } = usePermissions();
  const activeChild = item.children?.some(c => c.key === view) ?? false;
  const [open, setOpen] = useState(true);

  const visibleChildren = item.children!.filter(c => c.soon || isTabEnabled(profile, c.slug));

  if (!sidebarOpen) {
    return (
      <div className="cz-sb-group">
        <Tip label={item.label}>
          <button
            className={"cz-sb-item parent" + (activeChild && !open ? " active" : "")}
            onClick={() => setOpen(p => !p)}
          >
            <Icon name={item.icon} size={20} />
          </button>
        </Tip>
        {open && visibleChildren.map(child => (
          <Tip key={child.key} label={child.label}>
            <button
              className={"cz-sb-item" + (view === child.key ? " active" : "") + (child.soon ? " soon" : "")}
              onClick={() => !child.soon && onNav(child.key)}
            >
              <Icon name={child.icon} size={18} />
            </button>
          </Tip>
        ))}
      </div>
    );
  }

  return (
    <div className="cz-sb-group">
      <button className={"cz-sb-item parent" + (activeChild && !open ? " active" : "")} onClick={() => setOpen(p => !p)}>
        <Icon name={item.icon} size={20} />
        <span className="cz-sb-item-text">{item.label}</span>
        <Icon name="chevDown" size={14} className={"cz-sb-chev" + (open ? " open" : "")} />
      </button>
      {open && (
        <div className="cz-sb-sub">
          {visibleChildren.map(child => (
            <button
              key={child.key}
              className={"cz-sb-sub-item" + (view === child.key ? " active" : "") + (child.soon ? " soon" : "")}
              onClick={() => !child.soon && onNav(child.key)}
            >
              {child.label}
              {child.soon && <span className="cz-sb-soon">Soon</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Sidebar ── */
export default function Sidebar({ view, onNav }: { view: string; onNav: (v: string) => void }) {
  const { expanded } = useSidebar();
  const { profile } = usePermissions();
  const showAdmin = isTabEnabled(profile, "admin");
  const name = profile?.name || profile?.email?.split("@")[0] || "";
  const role = profile?.role || "";

  return (
    <aside className={"cz-sb" + (expanded ? "" : " collapsed")}>
      {/* Brand */}
      <div className="cz-sb-header">
        <span className="cz-logo">C</span>
        {expanded && (
          <div className="cz-sb-header-text">
            <span className="cz-logo-full">Closzr</span>
            <span className="cz-logo-sub">Sales Intelligence</span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="cz-sb-nav">
        {NAV_ITEMS.map(item =>
          item.children ? (
            <Collapsible key={item.key} item={item} view={view} onNav={onNav} />
          ) : (
            <Tip key={item.key} label={item.label}>
              <button
                className={"cz-sb-item parent" + (view === item.key ? " active" : "") + (item.soon ? " soon" : "")}
                onClick={() => !item.soon && onNav(item.key)}
              >
                <Icon name={item.icon} size={20} />
                {expanded && <span className="cz-sb-item-text">{item.label}</span>}
                {expanded && item.soon && <span className="cz-sb-soon">Soon</span>}
              </button>
            </Tip>
          )
        )}
      </nav>

      {/* Footer */}
      <div className="cz-sb-footer">
        {showAdmin && (
          <Tip label="Users">
            <button className={"cz-sb-item" + (view === "admin" ? " active" : "")} onClick={() => onNav("admin")}>
              <Icon name="settings" size={18} />
              {expanded && <span className="cz-sb-item-text">Users</span>}
            </button>
          </Tip>
        )}
        <div className="cz-sb-user">
          <Avatar initials={getInitials(name)} size={expanded ? 32 : 28} name={name} />
          {expanded && (
            <div className="cz-sb-user-meta">
              <span className="cz-sb-user-name">{name}</span>
              <span className="cz-sb-user-role">
                {role}{profile?.subteam && profile.subteam !== "Unassigned" ? ` · ${profile.subteam}` : ""}
              </span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
