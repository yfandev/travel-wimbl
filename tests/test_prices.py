import asyncio
import json
import httpx
from wimbl.agents.prices import apply_ticket_fact, find_price, parse_amount, price_lines, price_total
from wimbl.agents.verifier import IndependentVerifier
from wimbl.config import settings
from wimbl.controller import TripController
from wimbl.integrations.cache import ResponseCache
from wimbl.integrations.youcom import YouSearch
from wimbl.memory import SharedMemory
from wimbl.schemas import Evidence, Fact, PriceLine, TripCandidate, TripRequest

OFFICIAL = "https://www.fcbarcelona.com/en/tickets/football"
FLIGHT = "https://www.expedia.com/lp/flights/sfo/bcn/san-francisco-to-barcelona"
HOTEL = "https://www.kayak.com/Barcelona-Hotels_Camp-Nou.L4706.22567.hotel.ksp"
HOTEL_PAGE = "https://www.travelocity.com/Camp-Nou-Hotels"
NOW = "2026-10-17T22:00:00+00:00"

def test_amounts_and_quotes_come_from_the_text():
    assert parse_amount("2.350") == 2350 and parse_amount("1,092") == 1092 and parse_amount("152.47") == 152.47
    assert parse_amount("152,47") == 152.47
    snippet = "Book cheap Flights from San Francisco (SFO) to Barcelona (BCN) start at $249 for one-way and $509 for round trip."
    amount, currency, quote = find_price(snippet, "flight")
    assert (amount, currency) == (509, "USD") and "$509 for round trip" in quote
    assert find_price("3-star hotel rooms have been found for as low as $49 per night", "hotel")[:2] == (49, "USD")
    assert find_price("**From 2.350€**", "tickets")[:2] == (2350, "EUR")
    assert find_price("[Camp Nou Experience tickets](https://x) from €28", "tickets") is None  # stadium tour, not a match
    assert find_price("Flights to Barcelona from $329. Fly from San Francisco on United.", "flight") is None  # no round trip
    assert find_price("Season 2026 round trip guide", "flight") is None  # a year is not a price

def test_total_is_the_sum_of_priced_lines_and_never_converts():
    lines = [PriceLine(item="flight", label="f", status="advertised", amount=509, currency="USD", subtotal=509, url=FLIGHT, quote="q", observed_at=NOW),
             PriceLine(item="hotel", label="h", status="advertised", amount=49, currency="USD", quantity=3, subtotal=147, url=HOTEL, quote="q", observed_at=NOW),
             PriceLine(item="tickets", label="t", status="advertised", amount=195, currency="EUR", subtotal=195, url=OFFICIAL, quote="q", observed_at=NOW)]
    total = price_total(lines, "usd")
    assert (total.amount, total.priced, total.lines, total.complete) == (656, 2, 3, False)
    assert total.other_currencies == {"EUR": 195} and total.label == "advertised price, not live inventory"
    assert price_total(lines[:2], "USD").complete

def test_a_confirmed_official_ticket_fact_fills_an_unpriced_ticket_line():
    lines = [PriceLine(item="tickets", label="Match ticket", status="not_published", url=OFFICIAL)]
    unconfirmed = Fact(kind="ticket_price", value="From €195", amount=195, currency="EUR", url="https://www.barcelona.com/x", quote="From €195", observed_at=NOW)
    apply_ticket_fact(lines, [unconfirmed], "football")
    assert lines[0].status == "not_published"  # unverified and unofficial: not a price
    confirmed = Fact(kind="ticket_price", value="From 2.350€", amount=2350, currency="EUR", url=OFFICIAL, quote="From 2.350€",
                     observed_at=NOW, official=True, verified=True, check="quote found on the cited page")
    apply_ticket_fact(lines, [confirmed], "football")
    assert (lines[0].status, lines[0].subtotal, lines[0].url, lines[0].observed_at) == ("advertised", 2350, OFFICIAL, NOW)

def you(tmp_path, pages=None):
    """Search answers by query: flight snippets carry a price; hotel snippets do not, so the hotel line needs Contents."""
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append((str(request.url), body))
        if str(request.url) == settings.you_contents_endpoint:
            return httpx.Response(200, json=[{"url": u, "markdown": (pages or {}).get(u)} for u in body["urls"]])
        q = body["query"]
        if q.startswith("round trip flights"):
            web = [{"url": FLIGHT, "title": "Cheap flights SFO to BCN", "description": "Flights start at $249 for one-way and $509 for round trip."}]
        elif q.startswith("hotels in"):
            web = [{"url": HOTEL_PAGE, "title": "Hotels near Camp Nou", "description": "The closest hotels near Camp Nou."}]
        else:
            web = [{"url": OFFICIAL, "title": "FC Barcelona tickets", "description": "Buy your tickets here to see FC Barcelona."}]
        return httpx.Response(200, json={"results": {"web": web}})
    async def no_sleep(_): pass
    return YouSearch(transport=httpx.MockTransport(handler), cache=ResponseCache(tmp_path / "c.jsonl"), sleep=no_sleep), calls

def candidate():
    return TripCandidate(title="t", destination="Barcelona, Spain", event="FC Barcelona tickets", rationale="r",
        evidence=[Evidence(title="FC Barcelona tickets", url=OFFICIAL, snippet="Buy your tickets here.", retrieved_at=NOW)])

def test_lines_use_snippets_then_page_text_and_say_when_no_price_is_published(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "test-key")
    search, calls = you(tmp_path, pages={HOTEL_PAGE: "| Hotel Les Corts | $78 nightly |\nThe price is $110 total per night"})
    lines = asyncio.run(price_lines(search, TripRequest(interest="FC Barcelona", days=4), candidate(), "football"))
    tickets, flight, hotel = lines
    assert (flight.status, flight.amount, flight.via, flight.url) == ("advertised", 509, "You.com Search snippet", FLIGHT)
    assert (hotel.status, hotel.amount, hotel.quantity, hotel.subtotal) == ("advertised", 78, 3, 234)
    assert hotel.via == "You.com Contents (page text)" and "$78 nightly" in hotel.quote and hotel.observed_at
    assert tickets.status == "not_published" and tickets.url == OFFICIAL and tickets.official and tickets.amount is None
    assert "official page" in tickets.note and tickets.sources_checked == [OFFICIAL]
    contents = [b for u, b in calls if u == settings.you_contents_endpoint]
    assert len(contents) == 1 and FLIGHT not in contents[0]["urls"]  # a priced snippet needs no page read

def test_demo_mode_makes_no_price_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "")
    search, calls = you(tmp_path)
    lines = asyncio.run(price_lines(search, TripRequest(interest="FC Barcelona"), candidate(), "football"))
    assert not calls and {l.status for l in lines} == {"not_searched"} and all(l.amount is None for l in lines)

def test_controller_sets_a_total_only_when_every_line_is_priced(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "you_api_key", "test-key")
    monkeypatch.setattr(settings, "wimbl_demo_mode", False)
    monkeypatch.setattr(settings, "wimbl_research_facts", False)
    search, _ = you(tmp_path, pages={HOTEL_PAGE: "Rooms from $78 nightly"})
    result = asyncio.run(TripController(you=search, memory=SharedMemory(str(tmp_path / "m.jsonl"))).run(TripRequest(interest="FC Barcelona")))
    c = result.candidates[0]
    assert c.price_total.amount == 509 + 78 * 3 and not c.price_total.complete and c.estimated_total is None
    codes = {f.code: f.message for f in result.findings}
    assert "Only 2 of 3 line items" in codes["PRICE_UNCONFIRMED"] and "PRICES_ADVERTISED_NOT_LIVE" in codes
    assert any(s.startswith("Prices: 2 of 3 line item(s)") and "743.00 USD" in s for s in result.steps)

def test_verifier_rejects_a_price_without_its_source_and_a_wrong_total():
    c = candidate()
    c.line_items = [PriceLine(item="flight", label="f", status="advertised", amount=509, currency="USD", subtotal=509)]
    c.price_total = price_total(c.line_items, "USD")
    c.price_total.amount = 600
    codes = {f.code for f in IndependentVerifier().verify(TripRequest(interest="FC Barcelona"), c)}
    assert {"PRICE_WITHOUT_SOURCE", "TOTAL_MISMATCH"} <= codes
