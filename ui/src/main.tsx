import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./closzr.css";
import "./styles.css";
import { AuthProvider, useAuth, LoginPage, ResetPasswordPage } from "./auth";
import { PermissionsProvider } from "./permissions";
import { DataProvider } from "./data/provider";
import { ORG_DOMAINS } from "./display";
import App from "./App";

function Root() {
  const { user, loading, passwordRecovery, signOut } = useAuth();
  const [ready, setReady] = useState(false);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--paper)" }}>
        <p style={{ color: "var(--ink-3)", fontSize: 15 }}>Cargando...</p>
      </div>
    );
  }

  if (passwordRecovery) {
    return <ResetPasswordPage />;
  }

  if (user?.email) {
    const domain = user.email.split("@")[1];
    if (!ORG_DOMAINS.includes(domain)) {
      signOut();
      return (
        <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--paper)" }}>
          <p style={{ color: "var(--red-ink)", fontSize: 15 }}>Acceso denegado — solo emails @{ORG_DOMAINS[0]}</p>
        </div>
      );
    }
  }

  if (!user && !ready) {
    return <LoginPage onSuccess={() => setReady(true)} />;
  }

  return (
    <PermissionsProvider userId={user?.id ?? null}>
      <DataProvider>
        <App />
      </DataProvider>
    </PermissionsProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <Root />
    </AuthProvider>
  </StrictMode>,
);
