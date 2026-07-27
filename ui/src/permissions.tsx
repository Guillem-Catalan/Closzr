import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { supabase } from "./data/supabase";
import { SLUG_TO_SCOPE } from "./display";

export type AccessLevel = "admin" | "manager" | "visitor" | "tree";
export type Scope = "none" | "self" | "team" | "all";

export type UserProfile = {
  id: string;
  email: string;
  name: string;
  accessLevel: AccessLevel;
  role: string;
  teamName: string;
  channel: string;
  reportsTo: string | null;
  scopes: Record<string, Scope>;
  visiblePartners: string[];
  subtreeEmails: string[];
};

const SCOPE_KEYS = [
  "general", "alerts", "pipeline", "benchmark", "performance",
  "forecast", "one_one", "team_analytics", "orgchart",
  "uplift", "insights", "admin", "partners",
] as const;

function buildSubtree(allRows: { email: string; reports_to: string | null }[], rootEmail: string): string[] {
  const childrenOf = new Map<string, string[]>();
  for (const r of allRows) {
    if (r.reports_to) {
      if (!childrenOf.has(r.reports_to)) childrenOf.set(r.reports_to, []);
      childrenOf.get(r.reports_to)!.push(r.email);
    }
  }
  const result: string[] = [rootEmail];
  const queue = [rootEmail];
  while (queue.length) {
    const email = queue.shift()!;
    for (const child of childrenOf.get(email) || []) {
      result.push(child);
      queue.push(child);
    }
  }
  return result;
}

function nameFromEmail(email: string): string {
  return email.split("@")[0].split(".").map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

function makeVisitorProfile(userId: string, email: string): UserProfile {
  return {
    id: userId,
    email,
    name: nameFromEmail(email),
    accessLevel: "visitor",
    role: "",
    teamName: "",
    channel: "",
    reportsTo: null,
    scopes: Object.fromEntries(SCOPE_KEYS.map(k => [k, "all" as Scope])),
    visiblePartners: [],
    subtreeEmails: [email],
  };
}

const PermCtx = createContext<{ profile: UserProfile | null; loading: boolean }>({ profile: null, loading: true });

export function usePermissions() {
  return useContext(PermCtx);
}

export function getViewScope(profile: UserProfile | null, viewSlug: string): Scope {
  if (!profile) return "all";
  if (profile.accessLevel !== "tree") return "all";
  const scopeKey = SLUG_TO_SCOPE[viewSlug];
  if (!scopeKey) return "none";
  return profile.scopes[scopeKey] || "none";
}

export function isViewEnabled(profile: UserProfile | null, viewSlug: string): boolean {
  if (!profile) return true;
  if (viewSlug === "admin") return profile.accessLevel === "admin";
  if (profile.accessLevel !== "tree") return true;
  const scopeKey = SLUG_TO_SCOPE[viewSlug];
  if (!scopeKey) return false;
  if (scopeKey === "partners") return profile.visiblePartners.length > 0 && profile.scopes.partners !== "none";
  return profile.scopes[scopeKey] !== "none";
}

export function PermissionsProvider({ userId, children }: { userId: string | null; children: ReactNode }) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async () => {
    if (!userId) { setLoading(false); return; }

    const { data: { user } } = await supabase.auth.getUser();
    if (!user?.email) { setLoading(false); return; }

    const email = user.email.toLowerCase();

    const { data: person, error } = await supabase
      .from("orgchart")
      .select("*")
      .eq("email", email)
      .single();

    if (error || !person) {
      setProfile(makeVisitorProfile(userId, email));
      setLoading(false);
      return;
    }

    const scopes: Record<string, Scope> = {};
    for (const key of SCOPE_KEYS) {
      scopes[key] = (person[`scope_${key}`] as Scope) || "none";
    }

    const { data: allPeople } = await supabase
      .from("orgchart")
      .select("email, reports_to");

    const subtreeEmails = allPeople ? buildSubtree(allPeople, email) : [email];

    setProfile({
      id: userId,
      email,
      name: person.full_name || "",
      accessLevel: (person.access_level as AccessLevel) || "tree",
      role: person.role || "ae",
      teamName: person.team_name || "",
      channel: person.channel || "",
      reportsTo: person.reports_to || null,
      scopes,
      visiblePartners: person.visible_partners || [],
      subtreeEmails,
    });
    setLoading(false);
  }, [userId]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  useEffect(() => {
    if (!userId) return;

    const channel = supabase
      .channel("orgchart-perms")
      .on("postgres_changes", { event: "*", schema: "public", table: "orgchart" }, () => {
        fetchProfile();
      })
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [userId, fetchProfile]);

  return <PermCtx.Provider value={{ profile, loading }}>{children}</PermCtx.Provider>;
}
