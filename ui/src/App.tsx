/* ============================================================
   CLOSZR — App root
   ============================================================ */
import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { useData } from "./data/store";
import { fetchDealDetail, type DealDetail } from "./data/fetchDetail";
import Sidebar, { SidebarProvider, useSidebar } from "./layout/Sidebar";
import { Icon } from "./views/components";
import PipelineView from "./views/pipeline/PipelineView";
import DealWorkspace from "./views/pipeline/DealWorkspace";
import ForecastView from "./views/forecast/ForecastView";
import OneOnOneView from "./views/oneone/OneOnOneView";
import TodoView from "./views/todo/TodoView";
import ComingSoon from "./views/ComingSoon";
const AdminView = lazy(() => import("./views/admin/AdminView"));

function SidebarToggle() {
  const { toggle, expanded } = useSidebar();
  return (
    <button className="cz-sb-toggle" onClick={toggle} title={expanded ? "Collapse (⌘B)" : "Expand (⌘B)"}>
      <Icon name="panelLeft" size={18} />
    </button>
  );
}

function App() {
  const D = useData();
  const [view, setView] = useState("forecast");
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
      <SidebarProvider>
        <div className="cz-app">
          <Sidebar view={view} onNav={setView}/>
          <main className="cz-main" style={{display:"flex",alignItems:"center",justifyContent:"center",minHeight:"60vh"}}>
            <SidebarToggle/>
            <p style={{color:"var(--ink-3)",fontSize:15}}>Cargando datos...</p>
          </main>
        </div>
      </SidebarProvider>
    );
  }

  return (
    <SidebarProvider>
      <div className="cz-app">
        <Sidebar view={view} onNav={setView}/>
        <main className="cz-main">
          <SidebarToggle/>
          {view === "todos" && <TodoView onOpen={handleOpen}/>}
          {view === "pipeline" && <PipelineView onOpen={handleOpen}/>}
          {view === "forecast" && <ForecastView onOpen={handleOpen}/>}
          {view === "oneone" && <OneOnOneView onOpen={handleOpen}/>}
          {view === "admin" && <Suspense fallback={<p style={{color:"var(--ink-3)"}}>Cargando...</p>}><AdminView/></Suspense>}
          {["general","benchmark","alerts","uplift"].includes(view) && <ComingSoon label={view.charAt(0).toUpperCase() + view.slice(1)}/>}
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
    </SidebarProvider>
  );
}

export default App;
