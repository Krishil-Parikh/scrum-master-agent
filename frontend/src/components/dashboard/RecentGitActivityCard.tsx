import { GitCommitHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { formatRelativeTime, initialsColor } from "../../lib/format";
import { usePodStore } from "../../store/podStore";
import { Avatar } from "../common/Avatar";

interface Commit {
  sha: string;
  author: string;
  date: string;
  subject: string;
  refs: string;
}

export function RecentGitActivityCard() {
  const hasProject = usePodStore((s) => s.hasProject);
  const events = usePodStore((s) => s.events);
  const [commits, setCommits] = useState<Commit[]>([]);

  useEffect(() => {
    if (!hasProject) return;
    let cancelled = false;
    const load = () => {
      api
        .listCommits(6)
        .then((data) => {
          if (!cancelled) setCommits(data);
        })
        .catch(() => {});
    };
    load();
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasProject, events.length]);

  return (
    <div className="panel dash-card">
      <div className="dash-card-title">
        <GitCommitHorizontal size={14} /> Recent Git Activity
      </div>
      {commits.length === 0 ? (
        <div className="dash-card-empty">No commits yet.</div>
      ) : (
        <div className="dash-git-list">
          {commits.map((c) => (
            <div key={c.sha} className="dash-git-row">
              <span className="dash-git-sha">{c.sha}</span>
              <span className="dash-git-subject" title={c.subject}>
                {c.subject.split("\n")[0]}
              </span>
              <span className="dash-git-time">{formatRelativeTime(c.date)}</span>
              <Avatar name={c.author.slice(0, 2).toUpperCase()} color={initialsColor(c.author)} size={18} />
            </div>
          ))}
        </div>
      )}
      <Link to="/git" className="dash-card-link dash-card-link-footer">
        View All →
      </Link>
    </div>
  );
}
