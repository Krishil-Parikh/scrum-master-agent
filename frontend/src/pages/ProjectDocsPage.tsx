import { FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { MiniMarkdown } from "../lib/MiniMarkdown";
import { usePodStore } from "../store/podStore";
import "./ProjectDocsPage.css";

export function ProjectDocsPage() {
  const hasProject = usePodStore((s) => s.hasProject);
  const events = usePodStore((s) => s.events);
  const [docs, setDocs] = useState<string[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!hasProject) return;
    api.listDocs().then((names) => {
      setDocs(names);
      setActive((current) => current ?? names[0] ?? null);
    });
    // Refresh the doc list as the pipeline progresses and writes new files.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasProject, events.length]);

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    api
      .getDoc(active)
      .then((d) => setContent(d.content))
      .finally(() => setLoading(false));
  }, [active, events.length]);

  if (!hasProject) {
    return (
      <div className="panel empty-state">
        <FileText size={28} />
        <div>No project yet.</div>
      </div>
    );
  }

  return (
    <div className="docs-page">
      <div className="panel docs-sidebar">
        <div className="panel-header">
          <div className="panel-title">
            <FileText size={16} /> Project Docs
          </div>
        </div>
        <div className="docs-list">
          {docs.map((name) => (
            <button
              key={name}
              className={"docs-list-item" + (name === active ? " active" : "")}
              onClick={() => setActive(name)}
            >
              {name}
            </button>
          ))}
          {docs.length === 0 && <div className="dash-card-empty">No docs generated yet.</div>}
        </div>
      </div>

      <div className="panel docs-content">
        {loading ? (
          <div className="dash-card-empty">Loading...</div>
        ) : content ? (
          <MiniMarkdown text={content} />
        ) : (
          <div className="dash-card-empty">This document is empty so far.</div>
        )}
      </div>
    </div>
  );
}
