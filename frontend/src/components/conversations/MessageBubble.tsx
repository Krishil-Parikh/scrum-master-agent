import type { Message } from "../../api/types";
import { formatClockTime } from "../../lib/format";
import { initialsColor } from "../../lib/format";
import { usePodStore } from "../../store/podStore";
import { Avatar } from "../common/Avatar";

const ROLE_BADGE_CLASS: Record<string, string> = {
  Scrum: "badge-blue",
  Developer: "badge-neutral",
  SME: "badge-green",
  System: "badge-neutral",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function renderText(text: string) {
  const parts = text.split(/(@[\w-]+)/g);
  return parts.map((part, i) =>
    part.startsWith("@") ? (
      <span key={i} className="message-mention">
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

export function MessageBubble({ message }: { message: Message }) {
  const agents = usePodStore((s) => s.agents);
  const agent = agents.find((a) => a.agent_id === message.sender_id);
  const color = agent?.color ?? initialsColor(message.sender_name);
  const avatarInitials = agent?.avatar_initials ?? initials(message.sender_name);

  return (
    <div className="message-row">
      <Avatar name={avatarInitials} color={color} size={32} />
      <div className="message-body">
        <div className="message-meta">
          <span className="message-sender">{message.sender_name}</span>
          {message.sender_role && (
            <span className={`badge ${ROLE_BADGE_CLASS[message.sender_role] ?? "badge-neutral"}`}>
              {message.sender_role}
            </span>
          )}
          <span className="message-time">{formatClockTime(message.created_at)}</span>
        </div>
        <div className="message-text">{renderText(message.text)}</div>
      </div>
    </div>
  );
}
