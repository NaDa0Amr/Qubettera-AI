// Shared TypeScript interfaces for the Multi-Agent Opinion Simulation Platform frontend.
// All shapes mirror the FastAPI backend contract documented in the brief and API_REFERENCE.md.

// ---------------------------------------------------------------------------
// Personas
// ---------------------------------------------------------------------------

export interface Persona {
  id: string;
  name: string;
  role: string;
  background: string;
  stance: string;
  style: string;
  expertise: string[];
  priorities: string;
  retrieval_focus: string;
  personality_traits: string[];
}

export interface PersonasResponse {
  personas: Persona[];
}

// ---------------------------------------------------------------------------
// Discussions — history list
// ---------------------------------------------------------------------------

export interface DiscussionSummary {
  discussion_id: string;
  // Null for discussions that failed before a topic was recorded.
  topic: string | null;
  created_at: string;
  num_rounds: number | null;
  num_agents: number | null;
  status: "running" | "completed" | "failed";
  has_analytics: boolean;
}

export interface DiscussionsResponse {
  discussions: DiscussionSummary[];
}

// ---------------------------------------------------------------------------
// Discussion detail / transcript
// ---------------------------------------------------------------------------

export interface EvidenceItem {
  text: string;
  title: string | null;
  url: string | null;
  score: number;
  metadata?: Record<string, unknown>;
}

export interface DiscussionMessage {
  message_id: string;
  discussion_id: string;
  phase: "initial" | "discussion";
  round_number: number;
  sequence_number: number;
  sender_id: string;
  recipient_ids: string[];
  content: string;
  opinion: string;
  retrieval_query: string | null;
  evidence: EvidenceItem[];
  created_at: string;
}

export interface DiscussionGraph {
  directed: boolean;
  nodes: string[];
  edges: [string, string][];
}

export interface DiscussionBrief {
  objective: string;
  constraints: string[];
  topics: string[];
  strict_notes: string[];
}

export interface DiscussionConfig {
  brief: DiscussionBrief;
  participant_ids: string[];
  num_rounds: number;
  model_config: Record<string, unknown>;
}

export interface DiscussionDetail {
  discussion_id: string;
  topic: string;
  created_at: string;
  /** "running" = transcript is still being written; poll for updates.
   *  "completed" | "failed" = terminal state, no more events expected.
   *  "empty" = no turns yet.
   *  Undefined for replays synthesised from legacy flat-array responses. */
  status?: "running" | "completed" | "failed" | "empty";
  config: DiscussionConfig;
  graph: DiscussionGraph;
  messages: DiscussionMessage[];
}

// ---------------------------------------------------------------------------
// SSE event payloads from POST /week3/discuss
// ---------------------------------------------------------------------------

export interface StreamStartedData {
  discussion_id: string;
}

export interface DiscussionStartedData {
  event: "discussion_started";
  discussion_id: string;
  created_at: string;
  config: DiscussionConfig;
  graph: DiscussionGraph;
}

export interface TurnCompletedData {
  event: "turn_completed";
  discussion_id: string;
  created_at: string;
  message: DiscussionMessage;
  runtime_metadata?: Record<string, unknown>;
}

export interface DiscussionCompletedData {
  event: "discussion_completed";
  discussion_id: string;
  created_at: string;
  message_count: number;
  discussion_turn_count: number;
}

export interface DiscussionFailedData {
  event: "discussion_failed";
  discussion_id: string;
  error: string;
}

/** Emitted by on_llm_new_token in AgentCallbackHandler when streaming=True. */
/**
 * `round` is populated when the Week 3 adapter has set the thread-local
 * current round before invoking the agent (see week2_adapter.py). It may be
 * null if TurnRequest carries no round_number, in which case the frontend
 * falls back to inferring the round from completed messages.
 */
export interface TokenChunkData {
  event: "token_chunk";
  agent_id: string | null;
  round: number | null;
  token: string;
  run_id: string;
}

// ---------------------------------------------------------------------------
// Streaming discussion hook state
// ---------------------------------------------------------------------------

export type ParticipantStatus = "idle" | "speaking" | "spoke" | "errored";

export interface ParticipantState {
  id: string;
  status: ParticipantStatus;
}

export type DiscussionStreamStatus = "idle" | "streaming" | "done" | "error";

export interface DiscussionStreamState {
  status: DiscussionStreamStatus;
  discussionId: string | null;
  brief: DiscussionBrief | null;
  graph: DiscussionGraph | null;
  config: DiscussionConfig | null;
  messages: DiscussionMessage[];
  participants: Record<string, ParticipantState>;
  error: string | null;
  lastEventAt: number | null;
  /** ID of the agent currently generating a response (null when idle between turns). */
  streamingAgentId: string | null;
  /** Accumulated token buffer for the agent currently speaking. */
  streamingText: string;
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface OpinionChangeEntry {
  agent_id: string;
  round: number;
  stance: number | null;
  change: number | null;
  reasoning: string;
}

export interface AgreementEntry {
  round: number;
  agreement: number;
  n_agents: number;
}

export interface InfluenceEntry {
  agent_id: string;
  influence: number | null;
  condition_number: number | null;
  note: string | null;
}

export interface SentimentEntry {
  message_id: string;
  agent_id: string;
  round: number;
  sentiment: number;
  label: "positive" | "neutral" | "negative";
  confidence: number;
  method: string;
  text_length: number;
  token_count: number;
  truncated: boolean;
  note: string | null;
}

export interface AnalyticsMetadata {
  generated_at: string;
  stance_model: string;
  sentiment_model: string;
  stance_num_samples: number;
  task1_from_cache: boolean;
}

export interface SentimentAgentSummary {
  avg_sentiment: number;
  message_count: number;
}

export interface SentimentRoundSummary {
  avg_sentiment: number;
  message_count: number;
}

export interface SentimentDistribution {
  positive: number;
  neutral: number;
  negative: number;
}

/**
 * Shape of the `sentiment` key inside analytics_{id}.json.
 * The engine (src/analytics/engine.py) returns an object, NOT a flat array.
 */
export interface SentimentPayload {
  messages: SentimentEntry[];
  by_agent: Record<string, SentimentAgentSummary>;
  by_round: Record<string, SentimentRoundSummary>;
  distribution: SentimentDistribution;
  method: string;
  max_length?: number;
  message_count?: number;
  truncation?: unknown;
}

export interface AnalyticsPayload {
  discussion_id: string;
  proposition: string;
  objective: string;
  topics: string[];
  agent_ids: string[];
  edges: [string, string][];
  rounds: number;
  opinion_change: OpinionChangeEntry[];
  agreement: AgreementEntry[];
  influence: InfluenceEntry[];
  /** Object with messages[], by_agent, by_round, distribution — NOT a flat array. */
  sentiment: SentimentPayload;
  metadata: AnalyticsMetadata;
}

// ---------------------------------------------------------------------------
// Analytics stream hook state
// ---------------------------------------------------------------------------

export type MetricName =
  | "opinion_change"
  | "agreement"
  | "influence"
  | "sentiment"
  | "report"
  | "visuals";

export type MetricStatus =
  | { state: "pending" }
  | { state: "running" }
  | { state: "ready"; data: unknown; durationMs: number }
  | { state: "failed"; code: string; message: string };

export type AnalyticsStreamStatus =
  | "idle"
  | "streaming"
  | "completed"
  | "failed";

export interface AnalyticsState {
  discussionId: string | null;
  streamStatus: AnalyticsStreamStatus;
  progress: { completed: number; total: number };
  metrics: Record<MetricName, MetricStatus>;
  error: string | null;
}

// ---------------------------------------------------------------------------
// API error envelope
// ---------------------------------------------------------------------------

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    service?: string;
  };
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  nextjs: "ok";
  backend: "ok" | "down";
  backend_ready: boolean;
  checked_at: string;
}

// ---------------------------------------------------------------------------
// Discussion start request
// ---------------------------------------------------------------------------

export interface DiscussRequest {
  topic: string;
  participant_ids: string[] | null;
  num_rounds: number;
  mode: "live" | "fake";
}
