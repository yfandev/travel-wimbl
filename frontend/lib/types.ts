// Shapes mirror the backend: wimbl/schemas.py today, and the record field lists in CLAUDE.md for Phases 2–5.
// Keep field names identical to the backend so the live API can replace the mocks without a mapping layer.

export type AgentRole =
  | "sports_parent" | "football_parent"
  | "tickets" | "flights" | "hotels" | "transit" | "price_watch" | "coordination"
  | "controller" | "verifier" | "learning" | "discovery";

export type CheckStatus = "pending" | "passed" | "failed";
export type Decision = "continue" | "replan" | "stop" | "escalate";
export type RunStage =
  | "REQUEST" | "INFER CONSTRAINTS" | "FREEZE ACCEPTANCE CRITERIA" | "DISCOVER" | "PLAN"
  | "VERIFY" | "REPAIR" | "REPLAN" | "FINAL RESULT" | "RETROSPECTIVE";

/** One model call: a line of data/run_log.jsonl written by wimbl/runlog.py. model_id_returned is the source of truth. */
export interface RunRecord {
  run_id: string;
  agent_role: string;
  model_id_requested: string;
  model_id_returned: string | null;
  version_tag: string;
  prompt_version: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  cost_estimate_usd: number | null;
  tool_calls: string[];
  /** "demo" means no model call was made; never present it as real output. */
  status: "ok" | "error" | "timeout" | "demo";
  error: string | null;
  timestamp: string;
  attempts: number;
}

/** Lesson record from the Shared Brain (wimbl/memory/, Phase 4). */
export interface Lesson {
  lesson_id: string;
  lesson: string;
  topic: string;
  from_agent: string;
  scope: "global" | "sports" | "football" | `football.${string}` | "user";
  source_type: "web" | "run" | "user" | "seed";
  evidence_urls: string[];
  confidence: number;
  run_id: string | null;
  /** Ancestor lesson IDs. */
  lineage: string[];
  supersedes: string | null;
  /** 0–2. */
  weight: number;
  trips_validated: number;
  successes: number;
  failures: number;
  created_at: string;
  last_validated: string | null;
  expires_at: string | null;
  version_introduced: number;
  evaluation_status: "candidate" | "promoted" | "rejected";
  status: "active" | "conflict" | "superseded" | "archived";
  superseded_by: string | null;
}

/** A lesson a child cites. parent_version is e.g. "Football Parent v3", from scope_versions["football"]. */
export interface InheritedLesson { lesson_id: string; influence: number; parent_version: string }

export interface AgentNode {
  id: string;
  /** Known roles plus anything new the backend adds. */
  role: AgentRole | (string & {});
  label: string;
  version?: string | null;
  inherited: InheritedLesson[];
  /** false = lineage only (parents are selected for the run but run no code yet). Absent on mocks: treated as true. */
  executed?: boolean;
  note?: string;
}

/** A compiled, frozen acceptance check: a predicate over the package and its evidence. */
export interface AcceptanceCheck {
  check_id: string;
  description: string;
  status: CheckStatus;
  detail: string | null;
}

export interface ControllerDecision { at: string; stage: RunStage; decision: Decision; reason: string }
export interface MonitorAlert { at: string; kind: "drift" | "loop"; message: string }

/** Shared trip-facts board entry published by a sibling. */
export interface TripFact { key: string; value: string; from_agent: AgentRole; to_agents: AgentRole[]; source_url: string | null; observed_at: string }

export interface PackageItem {
  kind: "ticket" | "flight" | "hotel" | "transit";
  label: string;
  price: number | null;
  source_url: string | null;
  observed_at: string | null;
}

export interface TripPackage {
  rank: number;
  title: string;
  match: string;
  kickoff: string;
  items: PackageItem[];
  estimated_total: number | null;
  currency: string;
  status: "candidate" | "verified" | "needs_review" | "rejected";
  assumptions: string[];
  risks: string[];
}

/** Timeline events streamed (or replayed) during a run. */
export type RunEvent =
  | { t: number; type: "stage"; stage: RunStage }
  | { t: number; type: "spawn"; agent: AgentNode }
  | { t: number; type: "active"; agent_id: string | null }
  | { t: number; type: "fact"; fact: TripFact }
  | { t: number; type: "check"; check_id: string; status: CheckStatus; detail: string | null }
  | { t: number; type: "alert"; alert: MonitorAlert }
  | { t: number; type: "decision"; decision: ControllerDecision }
  | { t: number; type: "packages"; packages: TripPackage[] };

/** GET /api/runs/{id} (wimbl/api_data.py). Fields after `events` are optional because mocks don't carry them. */
export interface Run {
  run_id: string;
  goal: string;
  mode: "live" | "replayed" | "mock";
  criteria_hash: string;
  constraints: string[];
  assumptions: string[];
  /** null means the backend doesn't enforce that budget yet. */
  budget: { retries: number | null; wall_clock_s: number | null; tokens: number | null; tool_calls: number | null };
  checks: AcceptanceCheck[];
  events: RunEvent[];
  started_at?: string;
  elapsed_ms?: number;
  status?: TripResult["status"];
  steps?: string[];
  findings?: VerificationFinding[];
  evidence_ledger?: (Evidence & { candidate: string })[];
  model_calls?: RunRecord[];
  timing_note?: string;
  budget_note?: string;
  trip_result?: TripResult;
  /** The agents that actually ran. Absent on runs recorded before the backend reported them. */
  agents?: AgentNode[];
  facts?: TripFact[];
}

/** GET /api/runs, newest first. */
export interface RunSummary {
  run_id: string;
  goal: string;
  mode: Run["mode"];
  status: TripResult["status"];
  controller_decision: TripResult["controller_decision"];
  started_at: string;
  elapsed_ms: number;
  candidates: number;
  findings: number;
  evidence: number;
}

/** One row of the N+1 comparison; null means "not yet run". */
export interface EvalScore { mean: number; spread: number; runs: number }
export interface N1Report {
  candidate_version: string;
  baseline_version: string;
  change: { target: "prompt" | "playbook" | "tool_policy" | "routing" | "structure"; summary: string; hypothesis: string };
  gate: string[];
  metrics: { name: string; baseline: EvalScore | null; candidate: EvalScore | null; split: "benchmark" | "heldout"; lower_is_better?: boolean }[];
  decision: "promoted" | "rejected" | null;
  decision_reason: string | null;
  history: { version: string; at: string; note: string; status: "active" | "retired" | "rolled_back" }[];
  evaluator?: string;
  caveat?: string;
  report?: string;
}

/** GET /api/memory/ablation. The extras are present only when an evaluation has been recorded. */
export interface MemoryAblation {
  metrics: { name: string; memory_off: number | null; memory_on: number | null; unit: string }[];
  n?: { off: number; on: number };
  primary_checks?: string[];
  primary_delta?: number | null;
  primary_ci95?: [number, number] | null;
  full_score_ci95?: [number, number] | null;
  served_lessons?: string[];
  child_model?: string;
  caveat?: string;
  report?: string;
}

// ---- Live discovery (POST /api/trips/discover), mirrors wimbl/schemas.py ----

export interface TripRequest {
  interest: string;
  origin: string;
  budget: number;
  currency: string;
  days: number;
  dates: string | null;
  traveler_context: string | null;
}

/** One search result kept as evidence. source is "You.com" for live results, "demo" for backend fixtures. */
export interface Evidence {
  title: string;
  url: string;
  snippet: string;
  source: string;
  retrieved_at: string;
  /** True when You.com Contents fetched the page and it names the event. */
  verified: boolean;
  page_age: string | null;
  provider_request_id: string | null;
  cache_hit: boolean;
}

export interface TripCandidate {
  title: string;
  destination: string;
  event: string;
  dates: string | null;
  estimated_total: number | null;
  currency: string;
  rationale: string;
  evidence: Evidence[];
  caveats: string[];
  status: "candidate" | "verified" | "needs_review" | "rejected";
}

export interface VerificationFinding { severity: "info" | "warning" | "error"; code: string; message: string }

export interface TripResult {
  run_id: string;
  interest: string;
  status: "verified" | "needs_review" | "no_results" | "error";
  acceptance_criteria: string[];
  candidates: TripCandidate[];
  findings: VerificationFinding[];
  controller_decision: "stop" | "replan" | "escalate";
  steps: string[];
}
