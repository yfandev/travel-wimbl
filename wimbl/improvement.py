"""Small baseline-vs-candidate harness; proxy metric, not a claim of real-world quality."""
from dataclasses import dataclass

@dataclass
class Scenario:
    name: str
    official_source: bool
    price: bool
    dates: bool
    within_budget: bool

SCENARIOS = [
    Scenario("complete_trip", True, True, True, True),
    Scenario("missing_price", True, False, True, True),
    Scenario("no_official_source", False, True, True, True),
    Scenario("over_budget", True, True, True, False),
    Scenario("missing_dates", True, True, False, True),
]
HELD_OUT = [Scenario("heldout_unpriced_event", True, False, True, True),
            Scenario("heldout_no_official_dates", False, True, False, True)]

def score(scenarios: list[Scenario], policy: dict) -> dict:
    detected = total = 0
    for s in scenarios:
        issues = []
        if not s.official_source: issues.append("official_source")
        if not s.price: issues.append("price")
        if not s.dates: issues.append("dates")
        if not s.within_budget: issues.append("budget")
        total += len(issues)
        detected += sum(bool(policy.get("checks", {}).get(issue, True)) for issue in issues)
    return {"detected_issues": detected, "total_issues": total, "recall": round(detected / total, 4) if total else 1.0}

def evaluate_candidate(candidate_policy: dict) -> dict:
    baseline = {"checks": {k: True for k in ("official_source", "price", "dates", "budget")}}
    base, cand = score(SCENARIOS, baseline), score(SCENARIOS, candidate_policy)
    held_base, held_cand = score(HELD_OUT, baseline), score(HELD_OUT, candidate_policy)
    passed = cand["recall"] >= base["recall"] and held_cand["recall"] >= held_base["recall"]
    return {"baseline": {"in_sample": base, "held_out": held_base},
            "candidate": {"in_sample": cand, "held_out": held_cand},
            "promotion_decision": "eligible_for_review" if passed else "rejected",
            "note": "Eligibility is not deployment. Review false positives, cost, latency, safety and scenario quality before promotion."}
