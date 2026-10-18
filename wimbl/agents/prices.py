"""Package line items: match ticket, round-trip flight and hotel. Every amount is copied from a You.com Search snippet,
a page read with You.com Contents, or a quote-checked You.com Research fact, together with the sentence it came from.
Nothing is estimated or converted: a line with no published price says so and names the sources it checked."""
import asyncio
import re
from wimbl.agents.hierarchy import official_domain
from wimbl.config import settings
from wimbl.integrations.youcom import YouAPIError, YouSearch
from wimbl.schemas import Fact, PriceLine, PriceTotal, TripCandidate, TripRequest

ADVERTISED = "advertised price, not live inventory"
PAGES_PER_LINE = 3  # three lines x three pages stays inside one Contents call (10 URLs)
_CURRENCIES = {"US$": "USD", "$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}
_CUR = r"US\$|\$|USD|€|EUR|£|GBP"
_NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
PRICE = re.compile(rf"(?P<c1>{_CUR})\s?(?P<n1>{_NUM})(?![\d])|(?<![\d.,])(?P<n2>{_NUM})\s?(?P<c2>{_CUR})")
# keyword: the sentence must name the item; avoid: a price nearer to this phrase belongs to something else;
# bounds drop numbers that are not a price for this item (years, ratings, totals for a whole stay).
ITEMS = {
    "tickets": {"keyword": r"ticket|seat|price|from", "avoid": None, "bounds": (10, 5000), "unit": "per ticket"},
    "flight": {"keyword": r"round[- ]?trip|roundtrip|return", "avoid": r"one[- ]?way", "bounds": (100, 10000), "unit": "round trip"},
    "hotel": {"keyword": r"per night|a night|/\s?night|nightly", "avoid": r"\btotal\b(?! per night)", "bounds": (20, 2000), "unit": "per night"},
}
NOT_MATCH_TICKETS = re.compile(r"tour|museum|experience|immersive", re.I)  # stadium-tour prices are not match tickets

def parse_amount(text: str) -> float:
    """'2.350' and '1,092' are thousands; '152.47' and '152,47' are decimals."""
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", text): return float(re.sub(r"[.,]", "", text))
    if m := re.fullmatch(r"(\d{1,3}(?:[.,]\d{3})*)[.,](\d{1,2})", text): return float(re.sub(r"[.,]", "", m[1]) + "." + m[2])
    return float(text)

def clean(text: str) -> str:
    """Page markdown as a reader sees it: link text without its target, no table pipes, emphasis or escapes."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<br\s*/?>|[|*#`>\\]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def segments(text: str):
    for line in (text or "").splitlines():
        yield from (s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", clean(line)) if s)

def find_price(text: str, item: str) -> tuple[float, str, str] | None:
    """(amount, currency, quote) for the first sentence that names the item and states a price; the price closest to the
    item's keyword wins, so '$249 one-way and $509 round trip' reads as 509."""
    spec = ITEMS[item]
    lo, hi = spec["bounds"]
    for seg in segments(text):
        if item == "tickets" and NOT_MATCH_TICKETS.search(seg): continue
        keys = [m.start() for m in re.finditer(spec["keyword"], seg, re.I)]
        if not keys: continue
        avoid = [m.start() for m in re.finditer(spec["avoid"], seg, re.I)] if spec["avoid"] else []
        best = None
        for m in PRICE.finditer(seg):
            amount = parse_amount(m["n1"] or m["n2"])
            if not lo <= amount <= hi: continue
            near = min(abs(m.start() - k) for k in keys)
            if avoid and min(abs(m.start() - a) for a in avoid) < near: continue
            if best is None or near < best[0]: best = (near, amount, _CURRENCIES[m["c1"] or m["c2"]], m.start())
        if best:
            start = max(0, best[3] - 160)
            quote = ("…" if start else "") + seg[start:best[3] + 80] + ("…" if best[3] + 80 < len(seg) else "")
            return best[1], best[2], quote
    return None

def _advertised(item: str, label: str, quantity: int, amount: float, currency: str, quote: str, row: dict, via: str,
                group: str) -> PriceLine:
    return PriceLine(item=item, label=label, status="advertised", amount=amount, currency=currency, quantity=quantity,
        unit=ITEMS[item]["unit"], subtotal=round(amount * quantity, 2), url=row["url"], title=row.get("title") or "",
        quote=quote, observed_at=row.get("retrieved_at"), via=via, official=bool(official_domain(row["url"], group)))

def _from_rows(item, label, quantity, rows, group, field, via) -> PriceLine | None:
    for row in rows:
        if hit := find_price(row.get(field) or "", item): return _advertised(item, label, quantity, *hit, row, via, group)
    return None

def _not_found(item: str, label: str, quantity: int, rows: list[dict], note: str, group: str) -> PriceLine:
    first = rows[0] if rows else {}
    return PriceLine(item=item, label=label, status="not_published" if rows else "not_searched", quantity=quantity,
        unit=ITEMS[item]["unit"], url=first.get("url"), title=first.get("title") or "", observed_at=first.get("retrieved_at"),
        via="", official=bool(first.get("url") and official_domain(first["url"], group)), note=note,
        sources_checked=[r["url"] for r in rows])

def plan_lines(request: TripRequest, candidate: TripCandidate) -> list[tuple[str, str, int, str | None]]:
    """(item, label, quantity, search query or None for tickets). Hotel nights assume one night fewer than trip days."""
    city = candidate.destination.split(",")[0].strip()
    when = f" {request.dates}" if request.dates else ""
    known = "to confirm" not in candidate.destination.lower()
    nights = max(request.days - 1, 1)
    return [("tickets", "Match ticket", 1, None),
            ("flight", f"Round-trip flight, {request.origin} to {city}" if known else "Round-trip flight", 1,
             f"round trip flights {request.origin} to {city}{when} fares" if known else None),
            ("hotel", f"Hotel in {city}, {nights} night{'s' * (nights != 1)}" if known else "Hotel", nights,
             f"hotels in {city}{when} price per night" if known else None)]

async def price_lines(you: YouSearch, request: TripRequest, candidate: TripCandidate, group: str) -> list[PriceLine]:
    """Snippets first; the top pages of a line whose snippets name no price are read with one You.com Contents call."""
    plan = plan_lines(request, candidate)
    if not settings.you_api_key:
        return [_not_found(i, label, q, [], "Demo mode: prices are not looked up without YOU_API_KEY.", group)
                for i, label, q, _ in plan]
    tickets = [{"title": e.title, "url": e.url, "snippet": e.snippet, "retrieved_at": e.retrieved_at} for e in candidate.evidence
               if official_domain(e.url, group) and not NOT_MATCH_TICKETS.search(e.url + " " + e.title)]
    queries = {item: query for item, _, _, query in plan if query}
    found = await asyncio.gather(*(you.search(q, count=6) for q in queries.values()), return_exceptions=True)
    rows = {"tickets": tickets, **{item: r if isinstance(r, list) else [] for item, r in zip(queries, found)}}
    failed = {item for item, r in zip(queries, found) if isinstance(r, Exception)}
    lines = {item: _from_rows(item, label, q, rows[item], group, "snippet", "You.com Search snippet") for item, label, q, _ in plan}
    want = [r["url"] for item, _, _, _ in plan if lines[item] is None for r in rows[item][:PAGES_PER_LINE]]
    try: pages = {p["url"].rstrip("/"): p for p in await you.contents(want)} if want else {}
    except YouAPIError: pages, failed = {}, failed | {"contents"}
    out = []
    for item, label, q, query in plan:
        if line := lines[item]:
            out.append(line); continue
        read = [dict(r, markdown=(pages.get(r["url"].rstrip("/")) or {}).get("markdown")) for r in rows[item][:PAGES_PER_LINE]]
        line = _from_rows(item, label, q, read, group, "markdown", "You.com Contents (page text)")
        if line is None:
            checked = rows[item]
            pages_read = sum(bool(r["markdown"]) for r in read)
            note = ("You.com Search failed for this line." if item in failed else
                    "Destination not confirmed, so this line was not searched." if query is None and item != "tickets" else
                    "No official match-ticket page in the evidence." if not checked else
                    f"No price in the search snippets of {len(checked)} source(s) or the page text of {pages_read} "
                    + ("official page(s)." if item == "tickets" else "page(s).")
                    + (" Pages could not be read with You.com Contents." if "contents" in failed else ""))
            line = _not_found(item, label, q, checked, note, group)
        out.append(line)
    return out

def summary(lines: list[PriceLine], total: PriceTotal) -> str:
    if all(l.status == "not_searched" and l.note.startswith("Demo mode") for l in lines): return "Demo mode: no price lookups."
    priced = [f"{l.item} via {l.via}" for l in lines if l.status == "advertised"]
    amount = f"; sum of priced lines {total.amount:,.2f} {total.currency}" if total.amount is not None else ""
    other = "".join(f" + {v:,.2f} {c} (not converted)" for c, v in total.other_currencies.items())
    return (f"Prices: {len(priced)} of {len(lines)} line item(s) have an advertised price" + (f" ({', '.join(priced)})" if priced else "")
            + amount + other + "; advertised prices, not live inventory.")

def apply_ticket_fact(lines: list[PriceLine], facts: list[Fact], group: str) -> None:
    """A ticket price that You.com Research found and code confirmed on an official page fills an unpriced ticket line."""
    i = next((i for i, l in enumerate(lines) if l.item == "tickets" and l.status != "advertised"), None)
    fact = next((f for f in facts if f.kind == "ticket_price" and f.verified and f.official and f.amount and f.currency), None)
    if i is None or fact is None: return
    old = lines[i]
    lines[i] = PriceLine(item="tickets", label=old.label, status="advertised", amount=fact.amount, currency=fact.currency.upper()[:3],
        quantity=old.quantity, unit=ITEMS["tickets"]["unit"], subtotal=round(fact.amount * old.quantity, 2), url=fact.url,
        title=fact.title, quote=fact.quote, observed_at=fact.observed_at, via=f"You.com Research ({fact.check})", official=True)

def price_total(lines: list[PriceLine], currency: str) -> PriceTotal:
    """Sum of priced line items in the trip currency. Other currencies are listed, never converted."""
    currency = currency.upper()
    same = [l for l in lines if l.subtotal is not None and l.currency == currency]
    other: dict[str, float] = {}
    for l in lines:
        if l.subtotal is not None and l.currency != currency: other[l.currency] = round(other.get(l.currency, 0) + l.subtotal, 2)
    return PriceTotal(currency=currency, amount=round(sum(l.subtotal for l in same), 2) if same else None, priced=len(same),
                      lines=len(lines), complete=bool(lines) and len(same) == len(lines), other_currencies=other, label=ADVERTISED)
