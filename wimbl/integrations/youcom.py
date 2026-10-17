import asyncio
from datetime import datetime, timezone
import httpx
from wimbl.agents.hierarchy import family_for
from wimbl.config import settings
from wimbl.integrations.cache import ResponseCache

SEARCH_TTL = 6 * 3600
CONTENTS_TTL = 24 * 3600
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
    "tennis": [
        {"title": "ATP Tour tournament calendar", "url": "https://www.atptour.com/en/tournaments", "snippet": "DEMO SOURCE — confirm event dates on the official site."},
        {"title": "Wimbledon Championships — official site", "url": "https://www.wimbledon.com/", "snippet": "DEMO SOURCE — check dates, tickets and current policies directly."},
        {"title": "Visit London — destination guide", "url": "https://visitlondon.com/", "snippet": "DEMO SOURCE — costs and availability are not confirmed."},
    ],
    "football": [
        {"title": "UEFA Champions League — official site", "url": "https://www.uefa.com/uefachampionsleague/", "snippet": "DEMO SOURCE — confirm fixtures and venues on the official site."},
        {"title": "Premier League fixtures", "url": "https://www.premierleague.com/fixtures", "snippet": "DEMO SOURCE — kick-off times can change for broadcast."},
        {"title": "Match-day travel guide", "url": "https://visitlondon.com/", "snippet": "DEMO SOURCE — costs and availability are not confirmed."},
    ],
}
DEMO_PAGES = {
    "https://www.wimbledon.com/": "# The Championships, Wimbledon\nDEMO PAGE — confirm dates and ticket rules on the official site.",
    "https://www.atptour.com/en/tournaments": "# ATP Tour calendar\nDEMO PAGE — tournament list.",
    "https://www.uefa.com/uefachampionsleague/": "# UEFA Champions League\nDEMO PAGE — confirm fixtures and venues on the official site.",
    "https://www.premierleague.com/fixtures": "# Premier League fixtures\nDEMO PAGE — fixture list.",
}

class YouSearch:
    """You.com Web Search (POST /v1/search) and Contents (POST /v1/contents) adapter with retries and a TTL cache."""
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

    async def _post(self, endpoint: str, body: dict, ttl: int, cacheable=lambda payload: True) -> tuple[object, str, bool]:
        """POST with retries. Only responses that pass `cacheable` are stored, so a transient miss is not pinned for the TTL."""
        key = ResponseCache.key(endpoint, body)
        if self.cache and (hit := self.cache.get(key, ttl)):
            return hit["payload"], hit["retrieved_at"], True
        headers = {"X-API-Key": settings.you_api_key, "Content-Type": "application/json", "Accept": "application/json"}
        error = YouAPIError(None, "You.com request was not attempted.")
        async with httpx.AsyncClient(timeout=25, transport=self.transport) as client:
            for attempt in range(self.max_attempts):
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
                if attempt + 1 < self.max_attempts: await self._sleep(0.5 * 2 ** attempt)
        raise error

    async def search(self, query: str, count: int | None = None, *, boost_domains: list[str] | None = None,
                     include_domains: list[str] | None = None) -> list[dict]:
        if boost_domains and include_domains:
            raise ValueError("You.com does not accept include_domains together with boost_domains.")
        count = max(1, min(count or settings.wimbl_max_search_results, 100))
        if not self._require_key():
            family = family_for(query)
            rows = DEMO_SEARCH.get(family, DEMO_SEARCH["tennis"])[:count]
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
