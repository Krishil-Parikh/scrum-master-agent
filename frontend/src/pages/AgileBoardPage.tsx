import { Trello } from "lucide-react";

import type { Task, TaskStatus } from "../api/types";
import { usePodStore } from "../store/podStore";
import { Avatar } from "../components/common/Avatar";
import "./AgileBoardPage.css";

const COLUMNS: Array<{ status: TaskStatus; label: string }> = [
  { status: "backlog", label: "Backlog" },
  { status: "ready", label: "Ready" },
  { status: "in_progress", label: "In Progress" },
  { status: "review", label: "Review" },
  { status: "blocked", label: "Blocked" },
  { status: "completed", label: "Completed" },
];

export function AgileBoardPage() {
  const backlog = usePodStore((s) => s.backlog);
  const agents = usePodStore((s) => s.agents);

  if (!backlog) {
    return (
      <div className="panel empty-state">
        <Trello size={28} />
        <div>No backlog yet -- start a project and run the pipeline first.</div>
      </div>
    );
  }

  const tasksByStatus = (status: TaskStatus) => Object.values(backlog.tasks).filter((t) => t.status === status);
  const storyOf = (task: Task) => backlog.stories[task.story_id];
  const epicOf = (task: Task) => {
    const story = storyOf(task);
    return story ? backlog.epics[story.epic_id] : undefined;
  };

  return (
    <div className="agile-board">
      {COLUMNS.map((col) => {
        const tasks = tasksByStatus(col.status);
        return (
          <div key={col.status} className="agile-column">
            <div className="agile-column-header">
              <span>{col.label}</span>
              <span className="badge badge-neutral">{tasks.length}</span>
            </div>
            <div className="agile-column-body">
              {tasks.map((task) => {
                const agent = agents.find((a) => a.agent_id === task.assigned_agent_id);
                const epic = epicOf(task);
                return (
                  <div key={task.task_id} className="agile-card">
                    {epic && <div className="agile-card-epic">{epic.title}</div>}
                    <div className="agile-card-title">{task.title}</div>
                    <div className="agile-card-footer">
                      <span className="badge badge-neutral">{task.specialty.replace("_", " ")}</span>
                      {agent && <Avatar name={agent.avatar_initials} color={agent.color} size={20} />}
                    </div>
                  </div>
                );
              })}
              {tasks.length === 0 && <div className="agile-column-empty">Nothing here.</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
