"""Shared Brain measurement: does a lesson written on one trip improve the tickets agent on held-out trips?

1. Trip A (Barcelona): the tickets child does its task, then writes lessons for future ticket agents via propose_lesson().
2. Trips B and C (Arsenal, Bayern; held out, never seen when the lesson was written): the tickets child runs with memory
   off and with memory on (get_inherited_lessons prompt block), repeated. Outputs are graded by fixed checks.
Evidence packs are fixtures (paraphrased, not live data). Writes docs/memory-results.md. Uses its own lesson DB.
"""
import asyncio
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, Field  # noqa: E402
from wimbl.config import settings  # noqa: E402
from wimbl.integrations.crusoe import CrusoeClient, LLMError  # noqa: E402
from wimbl.integrations.models import model_for  # noqa: E402
from wimbl.memory import LessonStore, get_inherited_lessons, propose_lesson  # noqa: E402

RUN_ID = "memory-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
REPEATS = 3
TOKEN_BUDGET = 600
MAX_TOKENS = 6000  # Lightning reasons before answering; 2048 truncated JSON in run 1

TRIPS = {
    "A_barcelona": {"club": "FC Barcelona", "official": "fcbarcelona.com", "resale_words": ("seient", "official resale", "exchange"),
        "third_party": "footballticketnet", "evidence": [
        {"url": "https://www.footballticketnet.com/fc-barcelona-football-tickets", "text": "FC Barcelona tickets from EUR 89! Guaranteed seats. Third-party marketplace; sellers set prices."},
        {"url": "https://www.fcbarcelona.com/en/tickets/football", "text": "Official FC Barcelona ticketing. Home match tickets are sold on the official site and app. Resale is only permitted through the official Seient Lliure platform."},
        {"url": "https://www.example-news.com/barca-fixtures", "text": "LaLiga kick-off times are confirmed about three weeks ahead and can move for broadcast."}]},
    "B_arsenal": {"club": "Arsenal", "official": "arsenal.com", "resale_words": ("ticket exchange", "exchange", "official resale"),
        "third_party": "livefootballtickets", "evidence": [
        {"url": "https://www.livefootballtickets.com/arsenal-tickets", "text": "Arsenal tickets available now, prices from GBP 150. Instant confirmation! Independent marketplace."},
        {"url": "https://www.arsenal.com/tickets", "text": "Official Arsenal ticketing. Most home matches sell out to members. Members can buy returned seats on the official Ticket Exchange."},
        {"url": "https://www.example-news.com/premier-league-tv-picks", "text": "Premier League fixtures are often moved for TV, sometimes with only a few weeks' notice."}]},
    "C_bayern": {"club": "FC Bayern Munich", "official": "fcbayern.com", "resale_words": ("second", "official resale", "exchange", "zweitmarkt"),
        "third_party": "ticketcompare", "evidence": [
        {"url": "https://www.ticketcompare.com/bayern-munich", "text": "Compare Bayern Munich ticket prices across sellers. Cheapest from EUR 120 right now."},
        {"url": "https://fcbayern.com/en/tickets", "text": "Official FC Bayern ticketing. Tickets are sold to members first. Resale is only allowed on the official FC Bayern secondary ticket market."},
        {"url": "https://www.example-news.com/bundesliga-scheduling", "text": "Bundesliga kick-off slots are fixed a few weeks in advance; dates may still shift."}]},
}

class TicketFinding(BaseModel):
    official_source_url: str
    recommended_channel: str
    unofficial_sources: list[str]
    price_is_live: bool
    risks: list[str]
    lessons_used: list[str] = Field(default_factory=list, description="IDs of inherited lessons you relied on, if any.")

class LessonDraft(BaseModel):
    lesson: str
    topic: str
    evidence_urls: list[str]

class LessonDrafts(BaseModel):
    lessons: list[LessonDraft] = Field(max_length=2)

def task(trip: dict) -> str:
    return (f"You are the tickets agent in a football-travel family. Using only this evidence, report where the traveler "
            f"should get tickets for a {trip['club']} home match. Do not claim prices are live.\n" + json.dumps(trip["evidence"]))

def grade(trip: dict, f: TicketFinding) -> dict[str, bool]:
    channel = f.recommended_channel.lower()
    return {
        "official_source": trip["official"] in f.official_source_url,
        "flags_third_party": any(trip["third_party"] in u for u in f.unofficial_sources),
        "no_live_price_claim": f.price_is_live is False,
        "names_official_resale": any(w in channel for w in trip["resale_words"]),
        "kickoff_risk": any(w in " ".join(f.risks).lower() for w in ("kick", "broadcast", "tv", "date", "time", "reschedul")),
    }

async def run_child(c: CrusoeClient, trip: dict, block: str, label: str) -> dict:
    messages = ([{"role": "system", "content": block}] if block else []) + [{"role": "user", "content": task(trip)}]
    try:
        r = await c.structured("tickets", messages, TicketFinding, run_id=RUN_ID, prompt_version=f"tickets-v0-{label}", max_tokens=MAX_TOKENS)
    except LLMError as exc:
        return {"error": str(exc)[:200]}
    return {"finding": r.parsed, "checks": grade(trip, r.parsed), "latency_ms": r.record["latency_ms"], "output_tokens": r.record["output_tokens"]}

async def main() -> int:
    if not settings.crusoe_api_key:
        print("ERROR: CRUSOE_API_KEY is not set. Add it to .env.local."); return 2
    db = ROOT / "data" / "memory_measure.sqlite3"
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(db) + suffix).unlink(missing_ok=True)
    store, c = LessonStore(str(db)), CrusoeClient()

    # Trip A: work, then write lessons for future ticket agents.
    a = TRIPS["A_barcelona"]
    first = await run_child(c, a, "", "tripA")
    print("trip A checks:", first.get("checks") or first.get("error"))
    reflect = [{"role": "user", "content": task(a)},
               {"role": "assistant", "content": first["finding"].model_dump_json() if "finding" in first else "(no answer)"},
               {"role": "user", "content": "Write up to two short, general lessons for future ticket agents on other clubs' trips "
                "(not specific to this club). Give each a snake_case topic and cite evidence URLs from the evidence above."}]
    drafts = (await c.structured("tickets", reflect, LessonDrafts, run_id=RUN_ID, prompt_version="tickets-reflect-v0", max_tokens=MAX_TOKENS)).parsed
    proposals = []
    for d in drafts.lessons:
        res = propose_lesson({"lesson": d.lesson, "topic": d.topic, "from_agent": "tickets", "scope": "football.tickets",
                              "source_type": "run", "run_id": f"{RUN_ID}-tripA", "evidence_urls": d.evidence_urls, "confidence": 0.6}, store=store)
        proposals.append((d, res)); print(f"proposed: {res.status} {res.lesson_id or ''} {res.reason}")
    inherited = get_inherited_lessons("tickets", "football", TOKEN_BUDGET, store=store)
    lesson_ids = {l.lesson_id for l in inherited.lessons}

    # Held-out trips B and C, memory off vs on.
    jobs = [(name, cond) for name in ("B_arsenal", "C_bayern") for cond in ("off", "on") for _ in range(REPEATS)]
    outs = await asyncio.gather(*[run_child(c, TRIPS[n], inherited.prompt_block if cond == "on" else "", f"{n}-{cond}") for n, cond in jobs])
    results: dict[tuple[str, str], list[dict]] = {}
    for (n, cond), out in zip(jobs, outs):
        results.setdefault((n, cond), []).append(out)
    write_report(first, proposals, inherited, results, lesson_ids)
    return 0

def write_report(first, proposals, inherited, results, lesson_ids) -> None:
    def score(outs): return [sum(o["checks"].values()) / len(o["checks"]) for o in outs if "checks" in o]
    lines = ["# Shared Brain measurement", "",
             f"Run `{RUN_ID}` on {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Tickets child model: `{model_for('tickets')}` "
             "served by Crusoe Managed Inference. Generated by `scripts/measure_memory.py`; every call is in the run log.", "",
             "Evidence packs are fixtures (paraphrased text with real club domains), not live data. Trips B and C were held out: "
             "the lessons were written on trip A without seeing them.", "",
             "## Trip A: lessons the tickets child wrote after working", ""]
    if "checks" in first:
        lines.append(f"Trip A score: {sum(first['checks'].values())}/{len(first['checks'])} checks.")
    lines.append("")
    for d, res in proposals:
        lines.append(f"- `{res.status}` {res.lesson_id or ''}: \"{d.lesson}\" (topic `{d.topic}`){' — ' + res.reason if res.reason else ''}")
    lines += ["", f"Served to trips B and C by `get_inherited_lessons('tickets', 'football', {inherited.token_budget})`: "
              f"{len(inherited.lessons)} lesson(s), {inherited.tokens_used} tokens, lineage {' → '.join(inherited.lineage)}.", "",
              "## Held-out trips: memory off vs on", "",
              f"{REPEATS} runs per cell. Five fixed checks: official source, flags the third-party site, no live-price claim, "
              "names the club's official resale or exchange channel, notes kickoff-time risk.", "",
              "| Trip | Memory | Mean score | Runs graded | Cited a served lesson | p50 latency | Mean output tokens |", "|---|---|---|---|---|---|---|"]
    summary = {}
    for (n, cond), outs in results.items():
        s = score(outs)
        ok = [o for o in outs if "checks" in o]
        cited = sum(1 for o in ok if set(o["finding"].lessons_used) & lesson_ids)
        summary[(n, cond)] = s
        lat = [o["latency_ms"] for o in ok]
        tok = [o["output_tokens"] or 0 for o in ok]
        lines.append(f"| {n} | {cond} | {statistics.mean(s):.3f} | {len(s)}/{len(outs)} | {cited}/{len(ok)} | "
                     f"{int(statistics.median(lat)) if lat else '-'} ms | {int(statistics.mean(tok)) if tok else '-'} |")
    off = [x for (n, c), s in summary.items() if c == "off" for x in s]
    on = [x for (n, c), s in summary.items() if c == "on" for x in s]
    if off and on:
        lines += ["", f"**Pooled: memory off {statistics.mean(off):.3f}, memory on {statistics.mean(on):.3f}, "
                  f"delta {statistics.mean(on) - statistics.mean(off):+.3f}** (n = {len(off)} vs {len(on)} graded runs)."]
    lines += ["", "### Per-check pass rate", "", "| Check | Off | On |", "|---|---|---|"]
    checks = next(iter(o["checks"] for outs in results.values() for o in outs if "checks" in o), {})
    for k in checks:
        rate = lambda cond: (lambda xs: f"{sum(xs)}/{len(xs)}")([o["checks"][k] for (n, c), outs in results.items() if c == cond for o in outs if "checks" in o])
        lines.append(f"| {k} | {rate('off')} | {rate('on')} |")
    errors = [o["error"] for outs in results.values() for o in outs if "error" in o]
    if errors: lines += ["", f"Failed calls (not graded): {len(errors)}. First: {errors[0]}"]
    lines += ["", "Small sample, one task type. Treat this as evidence the loop works end to end, not as a general quality claim."]
    out = ROOT / "docs" / "memory-results.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-25:])); print(f"Wrote {out.relative_to(ROOT)}")

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
