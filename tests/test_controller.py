import asyncio
import json
import httpx
from wimbl.config import settings
from wimbl.controller import TripController
from wimbl.integrations.cache import ResponseCache
from wimbl.integrations.crusoe import LLMError, LLMResult
from wimbl.integrations.models import CHILD_MODEL
from wimbl.integrations.youcom import YouAPIError, YouSearch
from wimbl.memory import SharedMemory
from wimbl.schemas import TripRequest

MATCH = "https://www.fcbarcelona.com/en/matches/138374/fc-barcelona-real-madrid"
PAGE = ("# FC Barcelona - Real Madrid\nBuy your tickets here for the La Liga match between FC Barcelona - Real Madrid, "
        "on Sun 25 Oct 2026, 20:00 GMT.\nKickoff CET 21:00\nFrom 2.350€")
RESEARCH = {"output": {"content_type": "object", "sources": [{"url": MATCH, "title": "FC Barcelona - Real Madrid", "snippets": []}],
    "content": {"facts": [
        {"kind": "match_date", "value": "Sun 25 Oct 2026", "amount": None, "currency": None, "source_url": MATCH, "quote": "on Sun 25 Oct 2026, 20:00 GMT"},
        {"kind": "kickoff_time", "value": "21:00 CET", "amount": None, "currency": None, "source_url": MATCH, "quote": "Kickoff CET 21:00"},
        {"kind": "ticket_channel", "value": "Official match ticket page", "amount": None, "currency": None, "source_url": MATCH, "quote": "Buy your tickets here for the La Liga match"},
        {"kind": "ticket_price", "value": "VIP from 2,350 EUR", "amount": 2350, "currency": "EUR", "source_url": MATCH, "quote": "From 2.350€"}],
        "unofficial_sources": ["StubHub"], "risks": ["Kickoff may move for TV."]}}}

def live_you(tmp_path, research=RESEARCH):
    def handler(request):
        url = str(request.url)
        if url == settings.you_search_endpoint:
            return httpx.Response(200, json={"results": {"web": [{"url": MATCH, "title": "FC Barcelona - Real Madrid", "description": "Official match page"}]}, "metadata": {"search_uuid": "s1"}})
        if url == settings.you_contents_endpoint:
            return httpx.Response(200, json=[{"url": u, "markdown": PAGE} for u in json.loads(request.content)["urls"]])
        assert url == settings.you_research_endpoint
        return research if isinstance(research, httpx.Response) else httpx.Response(200, json=research)
    async def no_sleep(_): pass
    return YouSearch(transport=httpx.MockTransport(handler), cache=ResponseCache(tmp_path / "cache.jsonl"), sleep=no_sleep)

class TicketsChild:
    """Stands in for CrusoeClient: records the call and returns parsed advice, or raises."""
    def __init__(self, fail=False): self.calls, self.fail = [], fail
    async def structured(self, role, messages, schema, **kwargs):
        self.calls.append((role, kwargs))
        if self.fail: raise LLMError("RateLimitError (HTTP 429)")
        return LLMResult(text="", model=CHILD_MODEL, parsed=schema(official_source_url=MATCH, recommended_channel="Official FC Barcelona ticket page",
                         unofficial_sources=["StubHub"], price_is_live=False, risks=["Kickoff can move for broadcast."]))

def test_demo_run_confirms_only_the_official_event_page(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "")
    monkeypatch.setattr(settings, "wimbl_demo_mode", True)
    controller = TripController(you=YouSearch(use_cache=False), memory=SharedMemory(str(tmp_path / "m.jsonl")))
    result = asyncio.run(controller.run(TripRequest(interest="football")))
    candidate = result.candidates[0]
    assert candidate.destination == "Barcelona, Spain"
    assert [e.url for e in candidate.evidence if e.verified] == ["https://www.fcbarcelona.com/en/"]
    assert {f.code for f in result.findings} == {"PRICE_UNCONFIRMED", "DATES_UNSET"}
    assert result.status == "needs_review" and result.controller_decision == "escalate"
    assert "Confirmed 1 official page(s) with demo pages." in result.steps

def test_search_failure_becomes_a_finding_not_a_crash(tmp_path):
    class Down:
        async def discover(self, request): raise YouAPIError(402, "You.com returned HTTP 402: insufficient credits")
    controller = TripController(discovery=Down(), you=YouSearch(use_cache=False), memory=SharedMemory(str(tmp_path / "m.jsonl")))
    result = asyncio.run(controller.run(TripRequest(interest="football")))
    assert result.status == "error" and result.controller_decision == "escalate"
    assert [f.code for f in result.findings] == ["SEARCH_UNAVAILABLE"]

def test_live_run_adds_quote_checked_facts_and_ticket_advice(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "test-key")
    monkeypatch.setattr(settings, "wimbl_demo_mode", False)
    child = TicketsChild()
    controller = TripController(you=live_you(tmp_path), memory=SharedMemory(str(tmp_path / "m.jsonl")), llm=child)
    result = asyncio.run(controller.run(TripRequest(interest="FC Barcelona home match")))
    candidate = result.candidates[0]
    assert [(f.kind, f.verified) for f in candidate.facts] == [("match_date", True), ("kickoff_time", True), ("ticket_channel", True), ("ticket_price", True)]
    assert candidate.dates == "Sun 25 Oct 2026" and candidate.destination == "Barcelona, Spain"
    codes = {f.code for f in result.findings}
    assert "DATES_UNSET" not in codes and "KICKOFF_UNCONFIRMED" not in codes and "TICKET_CHANNEL_UNCONFIRMED" not in codes
    assert {"PRICE_UNCONFIRMED", "TICKET_PRICES_NOT_LIVE"} <= codes  # no invented trip total; prices are not live
    assert candidate.ticket_advice.model == CHILD_MODEL and not candidate.ticket_advice.price_is_live
    assert child.calls[0][0] == "tickets" and child.calls[0][1]["max_tokens"] == 6000
    assert any("StubHub" in c for c in candidate.caveats)
    assert any(s.startswith("You.com Research returned 4 fact(s)") and "quotes confirmed for 4: 4 on the page" in s for s in result.steps)
    assert result.status == "needs_review" and result.controller_decision == "escalate"

def test_research_and_child_failures_become_findings_not_crashes(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "test-key")
    monkeypatch.setattr(settings, "wimbl_demo_mode", False)
    down = TripController(you=live_you(tmp_path / "a", httpx.Response(402, json={"error": "credits"})),
                          memory=SharedMemory(str(tmp_path / "m.jsonl")), llm=TicketsChild())
    result = asyncio.run(down.run(TripRequest(interest="FC Barcelona home match")))
    assert "FACTS_UNAVAILABLE" in {f.code for f in result.findings} and not result.candidates[0].facts
    flaky = TripController(you=live_you(tmp_path / "b"), memory=SharedMemory(str(tmp_path / "m.jsonl")), llm=TicketsChild(fail=True))
    result = asyncio.run(flaky.run(TripRequest(interest="FC Barcelona home match")))
    assert "TICKETS_CHILD_UNAVAILABLE" in {f.code for f in result.findings}
    assert len(result.candidates[0].facts) == 4 and result.candidates[0].ticket_advice is None
