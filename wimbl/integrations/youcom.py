import asyncio
from datetime import datetime, timezone
import httpx
from wimbl.agents.hierarchy import family_for
from wimbl.config import settings
from wimbl.integrations.cache import ResponseCache

SEARCH_TTL = 6 * 3600
CONTENTS_TTL = 24 * 3600
RESEARCH_TTL = 24 * 3600
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

def _now() -> str: return datetime.now(timezone.utc).isoformat()

class YouAPIError(RuntimeError):
    """A You.com call failed. Key, credit, scope and request errors (401/402/403/422) are not retryable."""
    def __init__(self, status_code: int | None, message: str, retryable: bool | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable if retryable is not None else (status_code is None or status_code in RETRYABLE_STATUS)

# Demo fixtures per agent family. Labelled "demo" so they are never credited to You.com.
DEMO_SEARCH = {
    "football": [
        {"title": "FC Barcelona — official site", "url": "https://www.fcbarcelona.com/en/", "snippet": "DEMO SOURCE — confirm fixtures and ticket rules on the official club site."},
        {"title": "UEFA Champions League — official site", "url": "https://www.uefa.com/uefachampionsleague/", "snippet": "DEMO SOURCE — confirm fixtures and venues on the official site."},
        {"title": "Visit Barcelona — match-day travel guide", "url": "https://www.barcelonaturisme.com/", "snippet": "DEMO SOURCE — costs and availability are not confirmed."},
    ],
}
DEMO_PAGES = {
    "https://www.fcbarcelona.com/en/": "# FC Barcelona\nDEMO PAGE — confirm fixtures and ticket rules on the official club site.",
    "https://www.uefa.com/uefachampionsleague/": "# UEFA Champions League\nDEMO PAGE — confirm fixtures and venues on the official site.",
}

class YouSearch:
    """You.com Web Search (POST /v1/search), Contents (POST /v1/contents) and Research (POST /v1/research) adapter with
    retries and a TTL cache."""
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, cache: ResponseCache | None = None,
                 use_cache: bool = True, max_attempts: int = 3, sleep=asyncio.sleep):
        self.transport = transport
        self.cache = cache or (ResponseCache(settings.you_cache_path) if use_cache and settings.you_cache_enabled else None)
        self.max_attempts = max_attempts
        self._sleep = sleep

    def _require_key(self) -> bool:
        """True when a live call is allowed; False for demo mode; raises when neither applies."""
        if settings.you_api_key: return True
        if settings.wimbl_demo_mode: return False
        raise YouAPIError(None, "YOU_API_KEY is missing and demo mode is disabled.", retryable=False)

    async def _post(self, endpoint: str, body: dict, ttl: int, cacheable=lambda payload: True, *,
                    timeout: float = 25, attempts: int | None = None) -> tuple[object, str, bool]:
        """POST with retries. Only responses that pass `cacheable` are stored, so a transient miss is not pinned for the TTL."""
        key = ResponseCache.key(endpoint, body)
        if self.cache and (hit := self.cache.get(key, ttl)):
            return hit["payload"], hit["retrieved_at"], True
        headers = {"X-API-Key": settings.you_api_key, "Content-Type": "application/json", "Accept": "application/json"}
        error = YouAPIError(None, "You.com request was not attempted.")
        attempts = attempts or self.max_attempts
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            for attempt in range(attempts):
                try:
                    response = await client.post(endpoint, headers=headers, json=body)
                except httpx.TimeoutException:
                    error = YouAPIError(None, "You.com request timed out.")
                except httpx.TransportError as exc:
                    error = YouAPIError(None, f"You.com request failed: {type(exc).__name__}.")
                else:
                    if response.status_code < 400:
                        payload, retrieved_at = response.json(), _now()
                        if self.cache and cacheable(payload): self.cache.put(key, endpoint, payload, retrieved_at)
                        return payload, retrieved_at, False
                    error = YouAPIError(response.status_code, f"You.com returned HTTP {response.status_code}: {response.text[:300]}")
                    if not error.retryable: raise error
                if attempt + 1 < attempts: await self._sleep(0.5 * 2 ** attempt)
        raise error

    async def search(self, query: str, count: int | None = None, *, boost_domains: list[str] | None = None,
                     include_domains: list[str] | None = None) -> list[dict]:
        if boost_domains and include_domains:
            raise ValueError("You.com does not accept include_domains together with boost_domains.")
        count = max(1, min(count or settings.wimbl_max_search_results, 100))
        if not self._require_key():
            family = family_for(query)
            rows = DEMO_SEARCH.get(family, DEMO_SEARCH["football"])[:count]
            return [dict(r, retrieved_at=_now(), source="demo", page_age=None, provider_request_id=None, cache_hit=False) for r in rows]
        body = {"query": query, "count": count}
        if boost_domains: body["boost_domains"] = boost_domains
        if include_domains: body["include_domains"] = include_domains
        payload, retrieved_at, cache_hit = await self._post(settings.you_search_endpoint, body, SEARCH_TTL,
                                                            cacheable=lambda p: bool(_search_items(p)))
        results = _search_items(payload)
        request_id = ((payload if isinstance(payload, dict) else {}).get("metadata") or {}).get("search_uuid")
        normalized = []
        for item in results[:count]:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link")
            title = item.get("title") or item.get("name")
            if not url or not title:
                continue
            snippets = item.get("snippets") if isinstance(item.get("snippets"), list) else []
            normalized.append({"title": str(title), "url": str(url),
                "snippet": str(item.get("description") or " ".join(map(str, snippets[:2])) or item.get("snippet") or ""),
                "page_age": item.get("page_age"), "provider_request_id": request_id,
                "retrieved_at": retrieved_at, "cache_hit": cache_hit, "source": "You.com"})
        return normalized

    async def contents(self, urls: list[str]) -> list[dict]:
        """Fetch page markdown for up to 10 URLs. Failed URLs come back with markdown None."""
        urls = list(dict.fromkeys(urls))[:10]
        if not urls: return []
        if not self._require_key():
            return [{"url": u, "title": None, "markdown": DEMO_PAGES.get(u), "retrieved_at": _now(), "cache_hit": False, "source": "demo"} for u in urls]
        body = {"urls": urls, "formats": ["markdown"], "crawl_timeout": 10, "max_age": CONTENTS_TTL}
        payload, retrieved_at, cache_hit = await self._post(settings.you_contents_endpoint, body, CONTENTS_TTL,
            cacheable=lambda p: bool(_content_rows(p)) and all(r.get("markdown") for r in _content_rows(p)))
        return [{"url": str(r.get("url") or ""), "title": r.get("title"), "markdown": r.get("markdown"),
                 "retrieved_at": retrieved_at, "cache_hit": cache_hit, "source": "You.com"} for r in _content_rows(payload)]

    async def research(self, query: str, schema: dict, *, boost_domains: list[str] | None = None) -> dict | None:
        """Research API (POST /v1/research) with a JSON output schema. Returns None in demo mode: there is no research fixture.
        One attempt only: a standard call takes 10-50 s and is billed per call, so a timeout is not retried."""
        if not self._require_key(): return None
        body = {"input": query, "research_effort": settings.you_research_effort, "output_schema": schema}
        if boost_domains: body["source_control"] = {"boost_domains": boost_domains}
        payload, retrieved_at, cache_hit = await self._post(settings.you_research_endpoint, body, RESEARCH_TTL,
            cacheable=lambda p: isinstance(_research_output(p).get("content"), dict), timeout=settings.you_research_timeout_s, attempts=1)
        output = _research_output(payload)
        content = output.get("content")
        return {"content": content if isinstance(content, dict) else {},
                "sources": [s for s in output.get("sources") or [] if isinstance(s, dict) and s.get("url")],
                "warnings": (payload.get("warnings") if isinstance(payload, dict) else None) or [],
                "retrieved_at": retrieved_at, "cache_hit": cache_hit}

def _research_output(payload) -> dict:
    return ((payload.get("output") if isinstance(payload, dict) else None) or {})

def _search_items(payload) -> list:
    """Official response shape: results.web[], falling back to results.news[]."""
    root = (payload.get("results") or {}) if isinstance(payload, dict) else {}
    if isinstance(root, list): return root
    if not isinstance(root, dict): return []
    return root.get("web") or (root["news"] if isinstance(root.get("news"), list) else [])

def _content_rows(payload) -> list[dict]:
    rows = payload if isinstance(payload, list) else (
        (payload.get("results") or payload.get("contents") or payload.get("data") or []) if isinstance(payload, dict) else [])
    return [r for r in rows if isinstance(r, dict)]
