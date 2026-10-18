import asyncio
import re
import time
from uuid import uuid4
from wimbl.agents.discovery import DiscoveryAgent
from wimbl.agents.facts import ON_PAGE, RESEARCH_SCHEMA, apply_facts, confirm_quotes, facts_from_research, research_query
from wimbl.agents.hierarchy import family_for, inheritance_chain, official_domain, official_domains
from wimbl.agents.prices import apply_ticket_fact, price_lines, price_total, summary
from wimbl.agents.tickets import advise
from wimbl.agents.verifier import IndependentVerifier
from wimbl.config import settings
from wimbl.integrations.crusoe import CrusoeClient
from wimbl.integrations.youcom import YouAPIError, YouSearch
from wimbl.memory import SharedMemory
from wimbl.schemas import TripCandidate, TripRequest, TripResult, VerificationFinding

# Words too generic to identify an event in page text.
GENERIC_WORDS = {"official", "site", "home", "page", "tour", "tournament", "tournaments", "calendar", "championships",
                 "event", "events", "tickets", "fixtures", "league", "guide", "travel"}

def _mentions_event(text: str, event: str) -> bool:
    words = [w for w in re.findall(r"[a-z]{4,}", event.lower()) if w not in GENERIC_WORDS]
    return bool(words) and any(w in text.lower() for w in words)

def _norm(url: str) -> str: return url.rstrip("/").lower()

class TripController:
    def __init__(self, discovery=None, verifier=None, memory=None, you=None, llm=None):
        self.you = you or getattr(discovery, "search", None) or YouSearch()
        self.discovery = discovery or DiscoveryAgent(search=self.you)
        self.verifier = verifier or IndependentVerifier()
        self.memory = memory or SharedMemory()
        self.llm = llm or CrusoeClient()

    async def _facts(self, request: TripRequest, candidate: TripCandidate, group: str, run_id: str,
                     steps: list[str]) -> list[VerificationFinding]:
        """You.com Research extracts event and ticket facts, You.com Contents re-reads the cited pages so code can check each
        quote, then the Nemotron tickets child reads the facts. Network work stays here so the verifier stays pure."""
        if not settings.wimbl_research_facts: return []
        started = time.monotonic()
        try:
            result = await self.you.research(research_query(request), RESEARCH_SCHEMA, boost_domains=official_domains(group))
        except YouAPIError as exc:
            steps.append(f"You.com Research failed (HTTP {exc.status_code or 'n/a'}); no event or ticket facts this run.")
            return [VerificationFinding(severity="warning", code="FACTS_UNAVAILABLE", message=str(exc)[:300])]
        if result is None:
            steps.append("Demo mode: no You.com Research call, so no event or ticket facts.")
            return []
        seconds = time.monotonic() - started
        facts = facts_from_research(result, group)
        cited = list(dict.fromkeys([f.url for f in facts if f.official] + [f.url for f in facts]))[:10]
        try: pages = await self.you.contents(cited) if cited else []
        except YouAPIError: pages = []
        verified = confirm_quotes(facts, pages, result["sources"])
        on_page = sum(f.check == ON_PAGE for f in facts)
        apply_facts(candidate, facts, result["content"])
        steps.append(f"You.com Research returned {len(facts)} fact(s) from {len(result['sources'])} source(s) in {seconds:.1f}s"
                     f"{' (cached)' if result['cache_hit'] else ''}; quotes confirmed for {verified}: {on_page} on the page "
                     f"re-read with You.com Contents, {verified - on_page} in You.com's excerpt of the page.")
        if not (facts and settings.wimbl_tickets_child): return []
        try:
            candidate.ticket_advice = await asyncio.wait_for(advise(self.llm, facts, request.interest, run_id),
                                                             settings.wimbl_child_timeout_s)
        except Exception as exc:  # the child is advice on top of the facts; its failure must not end the run
            steps.append(f"Tickets child (Nemotron) failed: {type(exc).__name__}.")
            return [VerificationFinding(severity="warning", code="TICKETS_CHILD_UNAVAILABLE", message=str(exc)[:300])]
        steps.append(f"Tickets child ran on {candidate.ticket_advice.model}, served by Crusoe Managed Inference."
                     if candidate.ticket_advice else "Tickets child skipped: CRUSOE_API_KEY is not set, so no model call was made.")
        return []

    async def _prices(self, request: TripRequest, candidate: TripCandidate, group: str) -> str | None:
        """Price the ticket, flight and hotel lines while the facts step runs; a confirmed official ticket price from that
        step fills an unpriced ticket line later. Returns a step only on failure."""
        if not settings.wimbl_price_lookup: return None
        try: candidate.line_items = await price_lines(self.you, request, candidate, group)
        except YouAPIError as exc: return f"Price lookup failed (HTTP {exc.status_code or 'n/a'}); no line items priced."
        return None

    async def _confirm(self, candidates: list[TripCandidate], group: str) -> tuple[int, str | None]:
        """Fetch official evidence pages with You.com Contents; mark Evidence.verified when the page names the event.
        Network work stays here so the verifier remains a pure, deterministic check."""
        confirmed = 0
        for candidate in candidates:
            official = [e for e in candidate.evidence if official_domain(e.url, group)][:3]
            if not official: continue
            try:
                pages = {_norm(p["url"]): p for p in await self.you.contents([e.url for e in official])}
            except YouAPIError as exc:
                return confirmed, str(exc)[:200]
            if not pages:
                return confirmed, f"You.com Contents returned no pages for {len(official)} official URL(s)."
            for e in official:
                page = pages.get(_norm(e.url))
                if page and page.get("markdown") and _mentions_event(page["markdown"], candidate.event):
                    e.verified = True
                    confirmed += 1
        return confirmed, None

    async def run(self, request: TripRequest) -> TripResult:
        run_id = str(uuid4())
        steps = ["Defined acceptance criteria before discovery."]
        group = family_for(request.interest)
        steps.append(f"Selected agent family: {' → '.join(inheritance_chain(group))}.")
        try:
            candidates = await self.discovery.discover(request)
        except YouAPIError as exc:
            decision = "replan" if exc.retryable else "escalate"
            return TripResult(run_id=run_id, interest=request.interest, status="error",
                acceptance_criteria=self.verifier.acceptance_criteria(), candidates=[],
                findings=[VerificationFinding(severity="error", code="SEARCH_UNAVAILABLE", message=str(exc)[:300])],
                controller_decision=decision, steps=steps + [f"You.com search failed (HTTP {exc.status_code or 'n/a'}); decision: {decision}."])
        steps.append(f"Discovery returned {len(candidates)} candidate(s).")
        if not candidates:
            return TripResult(run_id=run_id, interest=request.interest, status="no_results",
                acceptance_criteria=self.verifier.acceptance_criteria(), candidates=[], findings=[],
                controller_decision="replan", steps=steps + ["No evidence returned; replan with a broader query."])
        confirmed, error = await self._confirm(candidates, group)
        via = "demo pages" if all(e.source == "demo" for c in candidates for e in c.evidence) else "You.com Contents"
        steps.append(f"Contents check failed: {error}" if error else f"Confirmed {confirmed} official page(s) with {via}.")
        findings, price_error = await asyncio.gather(self._facts(request, candidates[0], group, run_id, steps),
                                                     self._prices(request, candidates[0], group))
        if price_error: steps.append(price_error)
        for candidate in candidates:
            if candidate.line_items:
                apply_ticket_fact(candidate.line_items, candidate.facts, group)
                candidate.price_total = price_total(candidate.line_items, candidate.currency)
                if candidate.price_total.complete: candidate.estimated_total = candidate.price_total.amount
                steps.append(summary(candidate.line_items, candidate.price_total))
            current = self.verifier.verify(request, candidate)
            findings.extend(current)
            if any(f.severity == "error" for f in current): candidate.status = "rejected"
            elif current: candidate.status = "needs_review"
            else: candidate.status = "verified"
        errors = any(f.severity == "error" for f in findings)
        warnings = any(f.severity == "warning" for f in findings)
        status = "needs_review" if errors or warnings else "verified"
        decision = "replan" if errors else ("escalate" if warnings else "stop")
        steps += [f"Independent verifier produced {len(findings)} finding(s).",
                  f"Controller decision: {decision}; no booking action is available."]
        scope = group if group == "football" else "sports"
        self.memory.add(scope=scope, lesson=f"Discovery run for '{request.interest}' returned {len(candidates)} candidate(s); findings: {[f.code for f in findings]}.",
            source=f"run:{run_id}", confidence=0.35, validated=False, tags=["run-summary", group])
        return TripResult(run_id=run_id, interest=request.interest, status=status,
            acceptance_criteria=self.verifier.acceptance_criteria(), candidates=candidates, findings=findings,
            controller_decision=decision, steps=steps)
