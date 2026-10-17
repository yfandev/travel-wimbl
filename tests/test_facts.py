from wimbl.agents.facts import RESEARCH_SCHEMA, apply_facts, confirm_quotes, facts_from_research
from wimbl.schemas import TripCandidate

MATCH = "https://www.fcbarcelona.com/en/matches/138374/fc-barcelona-real-madrid"
RESELLER = "https://www.stubhub.example/barca"
RESULT = {"retrieved_at": "2026-10-17T22:00:00+00:00", "cache_hit": False,
    "sources": [{"url": MATCH, "title": "FC Barcelona - Real Madrid", "snippets": ["Kickoff CET 21:00"]},
                {"url": RESELLER, "title": "StubHub", "snippets": ["Kick-off 21:00 at the Camp Nou, tickets from EUR 400"]}],
    "content": {"facts": [
        {"kind": "match_date", "value": "Sun 25 Oct 2026", "amount": None, "currency": None, "source_url": MATCH, "quote": "on Sun 25 Oct 2026, 20:00 GMT"},
        {"kind": "kickoff_time", "value": "21:00 CET", "amount": 21.0, "currency": "Europe/Madrid", "source_url": MATCH, "quote": "Kickoff CET\n\n21:00"},
        {"kind": "ticket_channel", "value": "Official ticket page", "amount": None, "currency": None, "source_url": MATCH, "quote": "Buy your tickets here for the La Liga match"},
        {"kind": "ticket_price", "value": "VIP from 2,350 EUR", "amount": 2350, "currency": "EUR", "source_url": MATCH, "quote": "From 2.350€"},
        {"kind": "kickoff_time", "value": "21:00", "amount": None, "currency": None, "source_url": RESELLER, "quote": "Kick-off 21:00 at the Camp Nou"},
        {"kind": "venue", "value": "Spotify Camp Nou", "amount": None, "currency": None, "source_url": MATCH, "quote": "Camp"},
        {"kind": "ticket_policy", "value": "Resale forbidden", "amount": None, "currency": None, "source_url": MATCH, "quote": "This sentence is not on the page."},
        {"kind": "weather", "value": "sunny", "amount": None, "currency": None, "source_url": MATCH, "quote": "sunny all day long"}],
        "unofficial_sources": ["StubHub"], "risks": ["Kickoff may move for TV."]}}
PAGE = {"url": MATCH + "/", "markdown": "[Buy your tickets here](https://www.fcbarcelona.com/t) for the La Liga match between "
        "FC Barcelona - Real Madrid, on Sun 25 Oct 2026, 20:00 GMT.\n**From 2.350€**"}

def test_parse_keeps_known_kinds_and_prices_only_on_price_facts():
    facts = facts_from_research(RESULT, "football")
    assert [f.kind for f in facts][-1] == "ticket_policy" and len(facts) == 7  # the unknown "weather" kind is dropped
    kickoff, price = facts[1], facts[3]
    assert kickoff.amount is None and kickoff.currency is None
    assert price.amount == 2350 and price.currency == "EUR"
    assert facts[0].official and not facts[4].official
    assert facts[0].title == "FC Barcelona - Real Madrid" and facts[0].observed_at == RESULT["retrieved_at"]

def test_quotes_are_verified_only_on_the_cited_page_or_its_excerpt():
    facts = facts_from_research(RESULT, "football")
    assert confirm_quotes(facts, [PAGE], RESULT["sources"]) == 4
    checks = {(f.kind, f.url): (f.verified, f.check) for f in facts}
    assert checks[("match_date", MATCH)] == (True, "quote found on the cited page")
    assert checks[("kickoff_time", MATCH)] == (True, "quote found in You.com's excerpt of the cited page")
    assert checks[("ticket_channel", MATCH)][0]  # a markdown link inside the quote does not break the match
    assert checks[("ticket_price", MATCH)][0]
    assert checks[("kickoff_time", RESELLER)] == (False, "schedule facts need an official page")
    assert checks[("venue", MATCH)] == (False, "quote too short to check")
    assert checks[("ticket_policy", MATCH)] == (False, "quote not found on the cited page")

def test_a_real_quote_that_does_not_state_the_value_is_not_verified():
    # Seen live: Research cited "All times in peninsular Spain time" for a 21:00 kickoff.
    result = dict(RESULT, content={"facts": [
        {"kind": "kickoff_time", "value": "21:00", "amount": None, "currency": None, "source_url": MATCH, "quote": "All times in peninsular Spain time"},
        {"kind": "match_date", "value": "2026-10-25", "amount": None, "currency": None, "source_url": MATCH, "quote": "on Sun 25 Oct 2026, 20:00 GMT"},
        {"kind": "ticket_price", "value": "VIP", "amount": 2550, "currency": "EUR", "source_url": MATCH, "quote": "From 2.350€"}]})
    page = dict(PAGE, markdown=PAGE["markdown"] + "\nAll times in peninsular Spain time")
    facts = facts_from_research(result, "football")
    assert confirm_quotes(facts, [page], RESULT["sources"]) == 1
    assert [(f.kind, f.verified, f.check) for f in facts] == [
        ("kickoff_time", False, "quote does not state the value"),
        ("match_date", True, "quote found on the cited page"),  # an ISO value still matches day and month in the quote
        ("ticket_price", False, "quote does not state the value")]

def test_apply_facts_fills_dates_from_verified_facts_and_adds_caveats():
    facts = facts_from_research(RESULT, "football")
    confirm_quotes(facts, [PAGE], RESULT["sources"])
    candidate = TripCandidate(title="T", destination="Destination to confirm from official event source", event="E", rationale="r")
    apply_facts(candidate, facts, RESULT["content"])
    assert candidate.dates == "Sun 25 Oct 2026"
    assert candidate.destination.startswith("Destination to confirm")  # the venue quote was too short to verify
    assert any("StubHub" in c for c in candidate.caveats) and any("Kickoff may move" in c for c in candidate.caveats)

def test_research_schema_fits_the_output_schema_subset():
    forbidden = {"format", "pattern", "minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength", "allOf", "not"}
    def walk(node):
        if isinstance(node, dict):
            assert not forbidden & set(node)
            if node.get("type") == "object":
                assert node["additionalProperties"] is False and sorted(node["required"]) == sorted(node["properties"])
            for value in node.values(): walk(value)
        elif isinstance(node, list):
            for value in node: walk(value)
    walk(RESEARCH_SCHEMA)
