import { KanbanSquare } from "lucide-react";
import { useMemo, useState } from "react";

import type { TaskStatus } from "../api/types";
import { usePodStore } from "../store/podStore";
import { Avatar } from "../components/common/Avatar";
import "./TasksBacklogPage.css";

const STATUS_BADGE: Record<TaskStatus, string> = {
  backlog: "badge-neutral",
  ready: "badge-blue",
  in_progress: "badge-blue",
  blocked: "badge-red",
  review: "badge-amber",
  completed: "badge-green",
};

const RISK_BADGE: Record<string, string> = { low: "badge-neutral", medium: "badge-amber", high: "badge-red" };

const STATUS_FILTERS: Array<TaskStatus | "all"> = ["all", "backlog", "ready", "in_progress", "blocked", "review", "completed"];

export function TasksBacklogPage() {
  const backlog = usePodStore((s) => s.backlog);
  const agents = usePodStore((s) => s.agents);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");

  const tasks = useMemo(() => {
    if (!backlog) return [];
    const all = Object.values(backlog.tasks);
    return statusFilter === "all" ? all : all.filter((t) => t.status === statusFilter);
  }, [backlog, statusFilter]);

  if (!backlog) {
    return (
      <div className="panel empty-state">
        <KanbanSquare size={28} />
        <div>No backlog yet -- start a project and run the pipeline first.</div>
      </div>
    );
  }

  return (
    <div className="panel backlog-page">
      <div className="panel-header">
        <div className="panel-title">
          <KanbanSquare size={16} /> Tasks &amp; Backlog
        </div>
        <div className="backlog-filters">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              className={"conversation-tab" + (statusFilter === s ? " active" : "")}
              onClick={() => setStatusFilter(s)}
            >
              {s.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <div className="backlog-table">
        <div className="backlog-row backlog-row-head">
          <span>Task</span>
          <span>Specialty</span>
          <span>Assignee</span>
          <span>Status</span>
          <span>Risk</span>
          <span>Depends on</span>
        </div>
        {tasks.map((task) => {
          const agent = agents.find((a) => a.agent_id === task.assigned_agent_id);
          return (
            <div className="backlog-row" key={task.task_id}>
              <span className="backlog-task-title" title={task.description}>
                {task.title}
                {task.blocked_reason && <div className="backlog-blocked-reason">{task.blocked_reason}</div>}
              </span>
              <span className="badge badge-neutral">{task.specialty.replace("_", " ")}</span>
              <span className="backlog-assignee">
                {agent && <Avatar name={agent.avatar_initials} color={agent.color} size={20} />}
                {agent?.display_name ?? "—"}
              </span>
              <span className={"badge " + STATUS_BADGE[task.status]}>{task.status.replace("_", " ")}</span>
              <span className={"badge " + (RISK_BADGE[task.risk] ?? "badge-neutral")}>{task.risk}</span>
              <span className="backlog-deps">
                {task.depends_on.length
                  ? task.depends_on.map((id) => backlog.tasks[id]?.title ?? id).join(", ")
                  : "—"}
              </span>
            </div>
          );
        })}
        {tasks.length === 0 && <div className="backlog-empty">No tasks match this filter.</div>}
      </div>
    </div>
  );
}
