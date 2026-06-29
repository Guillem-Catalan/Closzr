/* ============================================================
   CLOSZR — App root
   ============================================================ */
import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { Icon, Avatar, getInitials } from "./views/components";
import { useData } from "./data/store";
import { fetchDealDetail, type DealDetail } from "./data/fetchDetail";
import { usePermissions, isTabEnabled } from "./permissions";
import PipelineView from "./views/PipelineView";
import DealWorkspace from "./views/DealWorkspace";
import ForecastView from "./views/ForecastView";
import OneOnOneView from "./views/OneOnOneView";
import TodoView from "./views/TodoView";
const AdminView = lazy(() => import("./views/AdminView"));

const TAB_MAP: Record<string, string> = { "Forecast": "forecast", "TO-DOs": "todos", "Pipeline": "deals", "1:1": "oneone", "Admin": "admin" };

function TopBar({ view, onNav }: { view: string; onNav: (v: string) => void }) {
  const { profile } = usePermissions();
  const mainTabs = ["Forecast", "TO-DOs", "Pipeline", "1:1"];
  const tabs = mainTabs.filter(t => isTabEnabled(profile, TAB_MAP[t]));
  const showAdmin = isTabEnabled(profile, "admin");
  const displayName = profile?.name || profile?.email?.split("@")[0] || "";
  const roleLabel = profile?.role || "";

  return (
    <header className="cz-topbar">
      <div className="cz-brand">
        <span className="cz-logo">Closzr</span>
        <span className="cz-logo-sub">Sales Intelligence</span>
      </div>
      <nav className="cz-topnav">
        {tabs.map(t => <button key={t} className={"cz-topnav-tab" + (t === view ? " on" : "")} onClick={() => onNav(t)}>{t}</button>)}
      </nav>
      <div style={{flex:1}}/>
      <div className="cz-user">
        <Avatar initials={getInitials(displayName)} size={34} name={displayName}/>
        <div className="cz-user-info">
          <span className="cz-user-name">{displayName}</span>
          <span className="cz-user-role">{roleLabel}{profile?.subteam && profile.subteam !== "Unassigned" ? ` · ${profile.subteam}` : ""}</span>
        </div>
      </div>
      {showAdmin && (
        <button className={"cz-topnav-tab" + (view === "Admin" ? " on" : "")} onClick={() => onNav("Admin")} style={{ marginLeft: 8 }}>
          <Icon name="settings" size={16} stroke={2}/>
        </button>
      )}
    </header>
  );
}

// ComingSoon removed — all tabs have content now

function App() {
  const D = useData();
  const [view, setView] = useState("Forecast");
  const [detail, setDetail] = useState<DealDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // deep-link: ?deal=<id>&tab=<hist|atlas|next>
  useEffect(() => {
    if (D.loading) return;
    const p = new URLSearchParams(location.search);
    const id = p.get("deal");
    if (!id) return;
    fetchDealDetail(id).then(setDetail);
  }, [D.loading]);

  const handleOpen = useCallback((row: any, _tab?: string) => {
    if (!row.id) return;
    setDetailLoading(true);
    fetchDealDetail(row.id).then(d => {
      setDetail(d);
      setDetailLoading(false);
    }).catch(() => setDetailLoading(false));
  }, []);

  if (D.loading) {
    return (
      <div className="cz-app">
        <TopBar view={view} onNav={setView}/>
        <main className="cz-main" style={{display:"flex",alignItems:"center",justifyContent:"center",minHeight:"60vh"}}>
          <p style={{color:"var(--ink-3)",fontSize:15}}>Cargando datos...</p>
        </main>
      </div>
    );
  }

  return (
    <div className="cz-app">
      <TopBar view={view} onNav={setView}/>
      <main className="cz-main">
        {view === "TO-DOs" && <TodoView onOpen={handleOpen}/>}
        {view === "Pipeline" && <PipelineView onOpen={handleOpen}/>}
        {view === "Forecast" && <ForecastView onOpen={handleOpen}/>}
        {view === "1:1" && <OneOnOneView onOpen={handleOpen}/>}
        {view === "Admin" && <Suspense fallback={<p style={{color:"var(--ink-3)"}}>Cargando...</p>}><AdminView/></Suspense>}
      </main>
      {detailLoading && (
        <div className="cz-overlay" style={{background:"rgba(28,24,16,.25)"}}>
          <p style={{color:"white",fontSize:15}}>Cargando deal...</p>
        </div>
      )}
      {detail && !detailLoading && (
        <DealWorkspace detail={detail} initialTab="hist" onClose={() => setDetail(null)}/>
      )}
    </div>
  );
}

export default App;
