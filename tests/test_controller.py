import asyncio
from wimbl.config import settings
from wimbl.controller import TripController
from wimbl.integrations.youcom import YouAPIError, YouSearch
from wimbl.memory import SharedMemory
from wimbl.schemas import TripRequest

def test_demo_run_confirms_only_the_official_event_page(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "")
    monkeypatch.setattr(settings, "wimbl_demo_mode", True)
    controller = TripController(you=YouSearch(use_cache=False), memory=SharedMemory(str(tmp_path / "m.jsonl")))
    result = asyncio.run(controller.run(TripRequest(interest="tennis")))
    candidate = result.candidates[0]
    assert candidate.destination == "London, United Kingdom"
    assert [e.url for e in candidate.evidence if e.verified] == ["https://www.wimbledon.com/"]
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
