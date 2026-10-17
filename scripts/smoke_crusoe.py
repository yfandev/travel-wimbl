"""Crusoe + Nemotron smoke tests T1–T4 (setup spec §4) and the Nano-vs-Lightning child benchmark.

Writes docs/smoke-results.md. Every call also lands in the run log with the model ID the endpoint returned.
Never prints credentials. Usage: python scripts/smoke_crusoe.py
"""
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openai import APIStatusError, BadRequestError  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from wimbl.config import settings  # noqa: E402
from wimbl.integrations.crusoe import CrusoeClient, LLMError, extract_json, strip_reasoning  # noqa: E402
from wimbl.integrations.models import LIGHTNING, NANO, SUPER  # noqa: E402

# The setup spec's spellings, which Crusoe's /v1/models catalog does not list (spec ID -> catalog ID).
SPEC_IDS = {"nvidia/Nemotron-3-Super-120B-A12B": SUPER, "nvidia/Nemotron-3-Nano-30B-A3B": NANO,
            "nvidia/nemotron-3.5-lightning-30b-a3b": LIGHTNING}
RUN_ID = "smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
TOOLS = [{"type": "function", "function": {"name": "search_tickets", "description": "Find official ticket listings for a match",
    "parameters": {"type": "object", "properties": {"team": {"type": "string"}, "date": {"type": "string"}}, "required": ["team"]}}}]

class Fixture(BaseModel):
    home_team: str
    away_team: str
    competition: str

# Child benchmark: a tickets-child task over a fixed evidence pack, graded deterministically.
EVIDENCE = [
    {"id": "E1", "url": "https://www.fcbarcelona.com/en/tickets/football", "observed_at": "2026-10-17T10:00:00Z",
     "text": "Official FC Barcelona ticketing. Tickets for home LaLiga matches go on sale on the official site and app. "
             "Prices vary by match category. Resale is only permitted through the official Seient Lliure platform."},
    {"id": "E2", "url": "https://www.footballticketnet.com/fc-barcelona-football-tickets", "observed_at": "2026-10-17T10:00:00Z",
     "text": "FC Barcelona tickets from EUR 89! Guaranteed seats. Third-party marketplace, prices set by sellers."},
    {"id": "E3", "url": "https://www.example-news.com/barca-fixtures", "observed_at": "2026-09-01T08:00:00Z",
     "text": "Fixture dates may move for broadcast; kick-off times are confirmed roughly three weeks ahead."},
]

class TicketFinding(BaseModel):
    official_source_url: str
    recommended_channel: str
    unofficial_sources: list[str]
    price_is_live: bool
    risks: list[str]

def grade(f: TicketFinding) -> dict:
    checks = {
        "official_source": "fcbarcelona.com" in f.official_source_url,
        "flags_resale_site": any("footballticketnet" in u for u in f.unofficial_sources),
        "no_live_price_claim": f.price_is_live is False,
        "mentions_kickoff_risk": any(w in " ".join(f.risks).lower() for w in ("kick", "broadcast", "date", "time")),
    }
    return {"score": sum(checks.values()) / len(checks), **checks}

def user(content: str) -> list[dict]: return [{"role": "user", "content": content}]

async def t1(c: CrusoeClient, model: str) -> dict:
    r = await c.chat("controller", user("Reply with the single word: ready"), run_id=RUN_ID, prompt_version="smoke-t1", model=model, max_tokens=512)
    text = strip_reasoning(r.text)
    return {"pass": bool(text), "detail": f"{text[:40]!r}", "returned": r.model, "latency_ms": r.record["latency_ms"]}

async def t2(c: CrusoeClient, model: str) -> dict:
    """Native tool calling only: the spec asks whether the endpoint itself returns tool_calls."""
    try:
        r = await c.chat("tickets", user("Find tickets for FC Barcelona's next home match."), run_id=RUN_ID,
                         prompt_version="smoke-t2", tools=TOOLS, model=model, max_tokens=1024)
    except BadRequestError as exc:
        return {"pass": False, "detail": f"tools rejected (HTTP {exc.status_code})", "returned": None}
    try:
        args = [json.loads(call["arguments"] or "{}") for call in r.tool_calls]
        ok = bool(args) and all(isinstance(a, dict) and "team" in a for a in args)
    except json.JSONDecodeError:
        ok, args = False, "invalid JSON"
    return {"pass": ok, "detail": f"tool_calls={args}" if r.tool_calls else "no tool_calls returned", "returned": r.model}

async def t2_fallback(c: CrusoeClient, model: str) -> dict:
    c.capabilities.setdefault(model, {})["tools"] = False
    r = await c.act("tickets", user("Find tickets for FC Barcelona's next home match."), TOOLS, run_id=RUN_ID,
                    prompt_version="smoke-t2", model=model, max_tokens=1024)
    return {"pass": bool(r.tool_calls), "detail": f"{r.tool_calls}"}

async def t3(c: CrusoeClient, model: str) -> dict:
    prompt = user("Give the fixture FC Barcelona vs Real Madrid in LaLiga as JSON.")
    fmt = {"type": "json_schema", "json_schema": {"name": "Fixture", "schema": Fixture.model_json_schema()}}
    native = "unsupported"
    try:
        r = await c.chat("verifier", prompt, run_id=RUN_ID, prompt_version="smoke-t3", response_format=fmt, model=model, max_tokens=1024)
        try:
            Fixture.model_validate(extract_json(r.text)); native = "pass"
        except ValueError:
            native = "accepted, invalid JSON"
    except BadRequestError:
        pass
    c.capabilities.setdefault(model, {})["response_format"] = False
    try:
        fb = await c.structured("verifier", prompt, Fixture, run_id=RUN_ID, prompt_version="smoke-t3", model=model, max_tokens=1024)
        fallback = f"pass ({fb.parsed.home_team} vs {fb.parsed.away_team})"
    except LLMError as exc:
        fallback = f"fail: {str(exc)[:80]}"
    return {"pass": native == "pass" or fallback.startswith("pass"), "detail": f"response_format: {native}; prompted JSON + repair: {fallback}"}

async def t4(model: str) -> dict:
    """5 truly parallel requests (own client, no semaphore) to see rate limits."""
    c = CrusoeClient(max_concurrency=5)
    async def one(i):
        t = time.monotonic()
        try:
            await c.chat("tickets", user(f"Reply with the number {i}."), run_id=RUN_ID, prompt_version="smoke-t4", model=model, max_tokens=256)
            return ("ok", round((time.monotonic() - t) * 1000))
        except (LLMError, APIStatusError) as exc:
            return ("429" if "429" in str(exc) else "error", round((time.monotonic() - t) * 1000))
    results = await asyncio.gather(*[one(i) for i in range(5)])
    rows = [r for r in c.runlog.read(RUN_ID) if r["prompt_version"] == "smoke-t4" and r["model_id_requested"] == model]
    retried = sum(1 for r in rows[-5:] if (r.get("attempts") or 1) > 1)
    ok = [ms for s, ms in results if s == "ok"]
    return {"pass": len(ok) == 5, "detail": f"{len(ok)}/5 ok, {retried} needed a 429/5xx retry, "
            f"latency p50 {int(statistics.median(ok)) if ok else '-'} ms, max {max(ok) if ok else '-'} ms"}

async def bench(c: CrusoeClient, model: str, runs: int = 3) -> dict:
    prompt = user("You are the tickets agent in a football-travel family. Using only this evidence, report where to buy "
                  "tickets for an FC Barcelona home match. Do not claim prices are live.\n" + json.dumps(EVIDENCE))
    scores, latency, out_tokens = [], [], []
    for _ in range(runs):
        try:
            r = await c.structured("tickets", prompt, TicketFinding, run_id=RUN_ID, prompt_version="bench-tickets-v0", model=model, max_tokens=2048)
            scores.append(grade(r.parsed)["score"]); latency.append(r.record["latency_ms"]); out_tokens.append(r.record["output_tokens"] or 0)
        except LLMError:
            scores.append(0.0)
    return {"mean_score": round(statistics.mean(scores), 3), "p50_latency_ms": int(statistics.median(latency)) if latency else None,
            "mean_output_tokens": int(statistics.mean(out_tokens)) if out_tokens else None, "runs": runs}

async def main() -> int:
    if not settings.crusoe_api_key:
        print("ERROR: CRUSOE_API_KEY is not set. Add it to .env.local."); return 2
    c = CrusoeClient()
    catalog = sorted(m.id for m in (await c.client.models.list()).data)
    spec_probe = {}
    for spec_id in SPEC_IDS:
        try:
            await c.chat("controller", user("ping"), run_id=RUN_ID, prompt_version="smoke-spec-id", model=spec_id, max_tokens=16)
            spec_probe[spec_id] = "200 OK"
        except APIStatusError as exc:
            body = exc.body if isinstance(exc.body, dict) else {}
            spec_probe[spec_id] = f"HTTP {exc.status_code} {body.get('code', '')} (error_id {body.get('error_id', 'n/a')})"
        print(f"  spec ID {spec_id}: {spec_probe[spec_id]}")
    results: dict[str, dict] = {}
    for model in (SUPER, NANO, LIGHTNING):
        print(f"== {model}")
        row = results[model] = {}
        for name, fn in (("T1", t1), ("T2", t2), ("T3", t3)):
            try: row[name] = await fn(c, model)
            except Exception as exc: row[name] = {"pass": False, "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}
            print(f"  {name}: {'PASS' if row[name]['pass'] else 'FAIL'} — {row[name]['detail']}")
        if not row["T2"]["pass"] and row["T1"]["pass"]:
            try: row["T2 fallback"] = await t2_fallback(c, model)
            except Exception as exc: row["T2 fallback"] = {"pass": False, "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}
            print(f"  T2 fallback (JSON action): {'PASS' if row['T2 fallback']['pass'] else 'FAIL'} — {row['T2 fallback']['detail']}")
        row["T4"] = await t4(model)
        print(f"  T4: {'PASS' if row['T4']['pass'] else 'FAIL'} — {row['T4']['detail']}")
    bench_results = {}
    for model in (NANO, LIGHTNING):
        if results[model]["T1"]["pass"]:
            bench_results[model] = await bench(c, model)
            print(f"  bench {model}: {bench_results[model]}")
    write_report(results, bench_results, catalog, spec_probe)
    return 0 if all(results[m]["T1"]["pass"] for m in results) else 1

def write_report(results: dict, bench_results: dict, catalog: list[str], spec_probe: dict) -> None:
    returned = {m: next((v.get("returned") for v in r.values() if v.get("returned")), None) for m, r in results.items()}
    lines = [f"# Crusoe + Nemotron smoke results", "",
             f"Run `{RUN_ID}` on {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC via `{settings.crusoe_base_url}`. "
             "Generated by `scripts/smoke_crusoe.py`; per-call records are in the run log (`data/run_log.jsonl`).", "",
             "## Spec vs catalog model IDs", "",
             "The setup spec's model IDs are not in Crusoe's catalog. Same models, different spelling; the live catalog wins "
             "(the spec itself says to pick IDs only from the live catalog).", "",
             "| Spec ID | Result when requested | Catalog ID used |", "|---|---|---|",
             *[f"| `{s}` | {spec_probe[s]} | `{c}` |" for s, c in SPEC_IDS.items()],
             "", f"`GET /v1/models` returned {len(catalog)} models: " + ", ".join(f"`{m}`" for m in catalog), "",
             "## Smoke tests T1–T4", "",
             "| Model requested | Model returned | T1 chat | T2 tool calls | T3 structured | T4 5× parallel |", "|---|---|---|---|---|---|"]
    for m, r in results.items():
        cell = lambda k: ("PASS" if r[k]["pass"] else "FAIL") if k in r else "–"
        t2 = cell("T2") + (f" (JSON-action fallback: {cell('T2 fallback')})" if "T2 fallback" in r else "")
        lines.append(f"| `{m}` | `{returned[m]}` | {cell('T1')} | {t2} | {cell('T3')} | {cell('T4')} |")
    lines += ["", "## Details", ""]
    for m, r in results.items():
        lines.append(f"**`{m}`**")
        lines += [f"- {k}: {v['detail']}" for k, v in r.items()]
        lines.append("")
    lines += ["## Child benchmark: tickets agent, Nano vs Lightning", "",
              "One fixed evidence pack (official club ticketing page, a third-party resale site, a stale fixture note), "
              "graded on four deterministic checks: cites the official source, flags the resale site, makes no live-price claim, "
              "notes kickoff-time risk. Structured output via the client's fallback path.", "",
              "| Model | Mean score | p50 latency | Mean output tokens | Runs |", "|---|---|---|---|---|"]
    for m, b in bench_results.items():
        lines.append(f"| `{m}` | {b['mean_score']} | {b['p50_latency_ms']} ms | {b['mean_output_tokens']} | {b['runs']} |")
    if bench_results:
        winner = max(bench_results, key=lambda m: (bench_results[m]["mean_score"], -(bench_results[m]["p50_latency_ms"] or 1e9)))
        lines += ["", f"Winner by score, then latency: `{winner}`. Pin it as `CHILD_MODEL` in `wimbl/integrations/models.py`."]
    lines += ["", "Price estimates exist only for Super (third-party, ComputePrices); other models log `cost_estimate_usd: null`."]
    out = ROOT / "docs" / "smoke-results.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
