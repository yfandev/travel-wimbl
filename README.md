# Wimbl

**Autonomous travel discovery, verification, and measured agent improvement.**

Wimbl discovers event-led trips from a traveler's interests, assembles evidence-backed candidates, verifies feasibility, and records learning candidates for scoped review.

## Public demo

We're preparing a one-minute walkthrough of Wimbl for the Crusoe Recursive Agents Hackathon.

- **Public demo video (YouTube):** _Link coming soon._
- **Recording / review link (Loom):** _Link coming soon._

The video will walk through the agent-family concept, the current application and code, and the search-and-verification workflow. Links will be added here once the recording is published. The You.com integration and other capabilities should be understood in light of the implementation notes under [Important limits](#important-limits).

## What we're building

Wimbl explores a family-of-agents approach to football-trip planning:

- **Travel parent:** shared travel principles such as preferences, budget constraints, and verification standards.
- **Sports parent:** sports-specific context and planning guidance.
- **Football child:** focused research for ticketing, match-day timing, travel logistics, and source reliability.
- **Scoped memory and evaluation:** candidate lessons can be recorded and evaluated before any broader promotion; they are not automatically treated as facts.

The goal is for parent agents to guide child planning while keeping claims grounded in evidence and making it possible to evaluate whether lessons improve future plans.

## Stack

- **FastAPI** backend and lightweight traveler dashboard.
- **NVIDIA NemoClaw / OpenShell** intended runtime for always-on agents in a guarded sandbox.
- **You.com Search API** for web discovery. Search results are evidence, not guaranteed live inventory.
- **Crusoe Managed Inference** via an OpenAI-compatible client adapter.
- **Wimbl controller** for acceptance criteria, verification and bounded stop/replan decisions.
- **Scoped shared memory** with provenance and confidence.
- **Version N+1 evaluation harness** for baseline/candidate comparisons over in-sample and held-out scenarios.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn wimbl.api:app --reload
```

Open http://127.0.0.1:8000. Without API keys, the app runs in **demo mode** with clearly labelled sample discovery results. No bookings are made.

Run tests:

```bash
pytest -q
```

## Configure integrations

Set values in `.env`:

- `CRUSOE_API_KEY` — Crusoe inference key.
- `CRUSOE_BASE_URL` — defaults to `https://api.inference.crusoecloud.com/v1`.
- `CRUSOE_MODEL` — model enabled for your account.
- `YOU_API_KEY` — You.com key.
- `YOU_SEARCH_ENDPOINT` — confirm endpoint and response schema against the API plan/docs for your account.

Do not commit `.env`. Inject secrets through host/gateway secret handling; do not place raw keys in prompts, memory, logs, or sandbox files.

## NemoClaw / OpenShell

Follow NVIDIA's current official [NemoClaw guide](https://www.nvidia.com/en-us/ai/nemoclaw). See `ops/nemoclaw/README.md` and `policy.example.yaml`. Policy formats and CLI commands are version-dependent; the YAML is a security design sketch, not a drop-in config. Test allowlisted egress and confirm provider keys remain host-side.

## API

- `GET /api/health`
- `POST /api/trips/discover` — JSON: `{"interest":"tennis","origin":"SFO","budget":2500,"currency":"USD","days":4}`
- `GET /api/memory`
- `POST /api/improvement/evaluate` — candidate policy JSON

## Important limits

- The verifier does not assume search results mean availability or a booking.
- Missing price/date data is flagged; the system does not fabricate a total.
- Memory records have scope, source, confidence, validation status and timestamp. Child lessons are candidate knowledge, not automatically propagated as fact.
- Version N+1 promotion is only marked `eligible_for_review` when proxy metrics do not regress on held-out scenarios. This is not automatic self-modification or deployment.
- The Crusoe adapter is included, but current trip orchestration uses deterministic checks and does not yet invoke Crusoe for planning.
- The You.com endpoint/response adapter must be confirmed against your account's current API documentation.
- This scaffold does not implement bookings or payments.
