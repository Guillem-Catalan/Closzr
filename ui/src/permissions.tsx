import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { supabase } from "./data/supabase";

export type TabScope = { enabled: boolean; scope: "all" | "team" | "self" | "custom"; reps?: string[] };

export type UserProfile = {
  id: string;
  email: string;
  name: string;
  team: string;
  subteam: string;
  role: "Admin" | "Manager" | "TL" | "PAE";
  visibleTeams: string[];
  visibleReps: string[];
  tabPermissions: Record<string, TabScope>;
};

const DEFAULT_PERMISSIONS: Record<string, TabScope> = {
  todos: { enabled: true, scope: "all" },
  deals: { enabled: true, scope: "all" },
  forecast: { enabled: true, scope: "all" },
  oneone: { enabled: true, scope: "all" },
  admin: { enabled: false, scope: "all" },
};

const PermCtx = createContext<{ profile: UserProfile | null; loading: boolean }>({ profile: null, loading: true });

export function usePermissions() {
  return useContext(PermCtx);
}

export function getTabScope(profile: UserProfile | null, tab: string): TabScope {
  if (!profile) return { enabled: true, scope: "all" };
  const perm = profile.tabPermissions[tab];
  if (!perm) return { enabled: false, scope: "all" };
  return perm;
}

export function isTabEnabled(profile: UserProfile | null, tab: string): boolean {
  if (!profile) return true;
  if (tab === "admin") return profile.role === "Admin";
  return getTabScope(profile, tab).enabled;
}

export function PermissionsProvider({ userId, children }: { userId: string | null; children: ReactNode }) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) { setLoading(false); return; }

    (async () => {
      const { data, error } = await supabase
        .from("users")
        .select("*")
        .eq("id", userId)
        .single();

      if (error || !data) {
        setLoading(false);
        return;
      }

      const tabPerms = (typeof data.tab_permissions === "object" && data.tab_permissions)
        ? data.tab_permissions as Record<string, TabScope>
        : DEFAULT_PERMISSIONS;

      setProfile({
        id: data.id,
        email: data.email || "",
        name: data.name || "",
        team: data.team || "",
        subteam: data.subteam || "",
        role: data.role || "PAE",
        visibleTeams: data.visible_teams || [],
        visibleReps: data.visible_reps || [],
        tabPermissions: { ...DEFAULT_PERMISSIONS, ...tabPerms },
      });
      setLoading(false);

      // Update last_login
      supabase.from("users").update({ last_login: new Date().toISOString() }).eq("id", userId).then(() => {});
    })();
  }, [userId]);

  return <PermCtx.Provider value={{ profile, loading }}>{children}</PermCtx.Provider>;
}
