import { createContext, useContext, useEffect, useState, type ReactNode, type FormEvent } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "./data/supabase";
import { ORG_DOMAINS, KNOWN_USERS, DEFAULT_ROLE, ACTIVE_TEAMS } from "./display";

// ---- Auth context ----
type AuthCtx = {
  session: Session | null;
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (email: string, password: string, name: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthCtx | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      setLoading(false);
    });
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const value: AuthCtx = {
    session,
    user: session?.user ?? null,
    loading,
    signIn: async (email, password) => {
      const domain = email.split("@")[1];
      if (!ORG_DOMAINS.includes(domain)) return { error: `Only @${ORG_DOMAINS[0]} emails allowed` };
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      return { error: error?.message ?? null };
    },
    signUp: async (email, password, name) => {
      const domain = email.split("@")[1];
      if (!ORG_DOMAINS.includes(domain)) return { error: `Only @${ORG_DOMAINS[0]} emails allowed` };
      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) return { error: error.message };
      const knownUser = KNOWN_USERS[email];
      if (data.user) {
        await supabase.from("users").upsert({
          id: data.user.id,
          email,
          name,
          role: knownUser?.role || DEFAULT_ROLE,
          team: knownUser?.team || ACTIVE_TEAMS[0],
          subteam: "Unassigned",
          visible_teams: [],
          visible_reps: [],
          tab_permissions: {
            general: { enabled: true, scope: "self" },
            todos: { enabled: true, scope: "self" },
            deals: { enabled: true, scope: "self" },
            benchmark: { enabled: true, scope: "self" },
            alerts: { enabled: true, scope: "self" },
            forecast: { enabled: true, scope: "self" },
            oneone: { enabled: false, scope: "self" },
            uplift: { enabled: true, scope: "self" },
            admin: { enabled: false, scope: "all" },
          },
        }, { onConflict: "id" });
      }
      return { error: null };
    },
    signOut: async () => { await supabase.auth.signOut(); },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---- Login / Register page (Closzr-styled) ----
export function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const { signIn, signUp, user, loading } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) onSuccess();
  }, [user, loading, onSuccess]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setBusy(true);
    if (mode === "login") {
      const { error: err } = await signIn(email, password);
      setBusy(false);
      if (err) setError(err);
    } else {
      if (!name.trim()) { setError("Escribe tu nombre"); setBusy(false); return; }
      const { error: err } = await signUp(email, password, name.trim());
      setBusy(false);
      if (err) { setError(err); return; }
    }
  }

  const inputStyle = {
    padding: "10px 14px", fontSize: 14, border: "1px solid var(--line-ink)",
    borderRadius: "var(--r-sm)", outline: "none", color: "var(--ink)",
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "var(--paper)", padding: 20,
    }}>
      <div style={{
        width: "100%", maxWidth: 380, background: "white", border: "1px solid var(--line)",
        borderRadius: "var(--r-lg)", padding: "32px 28px", boxShadow: "var(--sh-md)",
      }}>
        <div style={{ marginBottom: 24 }}>
          <span className="cz-logo" style={{ fontSize: 26 }}>Closzr</span>
          <p style={{ fontSize: 13, color: "var(--ink-3)", marginTop: 4 }}>
            Sales Intelligence · {mode === "login" ? "Sign in" : "Crear cuenta"}
          </p>
        </div>
        <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {mode === "register" && (
            <input
              type="text"
              required
              placeholder="Tu nombre (ej. María López)"
              value={name}
              onChange={e => setName(e.target.value)}
              style={inputStyle}
            />
          )}
          <input
            type="email"
            required
            placeholder={`you@${ORG_DOMAINS[0]}`}
            value={email}
            onChange={e => setEmail(e.target.value)}
            style={inputStyle}
          />
          <input
            type="password"
            required
            minLength={6}
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            style={inputStyle}
          />
          {error && <p style={{ fontSize: 13, color: "var(--red-ink)", margin: 0 }}>{error}</p>}
          {success && <p style={{ fontSize: 13, color: "var(--green-ink)", margin: 0 }}>{success}</p>}
          <button
            type="submit"
            disabled={busy}
            className="cz-btn-primary"
            style={{ width: "100%", justifyContent: "center", padding: "11px 20px", fontSize: 14, marginTop: 4 }}
          >
            {busy ? (mode === "login" ? "Entrando..." : "Creando...") : (mode === "login" ? "Sign in" : "Crear cuenta")}
          </button>
        </form>
        <p style={{ fontSize: 13, color: "var(--ink-3)", textAlign: "center", marginTop: 16 }}>
          {mode === "login" ? (
            <>¿No tienes cuenta? <button onClick={() => { setMode("register"); setError(null); setSuccess(null); }} style={{ background: "none", border: "none", color: "var(--indigo)", cursor: "pointer", fontSize: 13, fontWeight: 600, padding: 0 }}>Regístrate</button></>
          ) : (
            <>¿Ya tienes cuenta? <button onClick={() => { setMode("login"); setError(null); setSuccess(null); }} style={{ background: "none", border: "none", color: "var(--indigo)", cursor: "pointer", fontSize: 13, fontWeight: 600, padding: 0 }}>Sign in</button></>
          )}
        </p>
      </div>
    </div>
  );
}
