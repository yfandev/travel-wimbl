from uuid import uuid4
from wimbl.agents.discovery import DiscoveryAgent
from wimbl.agents.hierarchy import family_for, inheritance_chain
from wimbl.agents.verifier import IndependentVerifier
from wimbl.memory import SharedMemory
from wimbl.schemas import TripRequest, TripResult

class TripController:
    def __init__(self, discovery=None, verifier=None, memory=None):
        self.discovery = discovery or DiscoveryAgent()
        self.verifier = verifier or IndependentVerifier()
        self.memory = memory or SharedMemory()

    async def run(self, request: TripRequest) -> TripResult:
        run_id = str(uuid4())
        steps = ["Defined acceptance criteria before discovery."]
        group = family_for(request.interest)
        steps.append(f"Selected agent family: {' → '.join(inheritance_chain(group))}.")
        candidates = await self.discovery.discover(request)
        steps.append(f"Discovery returned {len(candidates)} candidate(s).")
        if not candidates:
            return TripResult(run_id=run_id, interest=request.interest, status="no_results",
                acceptance_criteria=self.verifier.acceptance_criteria(), candidates=[], findings=[],
                controller_decision="replan", steps=steps + ["No evidence returned; replan with a broader query."])
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
