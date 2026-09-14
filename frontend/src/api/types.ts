/**
 * TypeScript mirrors of the backend's Pydantic schemas
 * (backend/app/schemas/*.py). Kept hand-in-sync deliberately rather than
 * codegen'd -- the surface is small and stable enough that a generator
 * would be more ceremony than the two files staying aligned by hand.
 */

export type AgentSpecialty =
  | "scrum_master"
  | "frontend"
  | "backend"
  | "ai_ml"
  | "devops"
  | "mlops"
  | "database";

export type AgentState =
  | "idle"
  | "analyzing"
  | "planning"
  | "working"
  | "waiting"
  | "blocked"
  | "reviewing"
  | "helping"
  | "syncing"
  | "resolving_conflict"
  | "completed"
  | "failed";

export interface Agent {
  agent_id: string;
  display_name: string;
  specialty: AgentSpecialty;
  branch: string | null;
  color: string;
  avatar_initials: string;
  state: AgentState;
  online: boolean;
  note?: string;
  current_task_id?: string | null;
  skills_used?: string[];
  last_active_at?: string;
}

export type MessageChannel = "scrum" | "developers" | "sme" | "system" | "git" | "tasks";

export interface Message {
  message_id: string;
  channel: MessageChannel;
  sender_id: string;
  sender_name: string;
  sender_role: string;
  text: string;
  mentions: string[];
  reply_to: string | null;
  created_at: string;
}

export interface EventItem {
  event_id: string;
  type: string;
  actor_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export type TaskStatus = "backlog" | "ready" | "in_progress" | "blocked" | "review" | "completed";
export type TaskRisk = "low" | "medium" | "high";

export interface Task {
  task_id: string;
  story_id: string;
  title: string;
  description: string;
  specialty: AgentSpecialty;
  assigned_agent_id: string | null;
  status: TaskStatus;
  risk: TaskRisk;
  depends_on: string[];
  acceptance_criteria: string[];
  branch: string | null;
  created_at: string;
  updated_at: string;
  blocked_reason: string | null;
  files_changed: string[];
}

export interface UserStory {
  story_id: string;
  epic_id: string;
  title: string;
  as_a: string;
  i_want: string;
  so_that: string;
  acceptance_criteria: string[];
  task_ids: string[];
}

export interface Epic {
  epic_id: string;
  title: string;
  description: string;
  story_ids: string[];
}

export interface Sprint {
  sprint_id: string;
  name: string;
  goal: string;
  story_ids: string[];
  task_ids: string[];
  started_at: string | null;
  ended_at: string | null;
  days: number;
  status: string;
}

export interface Backlog {
  epics: Record<string, Epic>;
  stories: Record<string, UserStory>;
  tasks: Record<string, Task>;
  sprints: Record<string, Sprint>;
  current_sprint_id: string | null;
}

export interface Requirement {
  requirement_id: string;
  text: string;
  kind: "functional" | "non_functional" | "constraint";
  source: string;
}

export interface Decision {
  decision_id: string;
  context: string;
  decision: string;
  alternatives: string[];
  reason: string;
  impact: string;
  created_at: string;
}

export interface OpenQuestion {
  question: string;
  reason: string;
  owner: string;
  priority: string;
  raised_by: string;
}

export interface ProjectContext {
  project_id: string;
  name: string;
  objective: string;
  business_context: string;
  requirements: Requirement[];
  constraints: string[];
  stakeholders: string[];
  domain_terms: Record<string, string>;
  acceptance_criteria: string[];
  technology_stack: string[];
  architecture_notes: string;
  decisions: Decision[];
  open_questions: OpenQuestion[];
  current_sprint_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SMEQuestionRecord {
  question: {
    question_id: string;
    asked_by: string;
    asked_by_name: string;
    text: string;
    reason: string;
    priority: string;
    impacted_requirements: string[];
    status: string;
    created_at: string;
  };
  answer: {
    answer_id: string;
    question_id: string;
    text: string;
    decision: string;
    answered_by: string;
    created_at: string;
  } | null;
}

export type RunStatus = "idle" | "running" | "paused" | "stopped" | "completed" | "failed";

export interface RunState {
  status: RunStatus;
  current_phase: string;
  elapsed_seconds?: number;
}

export interface BootstrapResponse {
  has_project: boolean;
  context: ProjectContext | null;
  backlog: Backlog | null;
  agents: Agent[];
  messages: Message[];
  events: EventItem[];
  sme_questions?: SMEQuestionRecord[];
  run: RunState;
  ws_clients: number;
}

export interface WsEnvelope {
  kind: "event";
  event: EventItem;
}
