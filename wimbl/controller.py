import re
from uuid import uuid4
from wimbl.agents.discovery import DiscoveryAgent
from wimbl.agents.hierarchy import family_for, inheritance_chain, official_domain
from wimbl.agents.verifier import IndependentVerifier
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
    def __init__(self, discovery=None, verifier=None, memory=None, you=None):
        self.you = you or getattr(discovery, "search", None) or YouSearch()
        self.discovery = discovery or DiscoveryAgent(search=self.you)
        self.verifier = verifier or IndependentVerifier()
        self.memory = memory or SharedMemory()

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
        findings = []
        for candidate in candidates:
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
        scope = group if group in {"tennis", "football"} else "sports"
        self.memory.add(scope=scope, lesson=f"Discovery run for '{request.interest}' returned {len(candidates)} candidate(s); findings: {[f.code for f in findings]}.",
            source=f"run:{run_id}", confidence=0.35, validated=False, tags=["run-summary", group])
        return TripResult(run_id=run_id, interest=request.interest, status=status,
            acceptance_criteria=self.verifier.acceptance_criteria(), candidates=candidates, findings=findings,
            controller_decision=decision, steps=steps)
