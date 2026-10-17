"""Tickets child: a Nemotron model on Crusoe reads the You.com facts and advises where to buy and what to watch."""
import json
from pydantic import BaseModel
from wimbl.schemas import Fact, TicketAdvice

PROMPT_VERSION = "tickets-advice-v1"
MAX_TOKENS = 6000  # Lightning reasons before it answers; 2048 truncated its JSON (docs/memory-results.md)

class Advice(BaseModel):
    official_source_url: str
    recommended_channel: str
    unofficial_sources: list[str]
    price_is_live: bool
    risks: list[str]

def evidence_pack(facts: list[Fact]) -> list[dict]:
    """The evidence-pack shape the tickets child already uses (scripts/measure_memory.py): one item per fact, verified first."""
    ordered = sorted(facts, key=lambda f: not f.verified)[:20]
    return [{"id": f"F{i}", "url": f.url, "observed_at": f.observed_at, "official": f.official, "quote_confirmed": f.verified,
             "text": f"{f.kind}: {f.value}. Quote: {f.quote}"} for i, f in enumerate(ordered, 1)]

async def advise(llm, facts: list[Fact], interest: str, run_id: str) -> TicketAdvice | None:
    """None in demo mode (no CRUSOE_API_KEY): no model call is made and nothing is faked."""
    task = (f"You are the tickets agent in a football-travel family. Using only this evidence, report where the traveler "
            f"should get tickets for this goal: {interest}. Prefer the official club channel and its official resale service; "
            "list third-party resellers as unofficial. Do not claim prices are live. Note risks, such as kickoff times that "
            "can move.\n" + json.dumps(evidence_pack(facts), ensure_ascii=False))
    result = await llm.structured("tickets", [{"role": "user", "content": task}], Advice, run_id=run_id,
                                  prompt_version=PROMPT_VERSION, max_tokens=MAX_TOKENS)
    if result.demo or result.parsed is None: return None
    return TicketAdvice(**result.parsed.model_dump(), model=result.model)
