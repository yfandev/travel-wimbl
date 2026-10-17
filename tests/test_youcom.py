import asyncio
import json
import httpx
import pytest
from wimbl.config import settings
from wimbl.integrations.cache import ResponseCache
from wimbl.integrations.youcom import YouAPIError, YouSearch

SEARCH_PAYLOAD = {"results": {"web": [{"url": "https://www.fcbarcelona.com/en/", "title": "FC Barcelona", "description": "Official site",
    "page_age": "2026-10-01T00:00:00Z"}], "news": []}, "metadata": {"search_uuid": "abc-123", "query": "q", "latency": 0.2}}

@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "test-key")
    monkeypatch.setattr(settings, "wimbl_demo_mode", False)

def client(cache_dir, handler):
    async def no_sleep(_): pass
    return YouSearch(transport=httpx.MockTransport(handler), cache=ResponseCache(cache_dir / "cache.jsonl"), sleep=no_sleep)

def test_search_contract_provenance_and_cache(tmp_path, live):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=SEARCH_PAYLOAD)
    you = client(tmp_path, handler)
    first = asyncio.run(you.search("barcelona fixtures", count=3, boost_domains=["fcbarcelona.com"]))
    second = asyncio.run(you.search("barcelona fixtures", count=3, boost_domains=["fcbarcelona.com"]))
    assert len(calls) == 1
    assert calls[0].method == "POST" and str(calls[0].url) == settings.you_search_endpoint
    assert calls[0].headers["X-API-Key"] == "test-key"
    assert json.loads(calls[0].content) == {"query": "barcelona fixtures", "count": 3, "boost_domains": ["fcbarcelona.com"]}
    assert first[0]["provider_request_id"] == "abc-123" and first[0]["page_age"] == "2026-10-01T00:00:00Z"
    assert not first[0]["cache_hit"] and second[0]["cache_hit"]
    assert second[0]["retrieved_at"] == first[0]["retrieved_at"]
    assert "test-key" not in (tmp_path / "cache.jsonl").read_text()

def test_retries_server_errors_but_not_auth_errors(tmp_path, live):
    statuses, calls = iter([503, 200]), []
    def flaky(request):
        calls.append(request)
        status = next(statuses)
        return httpx.Response(status, json=SEARCH_PAYLOAD if status == 200 else {"error": "busy"})
    assert asyncio.run(client(tmp_path / "a", flaky).search("q"))[0]["url"] == "https://www.fcbarcelona.com/en/"
    assert len(calls) == 2
    denied_calls = []
    def denied(request):
        denied_calls.append(request)
        return httpx.Response(401, json={"error": "invalid key"})
    with pytest.raises(YouAPIError) as err:
        asyncio.run(client(tmp_path / "b", denied).search("q"))
    assert err.value.status_code == 401 and not err.value.retryable and len(denied_calls) == 1

def test_empty_search_results_are_not_cached(tmp_path, live):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"results": {"web": [], "news": []}, "metadata": {"search_uuid": "x"}})
    you = client(tmp_path, handler)
    assert asyncio.run(you.search("q")) == [] and asyncio.run(you.search("q")) == []
    assert len(calls) == 2

def test_include_with_boost_domains_is_rejected_before_any_request(tmp_path, live):
    def handler(request): raise AssertionError("no request expected")
    with pytest.raises(ValueError):
        asyncio.run(client(tmp_path, handler).search("q", include_domains=["a.com"], boost_domains=["b.com"]))

def test_contents_parses_pages_and_does_not_cache_failed_pages(tmp_path, live):
    calls = []
    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert str(request.url) == settings.you_contents_endpoint
        assert body["urls"] == ["https://www.fcbarcelona.com/en/", "https://x.example/"] and body["formats"] == ["markdown"]
        return httpx.Response(200, json=[{"url": "https://www.fcbarcelona.com/en/", "title": "W", "markdown": "# FC Barcelona"},
                                         {"url": "https://x.example/", "markdown": None}])
    you = client(tmp_path, handler)
    urls = ["https://www.fcbarcelona.com/en/", "https://x.example/", "https://www.fcbarcelona.com/en/"]
    pages = asyncio.run(you.contents(urls))
    assert [p["markdown"] for p in pages] == ["# FC Barcelona", None]
    asyncio.run(you.contents(urls))
    assert len(calls) == 2  # a failed page is not pinned in the cache for the TTL

def test_demo_rows_are_labelled_demo(monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "")
    monkeypatch.setattr(settings, "wimbl_demo_mode", True)
    rows = asyncio.run(YouSearch(use_cache=False).search("football official event schedule"))
    assert rows and all(r["source"] == "demo" for r in rows)
    assert any("uefa.com" in r["url"] for r in rows)

RESEARCH_PAYLOAD = {"output": {"content": {"facts": [], "unofficial_sources": [], "risks": []}, "content_type": "object",
    "sources": [{"url": "https://www.fcbarcelona.com/en/", "title": "FC Barcelona", "snippets": ["Official site"]}, {"title": "no url"}]}}

def test_research_contract_cache_and_no_retry_on_timeout(tmp_path, live):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=RESEARCH_PAYLOAD)
    you = client(tmp_path, handler)
    first = asyncio.run(you.research("q", {"type": "object"}, boost_domains=["fcbarcelona.com"]))
    second = asyncio.run(you.research("q", {"type": "object"}, boost_domains=["fcbarcelona.com"]))
    assert len(calls) == 1 and str(calls[0].url) == settings.you_research_endpoint
    assert calls[0].headers["X-API-Key"] == "test-key"
    assert json.loads(calls[0].content) == {"input": "q", "research_effort": "standard", "output_schema": {"type": "object"},
                                            "source_control": {"boost_domains": ["fcbarcelona.com"]}}
    assert first["content"] == RESEARCH_PAYLOAD["output"]["content"] and [s["url"] for s in first["sources"]] == ["https://www.fcbarcelona.com/en/"]
    assert not first["cache_hit"] and second["cache_hit"] and second["retrieved_at"] == first["retrieved_at"]
    slow_calls = []
    def slow(request):
        slow_calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)
    with pytest.raises(YouAPIError):
        asyncio.run(client(tmp_path / "slow", slow).research("q", {"type": "object"}))
    assert len(slow_calls) == 1  # a billed 10-50 s call is never retried after a timeout

def test_research_returns_none_in_demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "")
    monkeypatch.setattr(settings, "wimbl_demo_mode", True)
    assert asyncio.run(YouSearch(use_cache=False).research("q", {"type": "object"})) is None
