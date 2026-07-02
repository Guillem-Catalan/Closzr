import { Icon, Avatar, getInitials } from "../views/components";
import { usePermissions, isTabEnabled } from "../permissions";
import { NAV_GROUPS } from "./nav-items";

interface SidebarProps {
  view: string;
  onNav: (v: string) => void;
}

export default function Sidebar({ view, onNav }: SidebarProps) {
  const { profile } = usePermissions();
  const showAdmin = isTabEnabled(profile, "admin");
  const displayName = profile?.name || profile?.email?.split("@")[0] || "";
  const roleLabel = profile?.role || "";

  return (
    <aside className="cz-sidebar">
      <div className="cz-sidebar-header">
        <span className="cz-logo">Closzr</span>
        <span className="cz-logo-sub">Sales Intelligence</span>
      </div>

      <nav className="cz-sidebar-nav">
        {NAV_GROUPS.map((group, gi) => (
          <div className="cz-sidebar-group" key={gi}>
            {group.title && <div className="cz-sidebar-label">{group.title}</div>}
            {group.items
              .filter(item => item.soon || isTabEnabled(profile, item.slug))
              .map(item => (
                <button
                  key={item.key}
                  className={
                    "cz-sidebar-item" +
                    (view === item.key ? " on" : "") +
                    (item.soon ? " soon" : "")
                  }
                  onClick={() => !item.soon && onNav(item.key)}
                >
                  <Icon name={item.icon} size={18} />
                  <span>{item.label}</span>
                  {item.soon && <span className="cz-sidebar-badge">Soon</span>}
                </button>
              ))}
          </div>
        ))}
      </nav>

      <div className="cz-sidebar-footer">
        {showAdmin && (
          <button
            className={"cz-sidebar-item" + (view === "admin" ? " on" : "")}
            onClick={() => onNav("admin")}
          >
            <Icon name="settings" size={18} />
            <span>Users</span>
          </button>
        )}
        <div className="cz-sidebar-user">
          <Avatar initials={getInitials(displayName)} size={34} name={displayName} />
          <div className="cz-user-info">
            <span className="cz-user-name">{displayName}</span>
            <span className="cz-user-role">
              {roleLabel}
              {profile?.subteam && profile.subteam !== "Unassigned" ? ` · ${profile.subteam}` : ""}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
