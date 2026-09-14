import { CalendarRange } from "lucide-react";
import { Link } from "react-router-dom";

import { usePodStore } from "../../store/podStore";

export function CurrentSprintCard() {
  const backlog = usePodStore((s) => s.backlog);
  const sprint = backlog?.current_sprint_id ? backlog.sprints[backlog.current_sprint_id] : undefined;

  if (!backlog || !sprint) {
    return (
      <div className="panel dash-card">
        <div className="dash-card-title">
          <CalendarRange size={14} /> Current Sprint
        </div>
        <div className="dash-card-empty">No sprint planned yet.</div>
      </div>
    );
  }

  const tasks = sprint.task_ids.map((id) => backlog.tasks[id]).filter(Boolean);
  const completed = tasks.filter((t) => t.status === "completed").length;
  const pct = tasks.length ? Math.round((completed / tasks.length) * 100) : 0;

  return (
    <div className="panel dash-card">
      <div className="dash-card-title">
        <CalendarRange size={14} /> Current Sprint
      </div>
      <div className="dash-sprint-name">{sprint.name}</div>
      <div className="dash-sprint-goal">{sprint.goal}</div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="dash-sprint-footer">
        <span>
          {completed} of {tasks.length} tasks completed
        </span>
        <Link to="/agile-board" className="dash-card-link">
          View Sprint →
        </Link>
      </div>
    </div>
  );
}
