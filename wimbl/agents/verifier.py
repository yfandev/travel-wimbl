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
        total = candidate.price_total
        if candidate.estimated_total is None:
            message = (f"Only {total.priced} of {total.lines} line items have an advertised price in {total.currency}; the total is partial, so do not claim the package fits the budget."
                       if total and total.lines else "Total trip price is missing; do not claim the package fits the budget.")
            findings.append(VerificationFinding(severity="warning", code="PRICE_UNCONFIRMED", message=message))
        elif candidate.estimated_total > request.budget:
            findings.append(VerificationFinding(severity="error", code="OVER_BUDGET", message=f"Estimated total exceeds budget ({candidate.estimated_total:.2f} > {request.budget:.2f})."))
        if not (candidate.dates or request.dates):
            findings.append(VerificationFinding(severity="warning", code="DATES_UNSET", message="Dates are missing; availability and feasibility cannot be verified."))
        if not candidate.destination or "to confirm" in candidate.destination.lower():
            findings.append(VerificationFinding(severity="warning", code="DESTINATION_UNCONFIRMED", message="Destination has not been established from authoritative evidence."))
        if candidate.facts:  # checks on extracted facts run only when a fact step ran, so demo runs are unchanged
            unconfirmed = [f for f in candidate.facts if not f.verified]
            if unconfirmed:
                findings.append(VerificationFinding(severity="warning", code="FACTS_UNCONFIRMED", message=f"{len(unconfirmed)} of {len(candidate.facts)} extracted fact(s) could not be confirmed on the cited page; treat them as leads."))
            if not any(f.verified and f.official and f.kind == "kickoff_time" for f in candidate.facts):
                findings.append(VerificationFinding(severity="warning", code="KICKOFF_UNCONFIRMED", message="No kickoff time is confirmed on an official page; kickoff times can move for broadcast."))
            if not any(f.verified and f.official and f.kind == "ticket_channel" for f in candidate.facts):
                findings.append(VerificationFinding(severity="warning", code="TICKET_CHANNEL_UNCONFIRMED", message="No official ticket channel is confirmed on an official page."))
            prices = [f for f in candidate.facts if f.kind == "ticket_price"]
            if prices:
                findings.append(VerificationFinding(severity="info", code="TICKET_PRICES_NOT_LIVE", message=f"Ticket prices are published prices seen at {prices[0].observed_at[:16].replace('T', ' ')} UTC, not live availability."))
        advertised = [l for l in candidate.line_items if l.status == "advertised"]
        if advertised:
            findings.append(VerificationFinding(severity="info", code="PRICES_ADVERTISED_NOT_LIVE", message=f"{len(advertised)} line item price(s) are advertised prices copied from their sources, not live inventory or a quote."))
        if any(l.status == "advertised" and not (l.url and l.observed_at and l.quote) for l in candidate.line_items):
            findings.append(VerificationFinding(severity="error", code="PRICE_WITHOUT_SOURCE", message="A line item shows a price without its source link, observation time and quote."))
        if total and total.amount is not None and abs(total.amount - sum(l.subtotal or 0 for l in candidate.line_items if l.currency == total.currency)) > 0.01:
            findings.append(VerificationFinding(severity="error", code="TOTAL_MISMATCH", message="The package total does not equal the sum of its line items."))
        if candidate.ticket_advice and candidate.ticket_advice.price_is_live:
            findings.append(VerificationFinding(severity="warning", code="LIVE_PRICE_CLAIM", message="The tickets child claimed a live price; search results do not prove live availability."))
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
