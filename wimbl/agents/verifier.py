from wimbl.agents.hierarchy import official_domain
from wimbl.schemas import TripCandidate, TripRequest, VerificationFinding

class IndependentVerifier:
    """Deterministic checks independent of the discovery agent's self-assessment."""
    def verify(self, request: TripRequest, candidate: TripCandidate) -> list[VerificationFinding]:
        findings = []
        if not candidate.evidence:
            findings.append(VerificationFinding(severity="error", code="NO_EVIDENCE", message="Candidate has no source evidence."))
        official = [e for e in candidate.evidence if official_domain(e.url)]
        if not official:
            findings.append(VerificationFinding(severity="warning", code="NO_OFFICIAL_SOURCE", message="No recognized official event source found; verify the event directly."))
        elif not any(e.verified for e in official):
            findings.append(VerificationFinding(severity="warning", code="OFFICIAL_SOURCE_UNCONFIRMED", message="Official source found, but its page content did not confirm the event; open it before relying on it."))
        if candidate.estimated_total is None:
            findings.append(VerificationFinding(severity="warning", code="PRICE_UNCONFIRMED", message="Total trip price is missing; do not claim the package fits the budget."))
        elif candidate.estimated_total > request.budget:
            findings.append(VerificationFinding(severity="error", code="OVER_BUDGET", message=f"Estimated total exceeds budget ({candidate.estimated_total:.2f} > {request.budget:.2f})."))
        if not (candidate.dates or request.dates):
            findings.append(VerificationFinding(severity="warning", code="DATES_UNSET", message="Dates are missing; availability and feasibility cannot be verified."))
        if not candidate.destination or "to confirm" in candidate.destination.lower():
            findings.append(VerificationFinding(severity="warning", code="DESTINATION_UNCONFIRMED", message="Destination has not been established from authoritative evidence."))
        return findings

    @staticmethod
    def acceptance_criteria() -> list[str]:
        return [
            "Candidate is grounded in clickable source URLs.",
            "Event identity and dates are confirmed by an official source.",
            "Travel dates and destination are compatible with the event.",
            "Comparable total trip cost is itemized and within budget.",
            "Ticket, transport and lodging availability are labelled accurately.",
            "No booking or payment occurs without explicit traveler approval.",
        ]
