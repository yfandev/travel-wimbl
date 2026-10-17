from datetime import datetime, timezone
from wimbl.integrations.youcom import YouSearch
from wimbl.schemas import Evidence, TripCandidate, TripRequest

class DiscoveryAgent:
    def __init__(self, search: YouSearch | None = None): self.search = search or YouSearch()

    async def discover(self, request: TripRequest) -> list[TripCandidate]:
        query = (f"{request.interest} events tournament official dates tickets travel packages hotels "
                 f"from {request.origin} budget {request.budget} {request.currency}")
        results = await self.search.search(query)
        if not results: return []
        evidence = [Evidence(title=r["title"], url=r["url"], snippet=r.get("snippet", ""),
            retrieved_at=r.get("retrieved_at") or datetime.now(timezone.utc).isoformat()) for r in results]
        event = next((e for e in evidence if any(k in (e.title + " " + e.snippet).lower()
                      for k in ("tennis", "wimbledon", "tournament", "event"))), evidence[0])
        destination = "Destination to confirm from official event source"
        if "wimbledon" in (event.title + event.url).lower(): destination = "London, United Kingdom"
        return [TripCandidate(title=f"{request.interest.title()} event-led trip candidate", destination=destination,
            event=event.title, dates=request.dates, estimated_total=None, currency=request.currency.upper(),
            rationale=f"Found sources related to '{request.interest}'. Confirm dates, tickets, transport and lodging before treating this as bookable.",
            evidence=evidence, caveats=["No live ticket inventory confirmed", "Flight and hotel prices not yet priced or verified",
            "Search snippets may be stale; confirm claims on official sources"])]
