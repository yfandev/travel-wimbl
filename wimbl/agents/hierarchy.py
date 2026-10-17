"""Explicit agent family. Child learnings are proposals, not automatically trusted facts."""
from urllib.parse import urlparse

AGENT_FAMILY = {
    "global": {"parent": None, "children": ["sports"]},
    "sports": {"parent": "global", "children": ["football"]},
    "football": {"parent": "sports", "children": ["tickets", "flights", "hotels", "transit", "price_watch", "coordination"]},
}

def family_for(interest: str) -> str:
    """WIMBL is football-only, so every goal belongs to the football family, including goals with no football keyword
    (e.g. "see Barcelona in March")."""
    return "football"

def inheritance_chain(group: str) -> list[str]:
    chain, current = [], group
    while current:
        chain.append(current)
        current = AGENT_FAMILY.get(current, {}).get("parent")
    return list(reversed(chain))

# Club sites with a fixed home stadium. League and confederation sites have no single destination.
EVENT_VENUES = {
    "fcbarcelona.com": "Barcelona, Spain", "realmadrid.com": "Madrid, Spain", "atleticodemadrid.com": "Madrid, Spain",
    "arsenal.com": "London, United Kingdom", "chelseafc.com": "London, United Kingdom",
    "tottenhamhotspur.com": "London, United Kingdom", "liverpoolfc.com": "Liverpool, United Kingdom",
    "manutd.com": "Manchester, United Kingdom", "mancity.com": "Manchester, United Kingdom",
    "fcbayern.com": "Munich, Germany", "bvb.de": "Dortmund, Germany", "juventus.com": "Turin, Italy",
    "acmilan.com": "Milan, Italy", "inter.it": "Milan, Italy", "psg.fr": "Paris, France",
}
# One list per family: steers You.com search (boost_domains) and drives the verifier's official-source check.
OFFICIAL_DOMAINS = {
    "football": ["uefa.com", "fifa.com", "premierleague.com", "laliga.com", "bundesliga.com", "legaseriea.it",
                 "ligue1.com", *EVENT_VENUES],
}
OFFICIAL_DOMAINS["sports"] = sorted({d for ds in OFFICIAL_DOMAINS.values() for d in ds} | {"olympics.com"})

def official_domains(group: str) -> list[str]:
    return OFFICIAL_DOMAINS.get(group, OFFICIAL_DOMAINS["sports"])

def official_domain(url: str, group: str = "sports") -> str | None:
    """The official domain that the URL's hostname belongs to, or None. Hostname match, not substring."""
    host = (urlparse(url).hostname or "").lower()
    return next((d for d in official_domains(group) if host == d or host.endswith("." + d)), None)
