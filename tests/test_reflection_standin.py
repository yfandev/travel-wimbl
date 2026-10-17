import asyncio
import json
import httpx
import pytest
from wimbl.config import settings
from wimbl.integrations.crusoe import CrusoeClient
from wimbl.memory import LessonStore, get_inherited_lessons
from wimbl.memory.reflection_standin import FailedCheck, propose_all, reflect_on_defects, standin_gate
from wimbl.runlog import RunLog

OFFICIAL = "https://www.fcbarcelona.com/en/tickets/football"
CHECK = FailedCheck(check_id="names_official_resale", requirement="recommend the club's official resale or exchange platform",
                    observed="recommended 'Official ticketing' only", evidence_urls=[OFFICIAL])

@pytest.fixture
def store(tmp_path):
    return LessonStore(str(tmp_path / "l.sqlite3"))

def client_returning(tmp_path, monkeypatch, content):
    monkeypatch.setattr(settings, "crusoe_api_key", "test-key")
    body = {"id": "c", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
    async def no_sleep(_): pass
    return CrusoeClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))),
                        runlog=RunLog(str(tmp_path / "r.jsonl")), sleep=no_sleep)

def test_reflection_writes_one_scoped_lesson_per_failed_check_with_only_given_evidence(tmp_path, monkeypatch, store):
    drafts = {"lessons": [{"check_id": "1", "topic": "evidence_urls",
        "lesson": "When a club runs an official resale or ticket exchange platform, name it as the recommended fallback channel.",
        "evidence_urls": [OFFICIAL, "https://made-up.example/"]}]}
    c = client_returning(tmp_path, monkeypatch, json.dumps(drafts))
    props = asyncio.run(reflect_on_defects(c, run_id="t1", agent_role="tickets", family="football", failed_checks=[CHECK]))
    assert len(props) == 1 and props[0].scope == "football.tickets" and props[0].evidence_urls == [OFFICIAL]
    assert props[0].topic == "names_official_resale"  # from the failed check, whatever the model put in topic
    assert [r.status for r in propose_all(props, store)] == ["created"]
    assert asyncio.run(reflect_on_defects(c, run_id="t2", agent_role="tickets", family="football", failed_checks=[])) == []

def _seed(store):
    from wimbl.memory import propose_lesson
    return propose_lesson({"lesson": "When a club runs an official resale or exchange platform, name it as the recommended fallback channel.",
                           "topic": "resale_channel", "from_agent": "learning-standin", "scope": "football.tickets",
                           "source_type": "run", "run_id": "t", "evidence_urls": [OFFICIAL]}, store=store).lesson_id

def run_gate(store, lid, baseline, candidate, critical=("official_source",)):
    async def evaluate(block):
        assert lid in block  # the candidate run sees exactly the lessons under test
        return candidate
    return asyncio.run(standin_gate(store, [lid], evaluate=evaluate, target_checks=["resale"], critical_checks=list(critical),
                                    threshold=0.1, decision_ref="gate-test", baseline=baseline))

def test_gate_promotes_only_when_target_rises_past_threshold(store):
    lid = _seed(store)
    res = run_gate(store, lid, [{"resale": False, "official_source": True}] * 3, [{"resale": True, "official_source": True}] * 3)
    assert res.decision == "promote" and res.delta == 1.0
    assert [l.lesson_id for l in get_inherited_lessons("tickets", "football", 400, store=store).lessons] == [lid]

def test_gate_rejects_small_gain_or_critical_regression(store):
    lid = _seed(store)
    flat = run_gate(store, lid, [{"resale": True, "official_source": True}] * 3, [{"resale": True, "official_source": True}] * 3)
    assert flat.decision == "reject" and get_inherited_lessons("tickets", "football", 400, store=store).lessons == []
    lid2 = _seed(store)
    hurt = run_gate(store, lid2, [{"resale": False, "official_source": True}] * 2, [{"resale": True, "official_source": False}] * 2)
    assert hurt.decision == "reject" and hurt.critical_regressions == ["official_source"]
