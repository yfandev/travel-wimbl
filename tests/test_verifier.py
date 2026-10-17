from wimbl.agents.verifier import IndependentVerifier
from wimbl.schemas import Evidence, TripCandidate, TripRequest

def test_missing_price_and_dates_are_flagged():
    req = TripRequest(interest="tennis", origin="SFO", budget=2000)
    c = TripCandidate(title="T", destination="London, United Kingdom", event="Wimbledon", rationale="test",
        evidence=[Evidence(title="Official", url="https://www.wimbledon.com/", retrieved_at="2026-01-01T00:00:00Z")])
    codes = {f.code for f in IndependentVerifier().verify(req, c)}
    assert {"PRICE_UNCONFIRMED", "DATES_UNSET"} <= codes

def test_over_budget_is_error():
    req = TripRequest(interest="tennis", origin="SFO", budget=100, dates="2027-07-01")
    c = TripCandidate(title="T", destination="London", event="Wimbledon", estimated_total=200, rationale="test",
        evidence=[Evidence(title="Official", url="https://www.wimbledon.com/", retrieved_at="2026-01-01T00:00:00Z")])
    assert any(f.code == "OVER_BUDGET" and f.severity == "error" for f in IndependentVerifier().verify(req, c))
