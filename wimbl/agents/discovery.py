from datetime import datetime, timezone
from wimbl.agents.hierarchy import EVENT_VENUES, family_for, official_domain, official_domains
from wimbl.integrations.youcom import YouSearch
from wimbl.schemas import Evidence, TripCandidate, TripRequest

class DiscoveryAgent:
    def __init__(self, search: YouSearch | None = None): self.search = search or YouSearch()

    async def discover(self, request: TripRequest) -> list[TripCandidate]:
        group = family_for(request.interest)
        # Search for the event, not the package: origin and budget words dilute event results.
        query = f"{request.interest} official event schedule dates tickets" + (f" {request.dates}" if request.dates else "")
        results = await self.search.search(query, boost_domains=official_domains(group))
        if not results: return []
        evidence = [Evidence(title=r["title"], url=r["url"], snippet=r.get("snippet", ""), source=r.get("source", "You.com"),
            retrieved_at=r.get("retrieved_at") or datetime.now(timezone.utc).isoformat(), page_age=r.get("page_age"),
            provider_request_id=r.get("provider_request_id"), cache_hit=r.get("cache_hit", False)) for r in results]
        # Prefer an official event site with a fixed venue, then any official site, then a keyword match.
        keywords = (request.interest.lower(), "tournament", "match", "event")
        event = (next((e for e in evidence if official_domain(e.url, group) in EVENT_VENUES), None)
                 or next((e for e in evidence if official_domain(e.url, group)), None)
                 or next((e for e in evidence if any(k in (e.title + " " + e.snippet).lower() for k in keywords)), evidence[0]))
        destination = EVENT_VENUES.get(official_domain(event.url, group) or "", "Destination to confirm from official event source")
        return [TripCandidate(title=f"{request.interest.title()} event-led trip candidate", destination=destination,
            event=event.title, dates=request.dates, estimated_total=None, currency=request.currency.upper(),
            rationale=f"Found sources related to '{request.interest}'. Confirm dates, tickets, transport and lodging before treating this as bookable.",
            evidence=evidence, caveats=["No live ticket inventory confirmed", "Flight and hotel prices not yet priced or verified",
            "Search snippets may be stale; confirm claims on official sources"])]
