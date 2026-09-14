import { Rocket, Settings as SettingsIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import { usePodStore } from "../store/podStore";
import "./SettingsPage.css";

export function SettingsPage() {
  const context = usePodStore((s) => s.context);
  const loadBootstrap = usePodStore((s) => s.loadBootstrap);
  const [health, setHealth] = useState<{ model: string; llm_keys_configured: number; sme_mode: string } | null>(
    null,
  );
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [autoStart, setAutoStart] = useState(true);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  const createProject = async () => {
    if (!name.trim() || !text.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      await api.intakeText(name.trim(), text.trim());
      if (autoStart) await api.startRun();
      await loadBootstrap();
      setName("");
      setText("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create project.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="settings-page">
      <div className="panel settings-card">
        <div className="panel-header">
          <div className="panel-title">
            <SettingsIcon size={16} /> Backend
          </div>
        </div>
        <div className="settings-body">
          <div className="settings-row">
            <span>API base URL</span>
            <code>{import.meta.env.VITE_API_BASE_URL}</code>
          </div>
          <div className="settings-row">
            <span>Model</span>
            <code>{health?.model ?? "—"}</code>
          </div>
          <div className="settings-row">
            <span>OpenRouter keys configured</span>
            <code>{health?.llm_keys_configured ?? "—"}</code>
          </div>
          <div className="settings-row">
            <span>SME mode</span>
            <code>{health?.sme_mode ?? "—"}</code>
          </div>
        </div>
      </div>

      <div className="panel settings-card">
        <div className="panel-header">
          <div className="panel-title">
            <SettingsIcon size={16} /> Current Project
          </div>
        </div>
        <div className="settings-body">
          {context ? (
            <>
              <div className="settings-row">
                <span>Name</span>
                <code>{context.name}</code>
              </div>
              <div className="settings-row">
                <span>Status</span>
                <code>{context.status}</code>
              </div>
              <div className="settings-row">
                <span>Project ID</span>
                <code>{context.project_id}</code>
              </div>
            </>
          ) : (
            <div className="dash-card-empty">No project created yet.</div>
          )}
        </div>
      </div>

      <div className="panel settings-card settings-card-wide">
        <div className="panel-header">
          <div className="panel-title">
            <Rocket size={16} /> Start a New Project
          </div>
        </div>
        <div className="settings-body">
          <label className="form-label">Project name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          <label className="form-label" style={{ marginTop: 12 }}>
            Project brief / PRD
          </label>
          <textarea
            className="input"
            rows={8}
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{ resize: "vertical", fontFamily: "inherit" }}
          />
          <label className="form-checkbox" style={{ marginTop: 12 }}>
            <input type="checkbox" checked={autoStart} onChange={(e) => setAutoStart(e.target.checked)} />
            Start the full pipeline immediately after creating the project
          </label>
          {error && <div className="form-error">{error}</div>}
          <button className="btn btn-primary" onClick={createProject} disabled={busy} style={{ marginTop: 14 }}>
            <Rocket size={15} /> {busy ? "Creating..." : "Create Project"}
          </button>
          <p className="settings-note">
            This starts a brand-new project run. The previous project's history stays on disk under
            backend/project_data/ and backend/workspace/.
          </p>
        </div>
      </div>
    </div>
  );
}
