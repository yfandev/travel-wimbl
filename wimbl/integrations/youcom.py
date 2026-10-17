from datetime import datetime, timezone
import httpx
from wimbl.config import settings

class YouSearch:
    """Search adapter. Confirm endpoint and response schema against your You.com plan/docs."""
    async def search(self, query: str, count: int | None = None) -> list[dict]:
        count = count or settings.wimbl_max_search_results
        if not settings.you_api_key:
            if settings.wimbl_demo_mode:
                now = datetime.now(timezone.utc).isoformat()
                return [
                    {"title": "ATP Tour tournament calendar", "url": "https://www.atptour.com/en/tournaments", "snippet": "Demo source. Confirm event dates on the official site.", "retrieved_at": now},
                    {"title": "Wimbledon Championships — official site", "url": "https://www.wimbledon.com/", "snippet": "Demo source. Check dates, tickets and current policies directly.", "retrieved_at": now},
                    {"title": "Visit London — destination guide", "url": "https://visitlondon.com/", "snippet": "Demo source. Costs and availability are not confirmed.", "retrieved_at": now},
                ][:count]
            raise RuntimeError("YOU_API_KEY is missing and demo mode is disabled.")
        headers = {"X-API-Key": settings.you_api_key, "Accept": "application/json"}
        params = {"q": query, "count": count}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(settings.you_search_endpoint, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()
        results = payload.get("results") or payload.get("web", {}).get("results") or payload.get("hits") or []
        normalized = []
        for item in results[:count]:
            url = item.get("url") or item.get("link")
            title = item.get("title") or item.get("name")
            if not url or not title:
                continue
            normalized.append({"title": str(title), "url": str(url),
                "snippet": str(item.get("description") or item.get("snippet") or item.get("content") or ""),
                "retrieved_at": datetime.now(timezone.utc).isoformat()})
        return normalized
