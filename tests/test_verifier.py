from wimbl.agents.verifier import IndependentVerifier
from wimbl.schemas import Evidence, TripCandidate, TripRequest

def test_missing_price_and_dates_are_flagged():
    req = TripRequest(interest="football", origin="SFO", budget=2000)
    c = TripCandidate(title="T", destination="Barcelona, Spain", event="FC Barcelona", rationale="test",
        evidence=[Evidence(title="Official", url="https://www.fcbarcelona.com/en/", retrieved_at="2026-01-01T00:00:00Z")])
    codes = {f.code for f in IndependentVerifier().verify(req, c)}
    assert {"PRICE_UNCONFIRMED", "DATES_UNSET"} <= codes

def test_over_budget_is_error():
    req = TripRequest(interest="football", origin="SFO", budget=100, dates="2027-07-01")
    c = TripCandidate(title="T", destination="Barcelona", event="FC Barcelona", estimated_total=200, rationale="test",
        evidence=[Evidence(title="Official", url="https://www.fcbarcelona.com/en/", retrieved_at="2026-01-01T00:00:00Z")])
    assert any(f.code == "OVER_BUDGET" and f.severity == "error" for f in IndependentVerifier().verify(req, c))
