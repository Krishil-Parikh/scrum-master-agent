import { create } from "zustand";

import { api } from "../api/client";
import type { Agent, Backlog, EventItem, Message, ProjectContext, RunState, SMEQuestionRecord } from "../api/types";

const MAX_EVENTS = 800;
const MAX_MESSAGES = 800;

interface PodStore {
  loaded: boolean;
  hasProject: boolean;
  context: ProjectContext | null;
  backlog: Backlog | null;
  agents: Agent[];
  messages: Message[];
  events: EventItem[];
  smeQuestions: SMEQuestionRecord[];
  run: RunState;
  wsConnected: boolean;

  loadBootstrap: () => Promise<void>;
  applyEvent: (event: EventItem) => void;
  setWsConnected: (connected: boolean) => void;
  refreshBacklog: () => Promise<void>;
  refreshAgents: () => Promise<void>;
  refreshSmeQuestions: () => Promise<void>;
  refreshContext: () => Promise<void>;
  refreshRun: () => Promise<void>;
  appendLocalMessage: (message: Message) => void;
}

let backlogRefreshTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * A message a human sends arrives twice: once as the direct POST response
 * (appended immediately for a snappy UI) and once more via the WebSocket
 * broadcast the backend fans out to every client, itself included. Dedupe
 * by message_id rather than skipping the optimistic append, so the sender
 * still sees their own message instantly.
 */
function addMessage(set: (fn: (state: PodStore) => Partial<PodStore>) => void, message: Message): void {
  set((state) => {
    if (state.messages.some((m) => m.message_id === message.message_id)) return {};
    return { messages: [...state.messages, message].slice(-MAX_MESSAGES) };
  });
}

export const usePodStore = create<PodStore>((set, get) => ({
  loaded: false,
  hasProject: false,
  context: null,
  backlog: null,
  agents: [],
  messages: [],
  events: [],
  smeQuestions: [],
  run: { status: "idle", current_phase: "" },
  wsConnected: false,

  loadBootstrap: async () => {
    const data = await api.bootstrap();
    set({
      loaded: true,
      hasProject: data.has_project,
      context: data.context,
      backlog: data.backlog,
      agents: data.agents,
      messages: data.messages,
      events: data.events,
      smeQuestions: data.sme_questions ?? [],
      run: data.run,
    });
  },

  refreshBacklog: async () => {
    if (!get().hasProject) return;
    try {
      const backlog = await api.getBacklog();
      set({ backlog });
    } catch {
      // best-effort -- a live event stream will eventually catch us up again
    }
  },

  refreshAgents: async () => {
    try {
      const agents = await api.listAgents();
      set({ agents });
    } catch {
      /* ignore transient failures */
    }
  },

  refreshSmeQuestions: async () => {
    if (!get().hasProject) return;
    try {
      const smeQuestions = await api.listSmeQuestions(true);
      set({ smeQuestions });
    } catch {
      /* ignore */
    }
  },

  refreshContext: async () => {
    if (!get().hasProject) return;
    try {
      const context = await api.currentProject();
      set({ context });
    } catch {
      /* ignore */
    }
  },

  refreshRun: async () => {
    try {
      const run = await api.runStatus();
      set({ run });
    } catch {
      /* ignore -- the WS stream will catch us up */
    }
  },

  appendLocalMessage: (message) => addMessage(set, message),

  setWsConnected: (connected) => set({ wsConnected: connected }),

  applyEvent: (event) => {
    set((state) => ({ events: [...state.events, event].slice(-MAX_EVENTS) }));

    const { type, payload, actor_id } = event;

    if (type === "MESSAGE_POSTED") {
      const message: Message = {
        message_id: (payload.message_id as string) ?? crypto.randomUUID(),
        channel: (payload.channel as Message["channel"]) ?? "system",
        sender_id: actor_id ?? "system",
        sender_name: (payload.sender_name as string) ?? actor_id ?? "System",
        sender_role: (payload.sender_role as string) ?? "",
        text: (payload.text as string) ?? "",
        mentions: (payload.mentions as string[]) ?? [],
        reply_to: null,
        created_at: event.created_at,
      };
      addMessage(set, message);
      return;
    }

    if (type === "AGENT_STATE_CHANGED" && actor_id) {
      set((state) => ({
        agents: state.agents.map((a) =>
          a.agent_id === actor_id
            ? { ...a, state: (payload.state as Agent["state"]) ?? a.state, note: (payload.note as string) ?? "" }
            : a,
        ),
      }));
      return;
    }

    if (
      [
        "TASK_ASSIGNED",
        "TASK_STARTED",
        "TASK_BLOCKED",
        "TASK_COMPLETED",
        "SPRINT_STARTED",
        "PHASE_COMPLETED",
        "MERGE_RESOLVED",
      ].includes(type)
    ) {
      if (backlogRefreshTimer) clearTimeout(backlogRefreshTimer);
      backlogRefreshTimer = setTimeout(() => get().refreshBacklog(), 300);
    }

    if (type === "SME_QUESTION_CREATED" || type === "SME_RESPONSE_RECEIVED") {
      get().refreshSmeQuestions();
    }

    if (type === "RETROSPECTIVE_CREATED" || type === "PHASE_COMPLETED") {
      get().refreshContext();
    }

    if (type === "PHASE_STARTED" || type === "PHASE_COMPLETED") {
      get().refreshRun();
    }
  },
}));
