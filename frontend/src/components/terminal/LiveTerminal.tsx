import { Copy, SquareTerminal } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { usePodStore } from "../../store/podStore";
import "./LiveTerminal.css";

export function LiveTerminal() {
  const events = usePodStore((s) => s.events);
  const run = usePodStore((s) => s.run);
  const scrollRef = useRef<HTMLDivElement>(null);

  const lines = useMemo(
    () =>
      events
        .filter((e) => e.type === "RUN_LOG")
        .map((e) => ({
          id: e.event_id,
          text: (e.payload.text as string) ?? "",
          channel: (e.payload.channel as string) ?? "",
        })),
    [events],
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines.length]);

  const copyOutput = () => {
    const text = lines.map((l) => l.text).join("\n");
    navigator.clipboard?.writeText(text).catch(() => {});
  };

  return (
    <div className="panel terminal-panel">
      <div className="panel-header">
        <div className="panel-title">
          <SquareTerminal size={16} />
          Live Terminal
          <span className={"badge " + (run.status === "running" ? "badge-green" : "badge-neutral")}>
            <span className="badge-dot" /> {run.status === "running" ? "Running" : "Idle"}
          </span>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={copyOutput}>
          <Copy size={13} /> Copy Output
        </button>
      </div>
      <div className="terminal-body" ref={scrollRef}>
        {lines.length === 0 ? (
          <div className="terminal-placeholder">$ waiting for pod activity...</div>
        ) : (
          lines.map((l) => (
            <pre key={l.id} className={"terminal-line" + (l.channel === "test" ? " terminal-line-test" : "")}>
              {l.text}
            </pre>
          ))
        )}
      </div>
    </div>
  );
}
