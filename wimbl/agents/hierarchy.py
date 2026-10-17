"""Explicit agent family. Child learnings are proposals, not automatically trusted facts."""
from urllib.parse import urlparse

AGENT_FAMILY = {
    "global": {"parent": None, "children": ["sports"]},
    "sports": {"parent": "global", "children": ["tennis", "football"]},
    "tennis": {"parent": "sports", "children": ["event_discovery", "trip_planner", "verifier"]},
    "football": {"parent": "sports", "children": ["event_discovery", "trip_planner", "verifier"]},
}

def family_for(interest: str) -> str:
    value = interest.lower()
    if any(k in value for k in ("football", "soccer", "nfl")): return "football"
    if any(k in value for k in ("tennis", "wimbledon", "atp", "wta")): return "tennis"
    return "sports"

def inheritance_chain(group: str) -> list[str]:
    chain, current = [], group
    while current:
        chain.append(current)
        current = AGENT_FAMILY.get(current, {}).get("parent")
    return list(reversed(chain))

# One list per family: steers You.com search (boost_domains) and drives the verifier's official-source check.
OFFICIAL_DOMAINS = {
    "tennis": ["wimbledon.com", "atptour.com", "wtatennis.com", "usopen.org", "rolandgarros.com", "ausopen.com"],
    "football": ["uefa.com", "fifa.com", "premierleague.com", "nfl.com"],
}
OFFICIAL_DOMAINS["sports"] = sorted({d for ds in OFFICIAL_DOMAINS.values() for d in ds} | {"olympics.com"})
# Event sites with a fixed venue city. Tour and league sites have no single destination.
EVENT_VENUES = {"wimbledon.com": "London, United Kingdom", "rolandgarros.com": "Paris, France",
                "usopen.org": "New York, United States", "ausopen.com": "Melbourne, Australia"}

def official_domains(group: str) -> list[str]:
    return OFFICIAL_DOMAINS.get(group, OFFICIAL_DOMAINS["sports"])

def official_domain(url: str, group: str = "sports") -> str | None:
    """The official domain that the URL's hostname belongs to, or None. Hostname match, not substring."""
    host = (urlparse(url).hostname or "").lower()
    return next((d for d in official_domains(group) if host == d or host.endswith("." + d)), None)
