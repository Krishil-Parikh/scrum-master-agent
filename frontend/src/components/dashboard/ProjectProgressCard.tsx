import { TrendingUp } from "lucide-react";

import { usePodStore } from "../../store/podStore";

export function ProjectProgressCard() {
  const backlog = usePodStore((s) => s.backlog);

  const tasks = backlog ? Object.values(backlog.tasks) : [];
  const completed = tasks.filter((t) => t.status === "completed").length;
  const total = tasks.length;
  const pct = total ? Math.round((completed / total) * 100) : 0;
  const sprint = backlog?.current_sprint_id ? backlog.sprints[backlog.current_sprint_id] : undefined;

  const daysRemaining = (() => {
    if (!sprint?.started_at || !sprint.days) return sprint?.days ?? "—";
    const started = new Date(sprint.started_at).getTime();
    const end = started + sprint.days * 86400000;
    const remaining = Math.max(0, Math.ceil((end - Date.now()) / 86400000));
    return remaining;
  })();

  return (
    <div className="panel dash-card">
      <div className="dash-card-title">
        <TrendingUp size={14} /> Project Progress
      </div>
      <div className="dash-progress-pct">{pct}%</div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="dash-stat-grid">
        <div className="dash-stat">
          <div className="dash-stat-label">Completed Tasks</div>
          <div className="dash-stat-value">
            {completed}/{total}
          </div>
        </div>
        <div className="dash-stat">
          <div className="dash-stat-label">Current Sprint</div>
          <div className="dash-stat-value">{sprint?.name ?? "—"}</div>
        </div>
        <div className="dash-stat">
          <div className="dash-stat-label">Days Remaining</div>
          <div className="dash-stat-value">{daysRemaining}</div>
        </div>
      </div>
    </div>
  );
}
