"""Explicit agent family. Child learnings are proposals, not automatically trusted facts."""
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
