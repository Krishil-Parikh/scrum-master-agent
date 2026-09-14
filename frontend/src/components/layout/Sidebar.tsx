import {
  Bot,
  GitBranch,
  KanbanSquare,
  LayoutDashboard,
  MessageSquare,
  Settings,
  SquareTerminal,
  Trello,
  FileText,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { usePodStore } from "../../store/podStore";
import { Avatar } from "../common/Avatar";
import "./Sidebar.css";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/conversations", label: "Conversations", icon: MessageSquare },
  { to: "/terminal", label: "Terminal", icon: SquareTerminal },
  { to: "/backlog", label: "Tasks & Backlog", icon: KanbanSquare },
  { to: "/git", label: "Git & Branches", icon: GitBranch },
  { to: "/agile-board", label: "Agile Board", icon: Trello },
  { to: "/docs", label: "Project Docs", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const agents = usePodStore((s) => s.agents);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">
          <Bot size={20} />
        </div>
        <div>
          <div className="sidebar-brand-name">AI Dev Pod</div>
          <div className="sidebar-brand-tag">Build Together. Autonomously.</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => "sidebar-nav-item" + (isActive ? " active" : "")}
          >
            <Icon size={17} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-agents">
        <div className="sidebar-section-label">Agents</div>
        <div className="sidebar-agent-list">
          {agents.map((agent) => (
            <div key={agent.agent_id} className="sidebar-agent-row" title={agent.note || agent.state}>
              <Avatar name={agent.avatar_initials} color={agent.color} size={26} />
              <div className="sidebar-agent-info">
                <div className="sidebar-agent-name">{agent.display_name}</div>
                <div className="sidebar-agent-status">
                  <span className={"status-dot" + (agent.online ? " online" : "")} />
                  {agent.online ? agent.state.replace("_", " ") : "Offline"}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
