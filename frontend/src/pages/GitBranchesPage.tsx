import { GitBranch, GitCommitHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { formatRelativeTime, initialsColor } from "../lib/format";
import { usePodStore } from "../store/podStore";
import { Avatar } from "../components/common/Avatar";
import "./GitBranchesPage.css";

interface Commit {
  sha: string;
  author: string;
  date: string;
  subject: string;
  refs: string;
}

export function GitBranchesPage() {
  const hasProject = usePodStore((s) => s.hasProject);
  const agents = usePodStore((s) => s.agents);
  const events = usePodStore((s) => s.events);
  const [branches, setBranches] = useState<string[]>([]);
  const [commits, setCommits] = useState<Commit[]>([]);

  useEffect(() => {
    if (!hasProject) return;
    let cancelled = false;
    const load = () => {
      Promise.all([api.listBranches(), api.listCommits(50)]).then(([b, c]) => {
        if (!cancelled) {
          setBranches(b);
          setCommits(c);
        }
      });
    };
    load();
    const interval = setInterval(load, 6000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasProject, events.length]);

  if (!hasProject) {
    return (
      <div className="panel empty-state">
        <GitBranch size={28} />
        <div>No project yet.</div>
      </div>
    );
  }

  return (
    <div className="git-page">
      <div className="panel git-branches-panel">
        <div className="panel-header">
          <div className="panel-title">
            <GitBranch size={16} /> Branches
          </div>
        </div>
        <div className="git-branch-list">
          {branches.map((b) => {
            const agent = agents.find((a) => a.branch === b);
            return (
              <div key={b} className="git-branch-row">
                {agent ? (
                  <Avatar name={agent.avatar_initials} color={agent.color} size={22} />
                ) : (
                  <Avatar name="M" color="#495057" size={22} />
                )}
                <span className="git-branch-name">{b}</span>
                {agent && <span className="git-branch-agent">{agent.display_name}</span>}
              </div>
            );
          })}
          {branches.length === 0 && <div className="dash-card-empty">No branches yet.</div>}
        </div>
      </div>

      <div className="panel git-commits-panel">
        <div className="panel-header">
          <div className="panel-title">
            <GitCommitHorizontal size={16} /> Commit History
          </div>
        </div>
        <div className="git-commit-list">
          {commits.map((c) => (
            <div key={c.sha} className="git-commit-row">
              <Avatar name={c.author.slice(0, 2).toUpperCase()} color={initialsColor(c.author)} size={24} />
              <div className="git-commit-body">
                <div className="git-commit-subject">{c.subject.split("\n")[0]}</div>
                <div className="git-commit-meta">
                  <span className="git-commit-sha">{c.sha}</span>
                  <span>{c.author}</span>
                  <span>{formatRelativeTime(c.date)}</span>
                </div>
              </div>
            </div>
          ))}
          {commits.length === 0 && <div className="dash-card-empty">No commits yet.</div>}
        </div>
      </div>
    </div>
  );
}
