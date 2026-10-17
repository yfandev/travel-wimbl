"""The agent family as data: who each agent is, which model serves it, and which memory scopes it inherits from.

Scopes run from most general to most specific: global → sports → football → football.<role>, plus "user" for
traveler-origin preferences. A lesson in a scope reaches every agent whose lineage includes that scope.
"""
from dataclasses import dataclass
from wimbl.agents.hierarchy import AGENT_FAMILY, inheritance_chain
from wimbl.integrations.models import CHILD_ROLES, SUPER_ROLES, model_for

FAMILY_SCOPES = tuple(AGENT_FAMILY)  # global, sports, football
USER_SCOPE = "user"

@dataclass(frozen=True)
class AgentSpec:
    role: str
    kind: str  # "family" (Super-tier: controller, verifier, learning) or "child" (trip specialists)
    model: str

REGISTRY = {**{r: AgentSpec(r, "family", model_for(r)) for r in SUPER_ROLES},
            **{r: AgentSpec(r, "child", model_for(r)) for r in CHILD_ROLES}}

def spec(agent_role: str) -> AgentSpec:
    if agent_role not in REGISTRY:
        raise ValueError(f"Unknown agent role {agent_role!r}; known roles: {sorted(REGISTRY)}")
    return REGISTRY[agent_role]

def role_scope(family: str, agent_role: str) -> str:
    return f"{family}.{agent_role}"

def lineage(agent_role: str, family: str) -> list[str]:
    """Scopes an agent inherits from, general to specific, ending with its own role scope."""
    spec(agent_role)
    if family not in AGENT_FAMILY:
        raise ValueError(f"Unknown family scope {family!r}; known: {list(FAMILY_SCOPES)}")
    return [*inheritance_chain(family), role_scope(family, agent_role)]

def valid_scope(scope: str) -> bool:
    if scope in FAMILY_SCOPES or scope == USER_SCOPE: return True
    family, _, role = scope.partition(".")
    return family in FAMILY_SCOPES and role in REGISTRY

def parent_scope(scope: str) -> str | None:
    """The scope a proven lesson is taught up to: football.tickets → football → sports → global."""
    if "." in scope: return scope.partition(".")[0]
    return AGENT_FAMILY.get(scope, {}).get("parent")
