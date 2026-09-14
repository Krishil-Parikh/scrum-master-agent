import type {
  Agent,
  Backlog,
  BootstrapResponse,
  EventItem,
  Message,
  MessageChannel,
  ProjectContext,
  RunState,
  SMEQuestionRecord,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  bootstrap: () => request<BootstrapResponse>("/api/bootstrap"),
  health: () =>
    request<{ status: string; env: string; model: string; llm_keys_configured: number; sme_mode: string }>(
      "/api/health",
    ),

  intakeText: (name: string, text: string) =>
    request<ProjectContext>("/api/project/intake", {
      method: "POST",
      body: JSON.stringify({ name, text }),
    }),

  intakeFile: async (name: string, file: File) => {
    const form = new FormData();
    form.append("name", name);
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/api/project/intake/file`, { method: "POST", body: form });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return (await res.json()) as ProjectContext;
  },

  currentProject: () => request<ProjectContext>("/api/project/current"),

  listDocs: () => request<string[]>("/api/project/docs"),
  getDoc: (name: string) => request<{ name: string; content: string }>(`/api/project/docs/${name}`),

  startRun: () => request<{ status: string }>("/api/run/start", { method: "POST" }),
  pauseRun: () => request<{ status: string }>("/api/run/pause", { method: "POST" }),
  resumeRun: () => request<{ status: string }>("/api/run/resume", { method: "POST" }),
  stopRun: () => request<{ status: string }>("/api/run/stop", { method: "POST" }),
  runStatus: () => request<RunState>("/api/run/status"),

  listAgents: () => request<Agent[]>("/api/agents"),

  listMessages: (channel?: MessageChannel) =>
    request<Message[]>(`/api/conversations${channel ? `?channel=${channel}` : ""}`),
  sendMessage: (channel: MessageChannel, text: string, sender_name = "Business SME") =>
    request<Message>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ channel, text, sender_name }),
    }),

  getBacklog: () => request<Backlog>("/api/backlog"),
  getCurrentSprint: () =>
    request<{ sprint: unknown; tasks: unknown[]; completed_count: number; total_count: number; progress_pct: number }>(
      "/api/sprint/current",
    ),

  listBranches: () => request<string[]>("/api/git/branches"),
  listCommits: (limit = 30) => request<Array<{ sha: string; author: string; date: string; subject: string; refs: string }>>(
    `/api/git/commits?limit=${limit}`,
  ),

  listEvents: (channel?: string, limit = 300) =>
    request<EventItem[]>(`/api/events?limit=${limit}${channel ? `&channel=${channel}` : ""}`),

  listSmeQuestions: (openOnly = true) => request<SMEQuestionRecord[]>(`/api/sme/questions?open_only=${openOnly}`),
  answerSmeQuestion: (question_id: string, text: string, decision = "") =>
    request("/api/sme/answer", { method: "POST", body: JSON.stringify({ question_id, text, decision }) }),
};

export { ApiError };
