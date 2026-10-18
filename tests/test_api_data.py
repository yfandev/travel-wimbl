import pytest
from fastapi.testclient import TestClient
from wimbl import api, api_data
from wimbl.config import settings
from wimbl.memory import LessonStore, SharedMemory, propose_lesson
from wimbl.memory import store as store_module
from wimbl.runlog import RunLog

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "")
    monkeypatch.setattr(settings, "wimbl_demo_mode", True)
    monkeypatch.setattr(settings, "wimbl_run_log_path", str(tmp_path / "run_log.jsonl"))
    monkeypatch.setattr(api_data, "runs", api_data.RunStore(str(tmp_path / "runs.jsonl")))
    monkeypatch.setattr(api.controller, "memory", SharedMemory(str(tmp_path / "journal.jsonl")))
    monkeypatch.setattr(api, "memory", api.controller.memory)
    monkeypatch.setattr(api.controller.you, "cache", None)
    monkeypatch.setattr(store_module, "_default", LessonStore(str(tmp_path / "lessons.sqlite3")))
    return TestClient(api.app)

GOAL = {"interest": "see Barcelona at the Camp Nou", "origin": "SFO", "budget": 2500, "currency": "USD", "days": 4}

def test_cors_allows_the_next_dev_server(client):
    res = client.options("/api/runs", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in client.get("/api/runs", headers={"Origin": "http://evil.example"}).headers

def test_discovery_run_is_listed_with_timeline_and_evidence_ledger(client):
    result = client.post("/api/trips/discover", json=GOAL).json()
    assert set(result) >= {"run_id", "candidates", "findings", "controller_decision", "steps"}  # Patrick's shape, unchanged
    listed = client.get("/api/runs").json()
    assert listed[0]["run_id"] == result["run_id"] and listed[0]["mode"] == "mock" and listed[0]["evidence"] == 3
    run = client.get(f"/api/runs/{result['run_id']}").json()
    assert set(run) >= {"run_id", "goal", "mode", "criteria_hash", "constraints", "assumptions", "budget", "checks", "events"}
    assert run["events"][0] == {"t": 0, "type": "stage", "stage": "REQUEST"} and run["events"][-1]["stage"] == "FINAL RESULT"
    assert [e["t"] for e in run["events"]] == sorted(e["t"] for e in run["events"])
    assert {c["check_id"]: c["status"] for c in run["checks"]}["C6"] == "passed"  # no booking action exists
    assert any(c["status"] == "failed" for c in run["checks"])  # price and dates are unconfirmed in the demo fixtures
    ledger = run["evidence_ledger"]
    assert len(ledger) == 3 and all({"url", "source", "retrieved_at", "verified"} <= set(e) for e in ledger)
    assert [e["url"] for e in ledger if e["verified"]] == ["https://www.fcbarcelona.com/en/"]
    assert client.get("/api/runs/does-not-exist").status_code == 404

def test_runlog_returns_records_newest_first(client):
    log = RunLog()
    for i in range(3): log.write(run_id=f"r{i}", agent_role="tickets", model_id_requested="m", status="ok")
    rows = client.get("/api/runlog").json()
    assert [r["run_id"] for r in rows] == ["r2", "r1", "r0"] and rows[0]["model_id_requested"] == "m"

def test_memory_journal_shape_is_unchanged_and_lessons_have_their_own_path(client):
    client.post("/api/trips/discover", json=GOAL)
    journal = client.get("/api/memory").json()["entries"]
    assert journal and {"scope", "lesson", "source", "confidence"} <= set(journal[0])  # run journal rows, as before
    propose_lesson({"lesson": "Name the club's official resale or ticket exchange platform when advising where to buy tickets.",
                    "topic": "names_official_resale", "from_agent": "tickets", "scope": "football.tickets", "source_type": "run",
                    "run_id": "t", "evidence_urls": ["https://www.fcbarcelona.com/en/tickets/football"]})
    lessons = client.get("/api/memory/lessons").json()["entries"]
    assert len(lessons) == 1 and {"lesson_id", "evaluation_status", "scope", "topic"} <= set(lessons[0])

def test_eval_endpoints_report_the_recorded_memory_measurement(client):
    abl = client.get("/api/memory/ablation").json()
    primary = abl["metrics"][0]
    assert (primary["memory_off"], primary["memory_on"]) == (0.75, 1.0) and abl["n"] == {"off": 20, "on": 20}
    assert abl["primary_ci95"][0] > 0 and "Small sample" in abl["caveat"]
    n1 = client.get("/api/improvement/latest").json()
    held = next(m for m in n1["metrics"] if m["split"] == "heldout")
    assert held["baseline"]["mean"] == 0.75 and held["candidate"]["mean"] == 1.0 and held["candidate"]["runs"] == 20
    assert n1["decision"] == "promoted" and n1["evaluator"].startswith("stand-in")

def test_run_lists_only_agents_that_ran(client):
    rid = client.post("/api/trips/discover", json=GOAL).json()["run_id"]
    agents = {a["id"]: a for a in client.get(f"/api/runs/{rid}").json()["agents"]}
    assert list(agents) == ["sports_parent", "football_parent", "controller", "discovery", "verifier"]
    assert not agents["football_parent"]["executed"] and agents["football_parent"]["version"] == "v1"
    assert agents["verifier"]["executed"] and all(a["inherited"] == [] for a in agents.values())
    assert "facts" not in client.get(f"/api/runs/{rid}").json()  # no trip board exists, so nothing is claimed

def test_verifier_is_not_listed_when_search_fails(client, monkeypatch):
    from wimbl.integrations.youcom import YouAPIError
    async def down(request): raise YouAPIError(402, "insufficient credits")
    monkeypatch.setattr(api.controller.discovery, "discover", down)
    rid = client.post("/api/trips/discover", json=GOAL).json()["run_id"]
    ids = [a["id"] for a in client.get(f"/api/runs/{rid}").json()["agents"]]
    assert "verifier" not in ids and "discovery" in ids

def test_tickets_agent_is_listed_in_run_order_only_when_the_run_called_it(client):
    from datetime import datetime, timezone
    from wimbl.schemas import TicketAdvice, TripCandidate, TripRequest, TripResult, VerificationFinding
    def record(advice=None, findings=()):
        c = TripCandidate(title="T", destination="Barcelona, Spain", event="E", rationale="r", ticket_advice=advice)
        result = TripResult(run_id=f"run-{len(findings)}-{bool(advice)}", interest="FC Barcelona", status="needs_review",
            acceptance_criteria=[], candidates=[c], findings=list(findings), controller_decision="escalate",
            steps=["Selected agent family: global → sports → football."])
        api_data.runs.record(TripRequest(interest="FC Barcelona"), result, datetime.now(timezone.utc), 10)
        return {a["id"]: a for a in client.get(f"/api/runs/{result.run_id}").json()["agents"]}
    advice = TicketAdvice(official_source_url="https://www.fcbarcelona.com/en/tickets", recommended_channel="Official club site",
                          unofficial_sources=[], price_is_live=False, risks=[], model="nvidia/Nemotron-3.5-Lightning-30B-A3B")
    ran = record(advice)
    assert list(ran) == ["sports_parent", "football_parent", "controller", "discovery", "tickets", "verifier"]
    assert ran["tickets"]["executed"] and ran["tickets"]["note"] == "NVIDIA Nemotron · Crusoe"
    failed = record(findings=[VerificationFinding(severity="warning", code="TICKETS_CHILD_UNAVAILABLE", message="429")])
    assert failed["tickets"]["note"] == "Nemotron call failed."
    assert "tickets" not in record()

def test_fact_and_ticket_findings_fail_their_criteria():
    findings = [{"code": c, "message": c} for c in ("KICKOFF_UNCONFIRMED", "FACTS_UNCONFIRMED", "TICKET_CHANNEL_UNCONFIRMED", "LIVE_PRICE_CLAIM")]
    result = {"acceptance_criteria": api_data.IndependentVerifier.acceptance_criteria(), "findings": findings, "candidates": [{}]}
    status = {c["check_id"]: c["status"] for c in api_data._checks(result)}
    assert status == {"C1": "passed", "C2": "failed", "C3": "passed", "C4": "passed", "C5": "failed", "C6": "passed"}
    clean = {c["check_id"]: c["status"] for c in api_data._checks({**result, "findings": []})}
    assert clean["C5"] == "passed"  # C5 is checked now, not pending
