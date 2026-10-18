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

def test_fact_checks_run_only_when_facts_exist():
    from wimbl.schemas import Fact
    req = TripRequest(interest="football", dates="2026-10-25")
    base = dict(title="T", destination="Barcelona, Spain", event="FC Barcelona", rationale="test", dates="2026-10-25",
                evidence=[Evidence(title="Official", url="https://www.fcbarcelona.com/en/", retrieved_at="2026-01-01T00:00:00Z", verified=True)])
    assert {f.code for f in IndependentVerifier().verify(req, TripCandidate(**base))} == {"PRICE_UNCONFIRMED"}
    price = Fact(kind="ticket_price", value="from 2,350 EUR", amount=2350, currency="EUR", url="https://www.stubhub.example/x",
                 quote="from 2,350 EUR", observed_at="2026-10-17T22:00:00+00:00")
    codes = {f.code for f in IndependentVerifier().verify(req, TripCandidate(**base, facts=[price]))}
    assert codes == {"PRICE_UNCONFIRMED", "FACTS_UNCONFIRMED", "KICKOFF_UNCONFIRMED", "TICKET_CHANNEL_UNCONFIRMED", "TICKET_PRICES_NOT_LIVE"}

def test_dates_typed_by_the_traveler_do_not_count_as_confirmed():
    req = TripRequest(interest="football", dates="March")
    c = TripCandidate(title="T", destination="Barcelona, Spain", event="FC Barcelona", rationale="test",
        evidence=[Evidence(title="Official", url="https://www.fcbarcelona.com/en/", retrieved_at="2026-01-01T00:00:00Z")])
    assert "DATES_UNSET" in {f.code for f in IndependentVerifier().verify(req, c)}
