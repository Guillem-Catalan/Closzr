import { createContext, useContext, useEffect, useState, type ReactNode, type FormEvent, type CSSProperties } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "./data/supabase";
import { ORG_DOMAINS } from "./display";

// ---- Auth context ----
type AuthCtx = {
  session: Session | null;
  user: User | null;
  loading: boolean;
  passwordRecovery: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (email: string, password: string, name: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  clearPasswordRecovery: () => void;
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
  const [passwordRecovery, setPasswordRecovery] = useState(false);

  useEffect(() => {
    const { data: sub } = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s);
      setLoading(false);
      if (event === "PASSWORD_RECOVERY") setPasswordRecovery(true);
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
    passwordRecovery,
    signIn: async (email, password) => {
      const domain = email.split("@")[1];
      if (!ORG_DOMAINS.includes(domain)) return { error: `Solo se permiten emails de @${ORG_DOMAINS[0]}` };
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      return { error: error?.message ?? null };
    },
    signUp: async (email, password, _name) => {
      const domain = email.split("@")[1];
      if (!ORG_DOMAINS.includes(domain)) return { error: `Solo se permiten emails de @${ORG_DOMAINS[0]}` };
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) return { error: error.message };
      return { error: null };
    },
    signOut: async () => { await supabase.auth.signOut(); },
    clearPasswordRecovery: () => setPasswordRecovery(false),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---- Shared styles ----
const S = {
  page: {
    minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
    background: "var(--paper)", padding: 20, fontFamily: "var(--font-sans)",
  } as CSSProperties,
  card: {
    width: "100%", maxWidth: 400, background: "var(--card)", border: "1px solid var(--line)",
    borderRadius: "var(--r-lg)", padding: "36px 32px", boxShadow: "var(--sh-md)",
  } as CSSProperties,
  input: {
    padding: "11px 14px", fontSize: 14, border: "1px solid var(--line-ink)",
    borderRadius: "var(--r-sm)", outline: "none", color: "var(--ink)",
    width: "100%", fontFamily: "inherit", background: "var(--card)",
    transition: "border-color .15s",
  } as CSSProperties,
  form: { display: "flex", flexDirection: "column", gap: 12 } as CSSProperties,
  error: {
    fontSize: 13, color: "var(--red-ink)", background: "var(--red-tint)",
    border: "1px solid #f5c6c0", borderRadius: "var(--r-sm)", padding: "8px 12px", margin: 0,
  } as CSSProperties,
  success: {
    fontSize: 13, color: "var(--green-ink)", background: "var(--green-tint)",
    border: "1px solid #b0dfc8", borderRadius: "var(--r-sm)", padding: "8px 12px", margin: 0,
  } as CSSProperties,
  link: {
    background: "none", border: "none", color: "var(--indigo)", cursor: "pointer",
    fontSize: 13, fontWeight: 600, padding: 0, fontFamily: "inherit",
  } as CSSProperties,
  social: {
    display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
    width: "100%", padding: "11px 16px", fontSize: 14, fontWeight: 500,
    border: "1px solid var(--line-ink)", borderRadius: "var(--r-sm)",
    background: "var(--card)", color: "var(--ink)", cursor: "pointer",
    transition: "background .15s, border-color .15s", fontFamily: "inherit",
  } as CSSProperties,
  backLink: {
    display: "inline-flex", alignItems: "center", gap: 4,
    fontSize: 13, color: "var(--ink-3)", cursor: "pointer",
    background: "none", border: "none", padding: 0, marginBottom: 16, fontFamily: "inherit",
  } as CSSProperties,
};

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

const SsoIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--ink-2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2"/>
    <path d="M7 11V7a5 5 0 0110 0v4"/>
    <circle cx="12" cy="16" r="1"/>
  </svg>
);

function validateDomain(email: string): boolean {
  const domain = email.split("@")[1];
  return ORG_DOMAINS.includes(domain);
}

function getPasswordStrength(pw: string): number {
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return score;
}

const STRENGTH_COLORS = ["var(--red)", "var(--amber)", "var(--blue)", "var(--green)"];
const STRENGTH_LABELS = ["Débil", "Regular", "Buena", "Fuerte"];

function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  const score = getPasswordStrength(password);
  return (
    <div style={{ marginTop: -4 }}>
      <div style={{ display: "flex", gap: 4 }}>
        {[1, 2, 3, 4].map(i => (
          <div key={i} style={{
            flex: 1, height: 3, borderRadius: 2,
            background: i <= score ? STRENGTH_COLORS[score - 1] : "var(--line)",
            transition: "background .2s",
          }} />
        ))}
      </div>
      <div style={{ fontSize: 11, marginTop: 3, color: STRENGTH_COLORS[score - 1] || "var(--ink-3)" }}>
        {STRENGTH_LABELS[score - 1] || ""}
      </div>
    </div>
  );
}

function PasswordInput({ value, onChange, placeholder, minLength, showStrength }: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  minLength?: number;
  showStrength?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <>
      <div style={{ position: "relative" }}>
        <input
          type={visible ? "text" : "password"}
          required
          minLength={minLength}
          placeholder={placeholder}
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{ ...S.input, paddingRight: 64 }}
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          style={{
            position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
            background: "none", border: "none", color: "var(--ink-3)", cursor: "pointer",
            fontSize: 12, padding: "4px", fontFamily: "inherit",
          }}
        >
          {visible ? "Ocultar" : "Mostrar"}
        </button>
      </div>
      {showStrength && <PasswordStrength password={value} />}
    </>
  );
}

function Divider({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, margin: "20px 0" }}>
      <div style={{ flex: 1, height: 1, background: "var(--line)" }} />
      <span style={{ fontSize: 12, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.5px" }}>{text}</span>
      <div style={{ flex: 1, height: 1, background: "var(--line)" }} />
    </div>
  );
}

function SocialButtons({ onGoogle, onSSO }: { onGoogle: () => void; onSSO: () => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <button style={S.social} onClick={onGoogle} onMouseEnter={e => { e.currentTarget.style.background = "var(--card-2)"; e.currentTarget.style.borderColor = "var(--ink-4)"; }} onMouseLeave={e => { e.currentTarget.style.background = "var(--card)"; e.currentTarget.style.borderColor = "var(--line-ink)"; }}>
        <GoogleIcon /> Continuar con Google
      </button>
      <button style={S.social} onClick={onSSO} onMouseEnter={e => { e.currentTarget.style.background = "var(--card-2)"; e.currentTarget.style.borderColor = "var(--ink-4)"; }} onMouseLeave={e => { e.currentTarget.style.background = "var(--card)"; e.currentTarget.style.borderColor = "var(--line-ink)"; }}>
        <SsoIcon /> Single Sign-On (SSO)
      </button>
    </div>
  );
}

type LoginMode = "login" | "register" | "forgot" | "sso" | "verify";

// ---- Login page ----
export function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const { signIn, signUp, user, loading } = useAuth();
  const [mode, setMode] = useState<LoginMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) onSuccess();
  }, [user, loading, onSuccess]);

  function switchMode(m: LoginMode) {
    setMode(m);
    setError(null);
    setSuccess(null);
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const { error: err } = await signIn(email, password);
    setBusy(false);
    if (err) setError(err);
  }

  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError("Escribe tu nombre"); return; }
    setBusy(true);
    const { error: err } = await signUp(email, password, name.trim());
    setBusy(false);
    if (err) { setError(err); return; }
    switchMode("verify");
  }

  async function handleForgot(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (!validateDomain(email)) {
      setError(`Solo se permiten emails de @${ORG_DOMAINS[0]}`);
      return;
    }
    setBusy(true);
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}`,
    });
    setBusy(false);
    if (error) { setError(error.message); return; }
    setSuccess("Si el email existe, recibirás un enlace de recuperación. Revisa tu bandeja de entrada.");
  }

  async function handleSSO(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!validateDomain(email)) {
      setError("No se encontró un proveedor SSO para este dominio");
      return;
    }
    setBusy(true);
    const domain = email.split("@")[1];
    const { error } = await supabase.auth.signInWithSSO({ domain });
    setBusy(false);
    if (error) setError(error.message);
  }

  async function handleGoogle() {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}`,
        queryParams: { hd: ORG_DOMAINS[0] },
      },
    });
    if (error) setError(error.message);
  }

  const subtitle: Record<LoginMode, string> = {
    login: "Sign in",
    register: "Crear cuenta",
    forgot: "Recuperar contraseña",
    sso: "Single Sign-On",
    verify: "Revisa tu email",
  };

  return (
    <div style={S.page}>
      <div style={S.card}>
        {/* Back link for sub-screens */}
        {(mode === "forgot" || mode === "sso") && (
          <button style={S.backLink} onClick={() => switchMode("login")}>
            ← Volver a sign in
          </button>
        )}

        {/* Header */}
        <div style={{ marginBottom: 28, textAlign: mode === "verify" ? "center" : undefined }}>
          {mode === "verify" && <div style={{ fontSize: 48, marginBottom: 12 }}>📧</div>}
          <span className="cz-logo" style={{ fontSize: 28 }}>Closzr</span>
          <p style={{ fontSize: 13, color: "var(--ink-3)", marginTop: 4 }}>
            Sales Intelligence · {subtitle[mode]}
          </p>
        </div>

        {/* ===== LOGIN ===== */}
        {mode === "login" && (
          <>
            <SocialButtons onGoogle={handleGoogle} onSSO={() => switchMode("sso")} />
            <Divider text="o con email" />
            <form onSubmit={handleLogin} style={S.form}>
              <input type="email" required placeholder={`tu@${ORG_DOMAINS[0]}`} value={email} onChange={e => setEmail(e.target.value)} style={S.input} />
              <PasswordInput value={password} onChange={setPassword} placeholder="Contraseña" minLength={6} />
              <div style={{ textAlign: "right", marginTop: -4 }}>
                <button type="button" onClick={() => switchMode("forgot")} style={{ ...S.link, fontSize: 13 }}>
                  ¿Olvidaste tu contraseña?
                </button>
              </div>
              {error && <p style={S.error}>{error}</p>}
              <button type="submit" disabled={busy} className="cz-btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px 20px", fontSize: 14, marginTop: 4, borderRadius: "var(--r-sm)" }}>
                {busy ? "Entrando..." : "Sign in"}
              </button>
            </form>
            <p style={{ fontSize: 13, color: "var(--ink-3)", textAlign: "center", marginTop: 20 }}>
              ¿No tienes cuenta? <button onClick={() => switchMode("register")} style={S.link}>Regístrate</button>
            </p>
          </>
        )}

        {/* ===== REGISTER ===== */}
        {mode === "register" && (
          <>
            <SocialButtons onGoogle={handleGoogle} onSSO={() => switchMode("sso")} />
            <Divider text="o con email" />
            <form onSubmit={handleRegister} style={S.form}>
              <input type="text" required placeholder="Tu nombre (ej. María López)" value={name} onChange={e => setName(e.target.value)} style={S.input} />
              <input type="email" required placeholder={`tu@${ORG_DOMAINS[0]}`} value={email} onChange={e => setEmail(e.target.value)} style={S.input} />
              <PasswordInput value={password} onChange={setPassword} placeholder="Contraseña (mín. 8 caracteres)" minLength={8} showStrength />
              {error && <p style={S.error}>{error}</p>}
              <button type="submit" disabled={busy} className="cz-btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px 20px", fontSize: 14, marginTop: 4, borderRadius: "var(--r-sm)" }}>
                {busy ? "Creando..." : "Crear cuenta"}
              </button>
            </form>
            <p style={{ fontSize: 13, color: "var(--ink-3)", textAlign: "center", marginTop: 20 }}>
              ¿Ya tienes cuenta? <button onClick={() => switchMode("login")} style={S.link}>Sign in</button>
            </p>
          </>
        )}

        {/* ===== FORGOT PASSWORD ===== */}
        {mode === "forgot" && (
          <>
            <p style={{ fontSize: 14, color: "var(--ink-2)", marginBottom: 20, lineHeight: 1.5 }}>
              Introduce tu email y te enviaremos un enlace para restablecer tu contraseña.
            </p>
            <form onSubmit={handleForgot} style={S.form}>
              <input type="email" required placeholder={`tu@${ORG_DOMAINS[0]}`} value={email} onChange={e => setEmail(e.target.value)} style={S.input} />
              {error && <p style={S.error}>{error}</p>}
              {success && <p style={S.success}>{success}</p>}
              <button type="submit" disabled={busy} className="cz-btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px 20px", fontSize: 14, marginTop: 4, borderRadius: "var(--r-sm)" }}>
                {busy ? "Enviando..." : "Enviar enlace de recuperación"}
              </button>
            </form>
            <p style={{ fontSize: 13, color: "var(--ink-3)", textAlign: "center", marginTop: 24 }}>
              ¿Recordaste tu contraseña? <button onClick={() => switchMode("login")} style={S.link}>Sign in</button>
            </p>
          </>
        )}

        {/* ===== SSO ===== */}
        {mode === "sso" && (
          <>
            <p style={{ fontSize: 14, color: "var(--ink-2)", marginBottom: 20, lineHeight: 1.5 }}>
              Introduce tu email corporativo y te redirigiremos al proveedor de identidad de tu organización.
            </p>
            <form onSubmit={handleSSO} style={S.form}>
              <input type="email" required placeholder={`tu@${ORG_DOMAINS[0]}`} value={email} onChange={e => setEmail(e.target.value)} style={S.input} />
              {error && <p style={S.error}>{error}</p>}
              <button type="submit" disabled={busy} className="cz-btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px 20px", fontSize: 14, marginTop: 4, borderRadius: "var(--r-sm)" }}>
                {busy ? "Redirigiendo..." : "Continuar con SSO"}
              </button>
            </form>
            <p style={{ fontSize: 13, color: "var(--ink-3)", textAlign: "center", marginTop: 24 }}>
              <button onClick={() => switchMode("login")} style={S.link}>Otras opciones de acceso</button>
            </p>
          </>
        )}

        {/* ===== EMAIL VERIFICATION ===== */}
        {mode === "verify" && (
          <>
            <p style={{ fontSize: 14, color: "var(--ink-2)", textAlign: "center", lineHeight: 1.6 }}>
              Hemos enviado un enlace de verificación a<br />
              <strong>{email}</strong>
            </p>
            <p style={{ fontSize: 13, color: "var(--ink-3)", textAlign: "center", marginTop: 12, lineHeight: 1.5 }}>
              Haz clic en el enlace del email para activar tu cuenta. Revisa la carpeta de spam si no lo encuentras.
            </p>
            <button
              className="cz-btn-primary"
              style={{ width: "100%", justifyContent: "center", padding: "12px 20px", fontSize: 14, marginTop: 24, borderRadius: "var(--r-sm)" }}
              onClick={async () => {
                const { error } = await supabase.auth.resend({ type: "signup", email });
                if (error) setError(error.message);
                else setSuccess("Email reenviado");
              }}
            >
              Reenviar email
            </button>
            {error && <p style={{ ...S.error, marginTop: 12 }}>{error}</p>}
            {success && <p style={{ ...S.success, marginTop: 12 }}>{success}</p>}
            <p style={{ fontSize: 13, color: "var(--ink-3)", textAlign: "center", marginTop: 20 }}>
              <button onClick={() => switchMode("login")} style={S.link}>Volver a sign in</button>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

// ---- Reset password page (shown after clicking email recovery link) ----
export function ResetPasswordPage() {
  const { clearPasswordRecovery } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleReset(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) { setError("Las contraseñas no coinciden"); return; }
    if (password.length < 8) { setError("La contraseña debe tener al menos 8 caracteres"); return; }
    setBusy(true);
    const { error } = await supabase.auth.updateUser({ password });
    setBusy(false);
    if (error) { setError(error.message); return; }
    setDone(true);
  }

  if (done) {
    return (
      <div style={S.page}>
        <div style={S.card}>
          <div style={{ textAlign: "center", marginBottom: 28 }}>
            <div style={{ fontSize: 48, marginBottom: 12, color: "var(--green)" }}>✓</div>
            <span className="cz-logo" style={{ fontSize: 28 }}>Closzr</span>
          </div>
          <div style={S.success}>Contraseña actualizada correctamente</div>
          <button
            className="cz-btn-primary"
            style={{ width: "100%", justifyContent: "center", padding: "12px 20px", fontSize: 14, marginTop: 20, borderRadius: "var(--r-sm)" }}
            onClick={clearPasswordRecovery}
          >
            Continuar a Closzr
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      <div style={S.card}>
        <div style={{ marginBottom: 28 }}>
          <span className="cz-logo" style={{ fontSize: 28 }}>Closzr</span>
          <p style={{ fontSize: 13, color: "var(--ink-3)", marginTop: 4 }}>
            Sales Intelligence · Nueva contraseña
          </p>
        </div>
        <p style={{ fontSize: 14, color: "var(--ink-2)", marginBottom: 20, lineHeight: 1.5 }}>
          Introduce tu nueva contraseña. Debe tener al menos 8 caracteres.
        </p>
        <form onSubmit={handleReset} style={S.form}>
          <PasswordInput value={password} onChange={setPassword} placeholder="Nueva contraseña" minLength={8} showStrength />
          <PasswordInput value={confirm} onChange={setConfirm} placeholder="Confirmar contraseña" minLength={8} />
          {error && <p style={S.error}>{error}</p>}
          <button type="submit" disabled={busy} className="cz-btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px 20px", fontSize: 14, marginTop: 4, borderRadius: "var(--r-sm)" }}>
            {busy ? "Guardando..." : "Guardar contraseña"}
          </button>
        </form>
      </div>
    </div>
  );
}
