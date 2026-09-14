import { CalendarClock } from "lucide-react";
import { Link } from "react-router-dom";

import type { MessageChannel } from "../../api/types";
import { usePodStore } from "../../store/podStore";

interface Ceremony {
  label: string;
  channel: MessageChannel;
  done: (haystack: string) => boolean;
}

const CEREMONIES: Ceremony[] = [
  { label: "SME Sync", channel: "sme", done: (h) => h.includes("business sme:") },
  { label: "Sprint Review", channel: "scrum", done: (h) => h.includes("sprint review") },
  { label: "Retrospective", channel: "scrum", done: (h) => h.includes("retrospective complete") },
];

export function UpcomingMeetingsCard() {
  const messages = usePodStore((s) => s.messages);
  const haystack = messages.map((m) => m.text.toLowerCase()).join(" \n ");

  return (
    <div className="panel dash-card">
      <div className="dash-card-title">
        <CalendarClock size={14} /> Ceremonies
      </div>
      <div className="dash-meeting-list">
        {CEREMONIES.map((c) => {
          const isDone = c.done(haystack);
          return (
            <div key={c.label} className="dash-meeting-row">
              <div>
                <div className="dash-meeting-name">{c.label}</div>
                <div className="dash-meeting-when">{isDone ? "Completed this sprint" : "Not yet run"}</div>
              </div>
              <Link to={`/conversations?channel=${c.channel}`} className={"btn btn-sm" + (isDone ? "" : " btn-ghost")}>
                {isDone ? "View" : "Open"}
              </Link>
            </div>
          );
        })}
      </div>
    </div>
  );
}
