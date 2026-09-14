import { ListChecks } from "lucide-react";
import { Link } from "react-router-dom";

import { usePodStore } from "../../store/podStore";
import { Avatar } from "../common/Avatar";

const STATUS_BADGE: Record<string, string> = {
  in_progress: "badge-blue",
  review: "badge-amber",
  blocked: "badge-red",
  completed: "badge-green",
  ready: "badge-neutral",
  backlog: "badge-neutral",
};

export function ActiveTasksCard() {
  const backlog = usePodStore((s) => s.backlog);
  const agents = usePodStore((s) => s.agents);

  const tasks = backlog
    ? Object.values(backlog.tasks)
        .filter((t) => t.status === "in_progress" || t.status === "review" || t.status === "blocked")
        .slice(0, 5)
    : [];

  return (
    <div className="panel dash-card">
      <div className="dash-card-title">
        <ListChecks size={14} /> Active Tasks
      </div>
      {tasks.length === 0 ? (
        <div className="dash-card-empty">Nothing in progress right now.</div>
      ) : (
        <div className="dash-task-list">
          {tasks.map((task) => {
            const agent = agents.find((a) => a.agent_id === task.assigned_agent_id);
            return (
              <div key={task.task_id} className="dash-task-row">
                <span className="dash-task-title" title={task.title}>
                  {task.title}
                </span>
                {agent && <Avatar name={agent.avatar_initials} color={agent.color} size={20} />}
                <span className={"badge " + (STATUS_BADGE[task.status] ?? "badge-neutral")}>
                  {task.status.replace("_", " ")}
                </span>
              </div>
            );
          })}
        </div>
      )}
      <Link to="/backlog" className="dash-card-link dash-card-link-footer">
        View All Tasks →
      </Link>
    </div>
  );
}
