import asyncio
import json
import httpx
import pytest
from pydantic import BaseModel
from wimbl.config import settings
from wimbl.integrations import crusoe
from wimbl.integrations.crusoe import CrusoeClient, LLMError, StructuredOutputError, extract_json
from wimbl.integrations.models import CHILD_MODEL, SUPER, model_for
from wimbl.runlog import FIELDS, RunLog

TOOLS = [{"type": "function", "function": {"name": "search_tickets", "description": "Find official ticket listings",
    "parameters": {"type": "object", "properties": {"team": {"type": "string"}}, "required": ["team"]}}}]

class Ticket(BaseModel):
    team: str
    official: bool

def completion(content="", model=SUPER, tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls: message["tool_calls"] = tool_calls
    return {"id": "c1", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}

@pytest.fixture
def make(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "crusoe_api_key", "test-key")
    def build(handler, **kw):
        async def no_sleep(_): pass
        log = RunLog(str(tmp_path / "runs.jsonl"))
        return CrusoeClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), runlog=log, sleep=no_sleep, **kw), log
    return build

def test_routing_uses_exact_catalog_ids():
    assert model_for("controller") == model_for("verifier") == model_for("learning") == SUPER == "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B"
    assert model_for("tickets") == CHILD_MODEL
    with pytest.raises(ValueError): model_for("planner_that_does_not_exist")

def test_run_record_uses_returned_model_and_never_logs_prompts_or_keys(make):
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json=completion("ready", model="nvidia/Nemotron-3-Super-120B-A12B-v1"))
    client, log = make(handler)
    result = asyncio.run(client.chat("controller", [{"role": "user", "content": "secret prompt"}], run_id="r1"))
    row = log.read("r1")[0]
    assert set(FIELDS) <= set(row)
    assert row["model_id_requested"] == SUPER and row["model_id_returned"] == "nvidia/Nemotron-3-Super-120B-A12B-v1"
    assert row["input_tokens"] == 100 and row["cost_estimate_usd"] == round((100 * 0.30 + 20 * 2.40) / 1e6, 6)
    raw = log.path.read_text()
    assert "secret prompt" not in raw and "test-key" not in raw and result.text == "ready"

def test_retries_429_and_5xx_with_backoff_but_not_401(make, monkeypatch):
    monkeypatch.setattr(crusoe.random, "uniform", lambda a, b: 0)
    statuses, delays = iter([429, 503, 200]), []
    def flaky(request):
        s = next(statuses)
        return httpx.Response(s, json=completion("ok") if s == 200 else {"error": {"message": "busy"}})
    client, log = make(flaky)
    async def record_sleep(d): delays.append(d)
    client._sleep = record_sleep
    asyncio.run(client.chat("tickets", [{"role": "user", "content": "x"}], run_id="r2"))
    assert delays == [1.0, 2.0] and log.read("r2")[0]["attempts"] == 3
    calls = []
    def denied(request):
        calls.append(request)
        return httpx.Response(401, json={"error": {"message": "bad key"}})
    client, log = make(denied)
    with pytest.raises(Exception):
        asyncio.run(client.chat("tickets", [{"role": "user", "content": "x"}], run_id="r3"))
    assert len(calls) == 1 and log.read("r3")[0]["status"] == "error"

def test_gives_up_after_four_attempts(make):
    calls = []
    def down(request):
        calls.append(request)
        return httpx.Response(500, json={"error": {"message": "down"}})
    client, log = make(down)
    with pytest.raises(LLMError):
        asyncio.run(client.chat("tickets", [{"role": "user", "content": "x"}], run_id="r4"))
    assert len(calls) == 4 and log.read("r4")[0]["attempts"] == 4

def test_structured_falls_back_when_response_format_unsupported_and_repairs_once(make):
    bodies = []
    replies = iter([httpx.Response(400, json={"error": {"message": "response_format not supported"}}),
                    httpx.Response(200, json=completion("<think>hmm</think> {\"team\": \"Barcelona\"}")),
                    httpx.Response(200, json=completion("```json\n{\"team\": \"Barcelona\", \"official\": true}\n```"))])
    def handler(request):
        bodies.append(json.loads(request.content))
        return next(replies)
    client, _ = make(handler)
    result = asyncio.run(client.structured("verifier", [{"role": "user", "content": "x"}], Ticket, run_id="r5"))
    assert result.parsed == Ticket(team="Barcelona", official=True)
    assert "response_format" in bodies[0] and "response_format" not in bodies[1]
    assert client.capabilities[SUPER]["response_format"] is False

def test_structured_raises_after_failed_repair(make):
    client, _ = make(lambda r: httpx.Response(200, json=completion("not json at all")))
    with pytest.raises(StructuredOutputError):
        asyncio.run(client.structured("verifier", [{"role": "user", "content": "x"}], Ticket, run_id="r6"))

def test_native_tool_call_is_validated(make):
    call = [{"id": "t1", "type": "function", "function": {"name": "search_tickets", "arguments": "{\"team\": \"Barcelona\"}"}}]
    client, log = make(lambda r: httpx.Response(200, json=completion(tool_calls=call)))
    result = asyncio.run(client.act("tickets", [{"role": "user", "content": "x"}], TOOLS, run_id="r7"))
    assert result.tool_calls == [{"name": "search_tickets", "arguments": {"team": "Barcelona"}}]
    assert log.read("r7")[0]["tool_calls"] == ["search_tickets"]

def test_json_action_fallback_when_model_ignores_tools(make):
    replies = iter([completion("I would search for tickets."), completion('{"tool": "search_tickets", "args": {"team": "Barcelona"}}')])
    client, _ = make(lambda r: httpx.Response(200, json=next(replies)))
    result = asyncio.run(client.act("tickets", [{"role": "user", "content": "x"}], TOOLS, run_id="r8"))
    assert result.tool_calls == [{"name": "search_tickets", "arguments": {"team": "Barcelona"}}]

def test_invalid_fallback_action_is_not_executed(make):
    replies = iter([completion("no tools"), completion('{"tool": "book_hotel", "args": {}}')])
    client, _ = make(lambda r: httpx.Response(200, json=next(replies)))
    assert asyncio.run(client.act("tickets", [{"role": "user", "content": "x"}], TOOLS, run_id="r9")).tool_calls == []

def test_concurrency_is_capped(make):
    active = peak = 0
    async def handler(request):
        nonlocal active, peak
        active += 1; peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json=completion("ok"))
    client, _ = make(handler, max_concurrency=2)
    async def run():
        await asyncio.gather(*[client.chat("tickets", [{"role": "user", "content": "x"}], run_id="r10") for _ in range(6)])
    asyncio.run(run())
    assert peak == 2

def test_demo_mode_makes_no_call_and_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "crusoe_api_key", "")
    monkeypatch.setattr(settings, "wimbl_demo_mode", True)
    log = RunLog(str(tmp_path / "runs.jsonl"))
    result = asyncio.run(CrusoeClient(runlog=log).chat("controller", [{"role": "user", "content": "x"}], run_id="r11"))
    assert result.demo and result.model is None and log.read("r11")[0]["status"] == "demo"

def test_extract_json_handles_prose_around_object():
    assert extract_json('Sure! {"a": 1} hope that helps') == {"a": 1}
