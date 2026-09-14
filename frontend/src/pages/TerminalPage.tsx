import { LiveTerminal } from "../components/terminal/LiveTerminal";

export function TerminalPage() {
  return (
    <div style={{ height: "calc(100vh - var(--topbar-height) - 40px)" }}>
      <LiveTerminal />
    </div>
  );
}
