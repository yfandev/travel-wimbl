"""Event and ticket facts from You.com Research. Each fact names its page and a verbatim quote; code, not a model,
checks the quote on that page before the fact counts as verified."""
import re
import unicodedata
from wimbl.agents.hierarchy import official_domain
from wimbl.schemas import Fact, TripCandidate, TripRequest

FACT_KINDS = ("match_date", "kickoff_time", "opponent", "competition", "venue", "ticket_channel", "resale_channel",
              "sale_date", "ticket_price", "ticket_policy")
OFFICIAL_ONLY = {"match_date", "kickoff_time"}  # schedule facts count only when an official page states them
MIN_QUOTE_CHARS = 8
MAX_FACTS = 30
_NULLABLE = {"anyOf": [{"type": "string"}, {"type": "null"}]}
# Research output_schema subset: every property listed in required, additionalProperties false, no min/max/format/pattern.
RESEARCH_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["facts", "unofficial_sources", "risks"],
    "properties": {
        "facts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["kind", "value", "amount", "currency", "source_url", "quote"],
            "properties": {"kind": {"type": "string", "enum": list(FACT_KINDS)}, "value": {"type": "string"},
                "amount": {"anyOf": [{"type": "number"}, {"type": "null"}]}, "currency": _NULLABLE,
                "source_url": {"type": "string"}, "quote": {"type": "string"}}}},
        "unofficial_sources": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}}}}
_PUNCT = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "−": "-",
                        **{chr(c): "-" for c in range(0x2010, 0x2016)}, **{c: None for c in "­​‌‍﻿"}})
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")

def research_query(request: TripRequest) -> str:
    when = f" Preferred dates: {request.dates}." if request.dates else ""
    return (f"Traveler goal: {request.interest}.{when} Find the next football match that fits this goal and that a traveler "
            "could attend, and how to buy tickets for it. Report facts: match date, kickoff time (local, with time zone), "
            "opponent, competition, venue, the official ticket channel, the official resale channel, ticket sale dates, "
            "published ticket prices with currency, and ticket policies. For every fact give source_url and quote: an exact "
            "sentence or phrase copied word for word from that page. List third-party ticket resellers you saw in "
            "unofficial_sources. Prices are published prices, not live availability.")

def url_key(url: str | None) -> str: return (url or "").rstrip("/").lower()

def normalize(text: str | None) -> str:
    """Case, width, curly quotes, dashes, markdown link targets and marks, and whitespace do not count in a quote match."""
    text = unicodedata.normalize("NFKC", text or "").casefold().translate(_PUNCT)
    text = re.sub(r"\]\([^)]*\)", " ", text)
    return re.sub(r"\s+", " ", re.sub(r"[\[\]*_#>`|\\]", " ", text)).strip()

def facts_from_research(result: dict, group: str) -> list[Fact]:
    titles = {url_key(s["url"]): s.get("title") or "" for s in result["sources"]}
    facts = []
    for row in (result["content"].get("facts") or [])[:MAX_FACTS]:
        if not isinstance(row, dict) or row.get("kind") not in FACT_KINDS or not row.get("value") or not row.get("source_url"):
            continue
        url, price = str(row["source_url"]), row["kind"] == "ticket_price"
        amount = row.get("amount") if price and isinstance(row.get("amount"), (int, float)) and not isinstance(row.get("amount"), bool) else None
        facts.append(Fact(kind=row["kind"], value=str(row["value"])[:300], amount=amount,
            currency=str(row["currency"])[:12] if price and row.get("currency") else None, url=url,
            title=titles.get(url_key(url), ""), quote=str(row.get("quote") or "")[:500], observed_at=result["retrieved_at"],
            official=bool(official_domain(url, group)), cache_hit=result["cache_hit"]))
    return facts

def states_value(f: Fact, quote: str) -> bool:
    """A real quote can still carry a made-up value, so times, dates, prices and names must appear in the quote itself."""
    value = normalize(f.value)
    if f.kind == "kickoff_time":
        return any(re.search(rf"\b0?{int(h)}\s?[:.h]\s?{m}\b", quote) for h, m in re.findall(r"\b(\d{1,2})[:.h](\d{2})\b", value))
    if f.kind == "match_date":
        if iso := re.search(r"\b\d{4}-(\d{2})-(\d{2})\b", value):
            pairs = [(iso[2], _MONTHS[int(iso[1]) - 1])] if 1 <= int(iso[1]) <= 12 else []
        else:  # "25 Oct 2026" or "October 25, 2026"; weekday names are skipped because they are not months
            pairs = ([(m[1], m[2]) for m in re.finditer(r"\b(\d{1,2})\s+([a-z]{3})", value)]
                     + [(m[2], m[1]) for m in re.finditer(r"\b([a-z]{3})[a-z]*\.?\s+(\d{1,2})\b", value)])
        day, month = next(((str(int(d)), mo) for d, mo in pairs if mo in _MONTHS), (None, None))
        return bool(day) and bool(re.search(rf"\b0?{day}\b", quote)) and month in quote
    if f.kind == "ticket_price":
        return f.amount is not None and str(int(f.amount)) in re.sub(r"(?<=\d)[.,\s'](?=\d)", "", quote)
    if f.kind in ("opponent", "competition", "venue"):
        return value in quote or all(w in quote for w in re.findall(r"[^\W\d_]{4,}", value))
    return True

ON_PAGE = "quote found on the cited page"
IN_EXCERPT = "quote found in You.com's excerpt of the cited page"

def confirm_quotes(facts: list[Fact], pages: list[dict], sources: list[dict]) -> int:
    """Set verified only when the quote states the value and is either on the cited page as re-read by You.com Contents
    (ON_PAGE) or in one of the excerpts You.com Research returned for that URL (IN_EXCERPT). The excerpt counts because
    JavaScript-rendered pages, such as club schedules, often re-read as app chrome. Schedule facts also need an official
    page. Returns the number verified."""
    markdown = {url_key(p.get("url")): normalize(p.get("markdown")) for p in pages if p.get("markdown")}
    excerpts = {url_key(s["url"]): [normalize(str(x)) for x in s.get("snippets") or []] for s in sources}
    for f in facts:
        quote, key = normalize(f.quote), url_key(f.url)
        if len(quote) < MIN_QUOTE_CHARS: f.check = "quote too short to check"
        elif f.kind in OFFICIAL_ONLY and not f.official: f.check = "schedule facts need an official page"
        elif not states_value(f, quote): f.check = "quote does not state the value"
        elif quote in markdown.get(key, ""): f.verified, f.check = True, ON_PAGE
        elif any(quote in x for x in excerpts.get(key, [])): f.verified, f.check = True, IN_EXCERPT
        else: f.check = "quote not found on the cited page" if key in markdown else "cited page could not be read"
    return sum(f.verified for f in facts)

def apply_facts(candidate: TripCandidate, facts: list[Fact], content: dict) -> None:
    """Fill gaps on the candidate from verified facts only, and carry Research's reseller and risk notes as caveats."""
    candidate.facts = facts
    first = {}
    for f in facts:
        if f.verified: first.setdefault(f.kind, f.value)
    if not candidate.dates and first.get("match_date"): candidate.dates = first["match_date"]
    if "to confirm" in candidate.destination.lower() and first.get("venue"): candidate.destination = first["venue"]
    resellers = [str(u)[:80] for u in content.get("unofficial_sources") or []][:8]
    if resellers: candidate.caveats.append("Third-party resellers seen (not official channels): " + ", ".join(resellers))
    candidate.caveats += [f"Research note: {str(r)[:220]}" for r in (content.get("risks") or [])[:3]]
