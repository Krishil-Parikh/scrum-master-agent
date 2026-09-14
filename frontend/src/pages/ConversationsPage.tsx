import { useSearchParams } from "react-router-dom";

import { ConversationPanel } from "../components/conversations/ConversationPanel";
import type { MessageChannel } from "../api/types";

export function ConversationsPage() {
  const [params] = useSearchParams();
  const channel = params.get("channel") as MessageChannel | null;

  return (
    <div style={{ height: "calc(100vh - var(--topbar-height) - 40px)" }}>
      <ConversationPanel initialChannel={channel ?? "all"} />
    </div>
  );
}
