import { Copy, MessagesSquare, Search, Send } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../api/client";
import type { Message, MessageChannel } from "../../api/types";
import { usePodStore } from "../../store/podStore";
import { MessageBubble } from "./MessageBubble";
import "./ConversationPanel.css";

const TABS: Array<{ key: MessageChannel | "all"; label: string }> = [
  { key: "all", label: "All" },
  { key: "scrum", label: "Scrum" },
  { key: "developers", label: "Developers" },
  { key: "sme", label: "SME" },
  { key: "system", label: "System" },
  { key: "git", label: "Git" },
  { key: "tasks", label: "Tasks" },
];

interface ConversationPanelProps {
  initialChannel?: MessageChannel | "all";
}

export function ConversationPanel({ initialChannel = "all" }: ConversationPanelProps) {
  const allMessages = usePodStore((s) => s.messages);
  const appendLocalMessage = usePodStore((s) => s.appendLocalMessage);
  const hasProject = usePodStore((s) => s.hasProject);
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>(initialChannel);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    let msgs = allMessages;
    if (tab !== "all") msgs = msgs.filter((m) => m.channel === tab);
    if (query.trim()) {
      const q = query.toLowerCase();
      msgs = msgs.filter((m) => m.text.toLowerCase().includes(q) || m.sender_name.toLowerCase().includes(q));
    }
    return msgs;
  }, [allMessages, tab, query]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [filtered.length]);

  const send = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setDraft("");
    try {
      const message: Message = await api.sendMessage(tab === "all" ? "sme" : (tab as MessageChannel), text);
      appendLocalMessage(message);
    } catch {
      // leave the draft area cleared but the message simply won't appear;
      // the WS reconnect / bootstrap reload will keep state consistent
    } finally {
      setSending(false);
    }
  };

  const copyAll = () => {
    const text = filtered.map((m) => `[${m.sender_name}] ${m.text}`).join("\n");
    navigator.clipboard?.writeText(text).catch(() => {});
  };

  return (
    <div className="panel conversation-panel">
      <div className="panel-header">
        <div className="panel-title">
          <MessagesSquare size={16} />
          Agent Conversations
        </div>
        <button className="btn btn-ghost btn-sm" onClick={copyAll}>
          <Copy size={13} /> Copy All
        </button>
      </div>

      <div className="conversation-toolbar">
        <div className="conversation-tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={"conversation-tab" + (tab === t.key ? " active" : "")}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="conversation-search">
          <Search size={13} />
          <input
            className="conversation-search-input"
            placeholder="Search conversations..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="conversation-list" ref={scrollRef}>
        {!hasProject ? (
          <div className="empty-state">
            <MessagesSquare size={28} />
            <div>No project yet. Create one from Settings to start the pod.</div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <MessagesSquare size={28} />
            <div>No messages yet in this channel.</div>
          </div>
        ) : (
          filtered.map((m) => <MessageBubble key={m.message_id} message={m} />)
        )}
      </div>

      <div className="conversation-composer">
        <input
          className="input"
          placeholder="Type a message to the team..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") send();
          }}
        />
        <button className="btn btn-primary" onClick={send} disabled={!draft.trim() || sending}>
          <Send size={14} /> Send
        </button>
      </div>
    </div>
  );
}
