from datetime import datetime, timezone
import httpx
from wimbl.config import settings

class YouSearch:
    """You.com Web Search API adapter (POST /v1/search)."""
    async def search(self, query: str, count: int | None = None) -> list[dict]:
        count = max(1, min(count or settings.wimbl_max_search_results, 100))
        if not settings.you_api_key:
            if settings.wimbl_demo_mode:
                now = datetime.now(timezone.utc).isoformat()
                return [
                    {"title": "ATP Tour tournament calendar", "url": "https://www.atptour.com/en/tournaments", "snippet": "DEMO SOURCE — confirm event dates on the official site.", "retrieved_at": now},
                    {"title": "Wimbledon Championships — official site", "url": "https://www.wimbledon.com/", "snippet": "DEMO SOURCE — check dates, tickets and current policies directly.", "retrieved_at": now},
                    {"title": "Visit London — destination guide", "url": "https://visitlondon.com/", "snippet": "DEMO SOURCE — costs and availability are not confirmed.", "retrieved_at": now},
                ][:count]
            raise RuntimeError("YOU_API_KEY is missing and demo mode is disabled.")
        headers = {"X-API-Key": settings.you_api_key, "Content-Type": "application/json", "Accept": "application/json"}
        body = {"query": query, "count": count}
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(settings.you_search_endpoint, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        # Official response shape: results.web[] and results.news[].
        root = payload.get("results") or {}
        if isinstance(root, dict):
            results = root.get("web") or []
            if not results and isinstance(root.get("news"), list):
                results = root["news"]
        elif isinstance(root, list):
            results = root
        else:
            results = []
        normalized = []
        for item in results[:count]:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link")
            title = item.get("title") or item.get("name")
            if not url or not title:
                continue
            normalized.append({"title": str(title), "url": str(url),
                "snippet": str(item.get("description") or item.get("snippet") or item.get("content") or ""),
                "retrieved_at": datetime.now(timezone.utc).isoformat()})
        return normalized
