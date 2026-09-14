import { Pause, Play, Square, Wifi, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { formatElapsed } from "../../lib/format";
import { usePodStore } from "../../store/podStore";
import { Avatar } from "../common/Avatar";
import "./TopBar.css";

export function TopBar() {
  const context = usePodStore((s) => s.context);
  const backlog = usePodStore((s) => s.backlog);
  const run = usePodStore((s) => s.run);
  const wsConnected = usePodStore((s) => s.wsConnected);
  const refreshRun = usePodStore((s) => s.refreshRun);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => refreshRun(), 4000);
    return () => clearInterval(interval);
  }, [refreshRun]);

  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (run.status !== "running") return;
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [run.status]);

  const elapsed = (run.elapsed_seconds ?? 0) + (run.status === "running" ? tick : 0);
  const sprint = backlog?.current_sprint_id ? backlog.sprints[backlog.current_sprint_id] : undefined;

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await refreshRun();
    } finally {
      setBusy(false);
    }
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-title">Project: {context?.name ?? "No project yet"}</div>
        {sprint && <span className="badge badge-blue">{sprint.name}</span>}
        <RunBadge status={run.status} />
        {run.status === "running" || run.status === "paused" ? (
          <span className="topbar-timer">{formatElapsed(elapsed)}</span>
        ) : null}
      </div>

      <div className="topbar-right">
        <div className="ws-indicator" title={wsConnected ? "Live updates connected" : "Reconnecting..."}>
          {wsConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
        </div>

        {run.status === "running" ? (
          <>
            <button className="btn btn-sm" disabled={busy} onClick={() => act(api.pauseRun)}>
              <Pause size={14} /> Pause
            </button>
            <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => act(api.stopRun)}>
              <Square size={14} /> Stop
            </button>
          </>
        ) : run.status === "paused" ? (
          <>
            <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => act(api.resumeRun)}>
              <Play size={14} /> Resume
            </button>
            <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => act(api.stopRun)}>
              <Square size={14} /> Stop
            </button>
          </>
        ) : (
          <button
            className="btn btn-primary btn-sm"
            disabled={busy || !context}
            onClick={() => act(api.startRun)}
            title={!context ? "Create a project first" : "Run the full pod pipeline"}
          >
            <Play size={14} /> {run.status === "completed" ? "Run Again" : "Start Run"}
          </button>
        )}

        <div className="topbar-user">
          <Avatar name="B" color="#1c7ed6" size={30} />
          <div>
            <div className="topbar-user-name">Business SME</div>
            <div className="topbar-user-status">
              <span className="status-dot online" /> Online
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

function RunBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    running: { cls: "badge-green", label: "Running" },
    paused: { cls: "badge-amber", label: "Paused" },
    stopped: { cls: "badge-red", label: "Stopped" },
    completed: { cls: "badge-blue", label: "Completed" },
    failed: { cls: "badge-red", label: "Failed" },
    idle: { cls: "badge-neutral", label: "Idle" },
  };
  const entry = map[status] ?? map.idle;
  return (
    <span className={`badge ${entry.cls}`}>
      <span className="badge-dot" /> {entry.label}
    </span>
  );
}
