import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { useWebSocket } from "./hooks/useWebSocket";
import { AgileBoardPage } from "./pages/AgileBoardPage";
import { ConversationsPage } from "./pages/ConversationsPage";
import { Dashboard } from "./pages/Dashboard";
import { GitBranchesPage } from "./pages/GitBranchesPage";
import { ProjectDocsPage } from "./pages/ProjectDocsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksBacklogPage } from "./pages/TasksBacklogPage";
import { TerminalPage } from "./pages/TerminalPage";
import { usePodStore } from "./store/podStore";

export default function App() {
  const loadBootstrap = usePodStore((s) => s.loadBootstrap);
  const loaded = usePodStore((s) => s.loaded);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    loadBootstrap().catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to reach the backend."));
  }, [loadBootstrap]);

  // WebSocket connection lives for the whole app lifetime, independent of
  // which page is mounted, so live updates never drop on navigation.
  useWebSocket();

  if (!loaded && loadError) {
    return (
      <div className="app-boot-error">
        <h2>Can't reach the backend</h2>
        <p>{loadError}</p>
        <p>
          Make sure the FastAPI server is running (<code>uvicorn app.main:app --port 8000</code> from{" "}
          <code>backend/</code>) and that <code>VITE_API_BASE_URL</code> in <code>frontend/.env.local</code> points
          at it.
        </p>
      </div>
    );
  }

  if (!loaded) {
    return <div className="app-boot-loading">Loading AI Dev Pod...</div>;
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/conversations" element={<ConversationsPage />} />
        <Route path="/terminal" element={<TerminalPage />} />
        <Route path="/backlog" element={<TasksBacklogPage />} />
        <Route path="/git" element={<GitBranchesPage />} />
        <Route path="/agile-board" element={<AgileBoardPage />} />
        <Route path="/docs" element={<ProjectDocsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
