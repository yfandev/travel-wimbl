# CLAUDE.md — WIMBL

Source of truth: `docs/WIMBL_Build_Brief.pdf` and `docs/WIMBL_Crusoe_Nemotron_Setup.pdf`. If this file and the briefs disagree, the briefs win; fix this file.

## 1. What WIMBL is

WIMBL is a self-improving family of football-travel agents. Give it a one-line goal ("see Barcelona at the Camp Nou in March, under $2,500 from SFO") and it infers constraints and safe defaults, freezes acceptance criteria, researches tickets, flights, hotels, and local transit in parallel, assembles ranked, source-backed packages, has an independent verifier check them, and repairs or replans within budget. It asks the traveler only when a decision genuinely cannot be resolved safely. After each trip, a learning engine proposes improvements to the family's prompts, playbooks, and structure, and promotes a change only when it beats baseline on held-out scenarios. Every model call runs on NVIDIA Nemotron models served by Crusoe Managed Inference (serverless). NVIDIA makes the models; Crusoe hosts them.

## 2. Architecture

Controller-led. Short-lived trip children do the work; persistent, versioned parents hold durable knowledge.

| Component | Responsibility | Key outputs |
|---|---|---|
| Trip Controller | Owns the lifecycle, frozen acceptance criteria, budgets, retries, replanning, stopping, rare escalation, and the approval gate. | Run state, assumptions, completion status, blocker reason. |
| Sports Parent | General travel knowledge, user-preference rules, verification standards, reusable strategies. | Scoped inherited lessons and policy defaults. |
| Football Parent | Football discovery strategy, ticket-sale patterns, match-day timing, trusted source guidance. | Football lessons with provenance and validation history. |
| Trip children | Specialists: tickets, flights, hotels, local transit, price watch, coordination. | Findings, options, citations, assumptions, risks. |
| Sibling coordination | Shared trip-facts board updated in near real time (e.g. flight arrival changes hotel check-in and airport transfer). | Shared trip facts with source and timestamp. |
| Independent verifier | Checks the package against frozen criteria. Sees only the package and evidence, never planner reasoning. Can reject completion and request repair. | Pass/fail checks, defects, evidence, residual risk. |
| Learning engine | Retrospective, change proposal, baseline and held-out evaluation, promote/reject, rollback. | Versioned candidate, evaluation report, decision record. |
| Shared memory | Lessons by scope, provenance, confidence, recency, and validation status. | Searchable lesson registry and lineage. |

Family tree: Sports Parent → Football Parent → trip children. Football only; there is no tennis family.

Lifecycle (bounded state machine, owned by the controller, not the planner):

```
REQUEST → INFER CONSTRAINTS → FREEZE ACCEPTANCE CRITERIA → DISCOVER → PLAN → VERIFY
        → (REPAIR / REPLAN) → FINAL RESULT → RETROSPECTIVE → N+1 EVALUATION
```

Module map (flat `wimbl/` package; `index.py` is the Vercel entrypoint):

| Path | Holds |
|---|---|
| `wimbl/api.py` | FastAPI app: requests, run state, results, memory, N+1 endpoints |
| `wimbl/controller/` | Goal compiler, state machine, budgets, loop/drift monitors, decision policy, approval gate |
| `wimbl/agents/` | Parents, trip children, trip board, independent verifier |
| `wimbl/memory/` | Lesson registry, influence scoring, conflict resolution, lineage |
| `wimbl/improvement/` | Baseline, candidate, held-out eval, promotion, rollback |
| `wimbl/integrations/` | `models.py` (routing), `crusoe.py` (LLM client), `youcom.py` (search) |
| `wimbl/runlog.py` | Per-call run records |
| `wimbl/static/` | Traveler view, operations view, N+1 lab |
| `evals/` | `benchmark_scenarios.json`, `heldout_scenarios.json`, replay fixtures |

Some of these modules are still planned; check the tree before assuming one exists.

## 3. Model routing

Endpoint: `https://api.inference.crusoecloud.com/v1/` (OpenAI-compatible chat completions, serverless; do not use Self-Serve Deployments). Routing lives in one file, `wimbl/integrations/models.py`, so a model can be swapped without touching the controller or learning engine.

| Role | Model ID (exact) |
|---|---|
| Trip Controller, Independent Verifier, Learning Engine | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B` |
| Trip children (tickets, flights, hotels, transit, price watch) | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` or `nvidia/Nemotron-3.5-Lightning-30B-A3B`: benchmark both on one scenario, pin the winner, record why |
| Optional image checks (ticket screenshots, venue maps) | `nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B`, only if time remains |

These are the exact IDs from Crusoe's `/v1/models` catalog (checked 2026-10-17). The briefs spell Super and Nano without the `NVIDIA-` prefix and Lightning in lowercase; those spellings return 404 `model_not_found`.

- Context on Crusoe: Super 262k (plan for 262k even though NVIDIA markets 1M), Nano 262k, Lightning 1M, Omni 262k.
- Tool calling is **unknown** until smoke test T2 passes. Fallback: a JSON action protocol (`{"tool": ..., "args": ...}`) parsed and validated in code before execution.
- Structured output: if `response_format` is unsupported, use prompt-instructed JSON plus validation plus one repair retry.
- The `model` field returned in the response is the source of truth; log it on every call.
- Reliability: retry 429/5xx with exponential backoff and jitter (1s, 2s, 4s, max 4 attempts); never retry 4xx auth/validation errors; cap parallel child calls with a semaphore (start at 4); per-call timeouts count against the run's tool-call budget.
- Run record on every model call: `run_id, agent_role, model_id_requested, model_id_returned, version_tag, prompt_version, input_tokens, output_tokens, latency_ms, cost_estimate_usd, tool_calls, status, error, timestamp`.
- Smoke tests T1 (chat), T2 (tool calling), T3 (structured output), T4 (5 parallel child calls) run against Super and the chosen child model before building on them.

## 4. Hackathon problem statements → WIMBL

The three problem statements and judging weights below come from the team's hackathon brief, not the two PDFs. Still to confirm on the hackathon page: credit amount, prize categories, banned project categories.

### Done Means Done
- A goal compiler (on Super) turns the one-line goal into hard constraints, safe reversible defaults, labelled assumptions, and executable acceptance checks: Python predicates over the package and its evidence. The checks are hashed and frozen at run start and never silently relaxed after failure.
- The independent verifier runs the checks plus model-based claim checks (dates, transfer timing, source freshness, ticket legitimacy signals) without seeing planner reasoning.
- Drift detection: the plan diverges from frozen constraints. Loop detection: repeated (tool, args) hashes, circular replans, or a failing-check count that stops improving.
- The controller decides **continue**, **replan**, **stop** (with a truthful partial result if budget runs out), or, rarely, **escalate** (only for a blocking ambiguity, authorization, or safety issue).
- Budgets per run: retries, wall-clock, tokens, tool calls.

### Shared Brain
- Family memory every agent reads before working (lessons scoped by its lineage) and updates after (findings, outcomes).
- Lesson record: `lesson_id, lesson, from_agent, scope, lineage, weight, evidence_urls, source_type, confidence, trips_validated, successes, failures, last_validated, expires_at, version_introduced, evaluation_status`.
- Influence = lineage relevance × smoothed observed success × independent validation count (capped) × recency. Raw trip counts never give unbounded influence. Hard user constraints and safety rules are not weighted lessons.
- Current: `last_validated` and `expires_at`. Lean: per-scope caps, merge near-duplicates. Conflict-free: contradiction detection within scope/topic on write, explicit supersede, user-origin preferences never overwritten by internet-derived facts.
- Inheritance attribution: every child decision cites the lesson IDs and parent version that influenced it.
- Measured: the same benchmark runs with memory off and on; the delta comes from run logs.

### Version N+1
- Observe → Reflect → Propose **one isolated change** (prompt, playbook/lesson, tool policy, routing rule, or workflow structure) with a stated hypothesis → Baseline on fixed benchmark scenarios → Evaluate the candidate on the same scenarios **and** held-out scenarios it was never tuned on (repeat stochastic runs) → Decide against a threshold and trade-offs defined before evaluation → Roll out with a version and rationale, monitor, roll back if needed → Teach the family by propagating the proven lesson to the correct parent scope.
- Never promote because one trip looked good. Require provenance, baseline comparison, held-out tests, no critical regression, and an auditable decision record.
- Never auto-rewrite production prompts or code outside this gate.
- Metrics: verified package success, false-completion rate, generalization (held-out delta), cost per verified success, time to verified result, regression rate, inheritance attribution, provenance coverage.

## 5. Judging criteria and how we win each

| Criterion | Weight | How WIMBL wins it |
|---|---|---|
| Technicality | 40% | Real Nemotron calls with per-call run records; executable frozen acceptance checks; loop and drift detection; an independent verifier; a real N+1 promotion gate with held-out evaluation and rollback; reliability (backoff, semaphore, budgets). |
| Live Demo | 20% | The 3-minute script below, run live against Crusoe with replayable search fixtures so it can't fall over on flaky search. Every number on screen is read from run logs. |
| Creativity | 25% | An agent *family* that inherits: the second trip visibly uses a lesson the first trip earned, and a child can explain "I checked the official club page first because of lesson L from Football Parent v3." |
| Future Potential | 15% | Model, search, runtime, and sport sit behind adapters; new sports are new parents under Sports. Each phase records how it runs at production scale. |

Demo script (Build Brief §8):
1. 0:00–0:25 Goal: enter a football-trip request; WIMBL infers defaults instead of asking a questionnaire.
2. 0:25–1:05 Family at work: ticket, flight, hotel, and verifier agents share findings with source URLs and timestamps.
3. 1:05–1:35 Done Means Done: the verifier catches a real issue (arrival after kickoff, unsupported ticket claim); the controller repairs or flags it.
4. 1:35–2:10 Version N+1: a real lesson proposal, baseline vs candidate, held-out result, promote/reject.
5. 2:10–2:45 Inheritance: a second trip shows which proven lessons were inherited and what changed.
6. 2:45–3:00 Evidence: actual metrics, exact model ID, inference route, provenance.

## 6. Rules

### Honesty rules
- Never imply a price or inventory is live unless a source supports it and the observation time is recorded. Search results are evidence, not proof of availability.
- Never claim a reservation, ticket, or booking is confirmed unless a real booking flow confirms it. WIMBL does not book.
- Learned lessons never weaken explicit user constraints, frozen acceptance criteria, or safety requirements.
- Never invent benchmark wins or metrics. Show measured results or label the benchmark "not yet run".
- Say: "WIMBL runs NVIDIA Nemotron [exact ID], served by Crusoe Managed Inference." Never call Nemotron a Crusoe model.
- Do not claim NeMo Switchyard, NeMo Guardrails, or a 1M context on Super; they are out of scope or unverified.
- Show only model IDs, costs, and metrics actually recorded in run logs.

### Approval gate
- No purchase, booking, payment, or other consequential external action executes without explicit traveler approval.
- Implement it as a hard check in controller code, not a model judgment. A test must prove a booking call raises without approval.

### Question policy
- Default to zero clarification questions. Infer reversible defaults, research unknown facts, offer ranked alternatives, label assumptions.
- Ask exactly one focused question only when genuinely blocked, naming the decision and why it matters.
- Track interruptions per trip; don't trade safety or correctness for fewer questions.

### Secrets
- `CRUSOE_API_KEY` and `YOU_API_KEY` come only from the environment (`.env` / `.env.local`, both gitignored, or host secrets).
- Never hard-code, log, or put keys in prompts, memory, or fixtures. `.env.example` keeps blank placeholders only. The repo is public.

### MVP definition of done
- A natural-language request produces a ranked, source-backed travel package.
- The controller records constraints, assumptions, acceptance criteria, budgets, and run status.
- The verifier can fail a package and trigger bounded repair or replanning.
- At least one persistent parent lesson is inherited by a later trip agent.
- N+1 evaluates one isolated change against baseline and held-out scenarios and records promotion or rejection.
- The UI shows evidence, uncertainty, inherited lessons, and version comparisons.
- The exact Crusoe-served model ID and version are recorded, with no unsupported claims about NVIDIA usage.
- No unnecessary questions are asked; required authorization gates stay intact.
- Setup: smoke tests T1–T4 recorded for Super and the chosen child; routing in one file with exact catalog IDs; retry/backoff and concurrency cap in place; every call writes a run record with the returned model ID.

Build priority: one verifiable end-to-end trip → evidence-backed family memory → the N+1 gate.

## 7. Working conventions

- Python 3.11+, venv at `.venv`: `source .venv/bin/activate && pytest -q`. Run locally with `uvicorn wimbl.api:app --reload`.
- Without keys the app runs in clearly labelled demo mode; never present demo output as real.
- **Standing rule:** after each build phase, explain in 3–4 sentences how what was just built is done at scale in production.
