import { Rocket, Sparkles } from "lucide-react";
import { useState } from "react";

import { api, ApiError } from "../api/client";
import { usePodStore } from "../store/podStore";

const EXAMPLE_BRIEF = `Build an AI-powered task management platform for a small team.

Users can sign up, log in, and manage their profile. Users can create projects and, within a project, create tasks with a title, description, status, and assignee. An AI feature suggests a category (bug/feature/chore) for a new task based on its title and description. A dashboard shows task counts by status and category.

The API must validate all input server-side. The system should be deployable via Docker with a basic CI pipeline. Task data must be stored in a relational database.`;

export function NoProjectBanner() {
  const loadBootstrap = usePodStore((s) => s.loadBootstrap);
  const [name, setName] = useState("AI Task Management Platform");
  const [text, setText] = useState(EXAMPLE_BRIEF);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [autoStart, setAutoStart] = useState(true);

  const create = async () => {
    if (!name.trim() || !text.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      await api.intakeText(name.trim(), text.trim());
      if (autoStart) await api.startRun();
      await loadBootstrap();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create the project.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" style={{ maxWidth: 720, margin: "40px auto", padding: 28 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <Sparkles size={20} color="var(--accent-blue)" />
        <h2 style={{ margin: 0, fontSize: 19 }}>Start a new project</h2>
      </div>
      <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4, marginBottom: 18 }}>
        Give the pod a project name and a brief (or paste a full PRD). The Scrum Master and six developer
        agents will analyze it, clarify ambiguities with the Business SME, plan a sprint, and start building
        — for real, on isolated Git branches.
      </p>

      <label className="form-label">Project name</label>
      <input className="input" value={name} onChange={(e) => setName(e.target.value)} style={{ marginBottom: 14 }} />

      <label className="form-label">Project brief / PRD</label>
      <textarea
        className="input"
        rows={10}
        value={text}
        onChange={(e) => setText(e.target.value)}
        style={{ marginBottom: 14, resize: "vertical", fontFamily: "inherit" }}
      />

      <label className="form-checkbox">
        <input type="checkbox" checked={autoStart} onChange={(e) => setAutoStart(e.target.checked)} />
        Start the full pipeline immediately after creating the project
      </label>

      {error && <div className="form-error">{error}</div>}

      <button className="btn btn-primary" onClick={create} disabled={busy} style={{ marginTop: 16 }}>
        <Rocket size={15} /> {busy ? "Creating..." : "Create Project"}
      </button>
    </div>
  );
}
