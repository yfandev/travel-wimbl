// MOCK DATA. Shaped like the backend's records so screens can be built before the API exists.
// Nothing here is a real observation: URLs point at example.org, and model metrics are null ("not yet run").
import type { AgentNode, Lesson, MemoryAblation, N1Report, Run, RunEvent, RunRecord } from "./types";
import { ROUTES } from "./routing";

const src = (path: string) => `https://example.org/mock/${path}`;
const at = (min: number, sec = 0) => `2026-10-17T15:${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}Z`;

const lesson = (l: Partial<Lesson> & Pick<Lesson, "lesson_id" | "lesson" | "topic" | "from_agent" | "scope">): Lesson => ({
  source_type: "web", evidence_urls: [], confidence: 0.8, run_id: null, lineage: [], supersedes: null, weight: 1,
  trips_validated: 0, successes: 0, failures: 0, created_at: "2026-10-17T15:00:00Z", last_validated: null, expires_at: null,
  version_introduced: 3, evaluation_status: "promoted", status: "active", superseded_by: null, ...l,
});

export const MOCK_LESSONS: Lesson[] = [
  lesson({
    lesson_id: "L-mock0007", topic: "ticket_source_order", from_agent: "tickets", scope: "football.tickets", source_type: "seed",
    lesson: "Check the club's official ticketing page before any resale site; general sale often opens 2–4 weeks before kickoff.",
    evidence_urls: [src("club-ticketing"), src("ticket-sale-calendar")], confidence: 0.9, weight: 1.64,
    trips_validated: 4, successes: 3, failures: 1, last_validated: "2026-10-12T00:00:00Z", expires_at: "2027-01-12T00:00:00Z",
  }),
  lesson({
    lesson_id: "L-mock0011", topic: "kickoff_time_risk", from_agent: "flights", scope: "football", source_type: "web",
    lesson: "La Liga kickoff times are confirmed late; plan arrival for the earliest plausible slot, not the provisional one.",
    evidence_urls: [src("league-scheduling")], weight: 1.28, trips_validated: 2, successes: 2,
    last_validated: "2026-10-03T00:00:00Z", expires_at: "2026-12-31T00:00:00Z", evaluation_status: "candidate",
  }),
  lesson({
    lesson_id: "L-mock0003", topic: "matchday_hotel_location", from_agent: "hotels", scope: "football", source_type: "web",
    lesson: "Book hotels within 2 km of the stadium for night matches.",
    evidence_urls: [src("forum-thread")], confidence: 0.4, weight: 0, trips_validated: 1, failures: 1,
    last_validated: "2026-09-20T00:00:00Z", version_introduced: 2, status: "superseded", superseded_by: "L-mock0009",
  }),
  lesson({
    lesson_id: "L-mock0009", topic: "matchday_hotel_location", from_agent: "transit", scope: "football", source_type: "run",
    lesson: "For night matches, prefer hotels on a direct metro line to the stadium over raw distance.",
    evidence_urls: [src("metro-map"), src("matchday-transport")], confidence: 0.75, weight: 1.14, run_id: "mock-run-0000",
    trips_validated: 2, successes: 2, last_validated: "2026-10-10T00:00:00Z", supersedes: "L-mock0003",
  }),
  lesson({
    lesson_id: "L-mock0002", topic: "arrival_buffer", from_agent: "coordination", scope: "sports", source_type: "seed",
    lesson: "Leave at least 4 hours between scheduled arrival and any fixed-time event.",
    evidence_urls: [src("delay-statistics")], confidence: 0.85, weight: 1.42, version_introduced: 2,
    trips_validated: 5, successes: 4, failures: 1, last_validated: "2026-10-14T00:00:00Z",
  }),
];

const child = (role: AgentNode["role"], label: string, inherited: AgentNode["inherited"]): AgentNode =>
  ({ id: role, role, label, inherited });

const FOOTBALL_V3 = "Football Parent v3";
const children: AgentNode[] = [
  child("tickets", "Tickets", [{ lesson_id: "L-mock0007", influence: 1.64, parent_version: FOOTBALL_V3 }]),
  child("flights", "Flights", [{ lesson_id: "L-mock0011", influence: 1.28, parent_version: FOOTBALL_V3 }, { lesson_id: "L-mock0002", influence: 1.42, parent_version: "Sports Parent v2" }]),
  child("hotels", "Hotels", [{ lesson_id: "L-mock0009", influence: 1.14, parent_version: FOOTBALL_V3 }]),
  child("transit", "Transit", [{ lesson_id: "L-mock0009", influence: 1.14, parent_version: FOOTBALL_V3 }]),
  child("price_watch", "Price watch", []),
];

const events: RunEvent[] = [
  { t: 0, type: "stage", stage: "REQUEST" },
  { t: 0, type: "spawn", agent: { id: "sports_parent", role: "sports_parent", label: "Sports Parent", version: "v2", inherited: [] } },
  { t: 0, type: "spawn", agent: { id: "football_parent", role: "football_parent", label: "Football Parent", version: "v3", inherited: [] } },
  { t: 600, type: "stage", stage: "INFER CONSTRAINTS" },
  { t: 1400, type: "stage", stage: "FREEZE ACCEPTANCE CRITERIA" },
  { t: 1400, type: "decision", decision: { at: at(20, 2), stage: "FREEZE ACCEPTANCE CRITERIA", decision: "continue", reason: "Six checks compiled and hashed; no blocking ambiguity, so no question asked." } },
  { t: 2200, type: "stage", stage: "DISCOVER" },
  ...children.flatMap((agent, i): RunEvent[] => [{ t: 2400 + i * 450, type: "spawn", agent }]),
  { t: 2500, type: "active", agent_id: "tickets" },
  { t: 3600, type: "active", agent_id: "flights" },
  { t: 4400, type: "fact", fact: { key: "arrival", value: "BCN Sat 14 Mar 09:40", from_agent: "flights", to_agents: ["hotels", "transit"], source_url: src("flight-search"), observed_at: at(20, 9) } },
  { t: 4600, type: "check", check_id: "arrival_before_kickoff", status: "passed", detail: "Arrives 09:40, kickoff 21:00 (11h 20m margin)" },
  { t: 5000, type: "active", agent_id: "hotels" },
  { t: 5800, type: "fact", fact: { key: "check_in", value: "Sat 14 Mar from 14:00 (bag drop on arrival)", from_agent: "hotels", to_agents: ["transit"], source_url: src("hotel-listing"), observed_at: at(20, 13) } },
  { t: 6000, type: "check", check_id: "hotel_covers_match_day", status: "passed", detail: "3 nights, 13–16 Mar, includes match day" },
  { t: 6400, type: "active", agent_id: "transit" },
  { t: 7000, type: "fact", fact: { key: "transfer", value: "Aerobús + metro L3, ~55 min", from_agent: "transit", to_agents: ["coordination"], source_url: src("matchday-transport"), observed_at: at(20, 16) } },
  { t: 7200, type: "check", check_id: "within_budget", status: "passed", detail: "$2,296 estimated of $2,500" },
  { t: 7600, type: "active", agent_id: "price_watch" },
  { t: 8200, type: "alert", alert: { at: at(20, 19), kind: "loop", message: "search(tickets, \"Barcelona Sevilla March\") repeated 3× with identical results; stopped retrying." } },
  { t: 8600, type: "stage", stage: "PLAN" },
  { t: 9000, type: "stage", stage: "VERIFY" },
  { t: 9000, type: "active", agent_id: "verifier" },
  { t: 9800, type: "check", check_id: "claims_sourced", status: "failed", detail: "Ticket price €95 has no source URL or observation time" },
  { t: 10200, type: "check", check_id: "ticket_from_legitimate_seller", status: "failed", detail: "Only a resale listing supports the ticket claim" },
  { t: 10400, type: "decision", decision: { at: at(20, 24), stage: "VERIFY", decision: "replan", reason: "2 checks failed and both are repairable inside budget; retry the tickets child against the official club page (lesson L-mock0007)." } },
  { t: 10800, type: "stage", stage: "REPAIR" },
  { t: 11000, type: "active", agent_id: "tickets" },
  { t: 12200, type: "fact", fact: { key: "ticket", value: "General sale from €89, opens 24 Feb", from_agent: "tickets", to_agents: ["price_watch", "coordination"], source_url: src("club-ticketing"), observed_at: at(20, 31) } },
  { t: 12800, type: "stage", stage: "VERIFY" },
  { t: 12800, type: "active", agent_id: "verifier" },
  { t: 13600, type: "check", check_id: "claims_sourced", status: "passed", detail: "Every price has a source URL and observation time" },
  { t: 14000, type: "check", check_id: "ticket_from_legitimate_seller", status: "passed", detail: "Official club ticketing page" },
  { t: 14400, type: "check", check_id: "no_unconfirmed_booking_claims", status: "passed", detail: "No booking or availability is claimed as confirmed" },
  { t: 14600, type: "decision", decision: { at: at(20, 38), stage: "FINAL RESULT", decision: "stop", reason: "All 6 frozen checks pass; returning 2 ranked packages." } },
  { t: 14600, type: "stage", stage: "FINAL RESULT" },
  { t: 14600, type: "active", agent_id: null },
  {
    t: 14800, type: "packages", packages: [
      {
        rank: 1, title: "FC Barcelona v Sevilla, 3 nights", match: "La Liga · Estadi Camp Nou", kickoff: "Sat 14 Mar, 21:00 (provisional)",
        estimated_total: 2296, currency: "USD", status: "verified",
        items: [
          { kind: "flight", label: "SFO → BCN, 1 stop, economy", price: 980, source_url: src("flight-search"), observed_at: at(20, 9) },
          { kind: "hotel", label: "3 nights, Eixample, direct L3 metro", price: 1180, source_url: src("hotel-listing"), observed_at: at(20, 13) },
          { kind: "ticket", label: "General sale, upper tier", price: 96, source_url: src("club-ticketing"), observed_at: at(20, 31) },
          { kind: "transit", label: "Aerobús + T-casual metro card", price: 40, source_url: src("matchday-transport"), observed_at: at(20, 16) },
        ],
        assumptions: ["1 traveler, economy", "Dates 13–16 Mar inferred from \"March\" and the fixture list", "Kickoff time is provisional (lesson L-mock0011)"],
        risks: ["Ticket general sale has not opened; price is the listed face value, not live inventory"],
      },
      {
        rank: 2, title: "FC Barcelona v Sevilla, 4 nights", match: "La Liga · Estadi Camp Nou", kickoff: "Sat 14 Mar, 21:00 (provisional)",
        estimated_total: 2456, currency: "USD", status: "verified",
        items: [
          { kind: "flight", label: "SFO → BCN, nonstop, economy", price: 1010, source_url: src("flight-search-2"), observed_at: at(20, 10) },
          { kind: "hotel", label: "4 nights, Gràcia", price: 1310, source_url: src("hotel-listing-2"), observed_at: at(20, 14) },
          { kind: "ticket", label: "General sale, upper tier", price: 96, source_url: src("club-ticketing"), observed_at: at(20, 31) },
          { kind: "transit", label: "Aerobús + T-casual metro card", price: 40, source_url: src("matchday-transport"), observed_at: at(20, 16) },
        ],
        assumptions: ["1 traveler, economy", "Extra night chosen to absorb a kickoff-time change"],
        risks: ["Only $44 under budget; a fare rise would break the budget check"],
      },
    ],
  },
];

export const MOCK_RUN: Run = {
  run_id: "mock-run-0001",
  goal: "See Barcelona at the Camp Nou in March, under $2,500 from SFO",
  mode: "mock",
  criteria_hash: "sha256:mock-3f9a1c",
  constraints: ["Budget ≤ $2,500 total", "Origin SFO", "Match at Estadi Camp Nou", "Month: March"],
  assumptions: ["1 traveler", "Economy cabin", "3–4 nights", "Mid-range hotel"],
  budget: { retries: 3, wall_clock_s: 180, tokens: 400_000, tool_calls: 60 },
  checks: [
    { check_id: "arrival_before_kickoff", description: "Flight arrives at least 4 h before kickoff", status: "pending", detail: null },
    { check_id: "within_budget", description: "Estimated total is within budget", status: "pending", detail: null },
    { check_id: "hotel_covers_match_day", description: "Hotel nights cover match day", status: "pending", detail: null },
    { check_id: "claims_sourced", description: "Every price and ticket claim has a source URL and observation time", status: "pending", detail: null },
    { check_id: "ticket_from_legitimate_seller", description: "Ticket comes from the club or an authorized seller", status: "pending", detail: null },
    { check_id: "no_unconfirmed_booking_claims", description: "No booking or availability claimed as confirmed", status: "pending", detail: null },
  ],
  events,
};

/** No model calls have been recorded yet, so the Nemotron panel has nothing to show beyond routing. */
export const MOCK_RUN_RECORDS: RunRecord[] = [];

export const MOCK_N1: N1Report = {
  candidate_version: "Football Parent v4",
  baseline_version: "Football Parent v3",
  change: {
    target: "playbook",
    summary: "Tickets child checks the official club page before any resale search.",
    hypothesis: "Fewer unsourced ticket claims, so fewer verifier failures and repairs, at equal or lower cost.",
  },
  gate: [
    "Verified package success improves on held-out scenarios",
    "False-completion rate does not rise",
    "Cost per verified success regresses by no more than 10%",
  ],
  metrics: [
    { name: "Verified package success", split: "benchmark", baseline: null, candidate: null },
    { name: "Verified package success", split: "heldout", baseline: null, candidate: null },
    { name: "False-completion rate", split: "heldout", baseline: null, candidate: null, lower_is_better: true },
    { name: "Cost per verified success (USD)", split: "heldout", baseline: null, candidate: null, lower_is_better: true },
  ],
  decision: null,
  decision_reason: null,
  history: [
    { version: "Football Parent v1", at: "2026-10-17", note: "Initial playbook", status: "retired" },
    { version: "Football Parent v2", at: "2026-10-17", note: "Added match-day timing rules", status: "retired" },
    { version: "Football Parent v3", at: "2026-10-17", note: "Current baseline", status: "active" },
  ],
};

export const MOCK_ABLATION: MemoryAblation = {
  metrics: [
    { name: "Verified success", memory_off: null, memory_on: null, unit: "%" },
    { name: "Cost per verified success", memory_off: null, memory_on: null, unit: "USD" },
    { name: "Time to verified result", memory_off: null, memory_on: null, unit: "s" },
  ],
};

export { ROUTES };
