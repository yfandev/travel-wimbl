"""Single source of truth for model routing. Swap a model here, not in the controller or learning engine.

WIMBL runs NVIDIA Nemotron models served by Crusoe Managed Inference (serverless).
This module has no imports from wimbl so config.py can take its defaults from it.
"""

SUPER = "nvidia/Nemotron-3-Super-120B-A12B"
NANO = "nvidia/Nemotron-3-Nano-30B-A3B"
LIGHTNING = "nvidia/nemotron-3.5-lightning-30b-a3b"
OMNI = "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B"

# Context windows as served on Crusoe (plan for 262k on Super even though NVIDIA markets 1M).
CONTEXT_TOKENS = {SUPER: 262_144, NANO: 262_144, LIGHTNING: 1_000_000, OMNI: 262_144}

SUPER_ROLES = ("controller", "verifier", "learning")
CHILD_ROLES = ("tickets", "flights", "hotels", "transit", "price_watch", "coordination")

# Provisional: Nano vs Lightning has not been benchmarked yet. Pin the winner here and record why.
CHILD_MODEL = NANO

ROUTES = {**{r: SUPER for r in SUPER_ROLES}, **{r: CHILD_MODEL for r in CHILD_ROLES}, "image_check": OMNI}

def model_for(role: str) -> str:
    """Model ID to request for an agent role. CRUSOE_MODEL overrides the Super-tier roles only."""
    if role not in ROUTES:
        raise ValueError(f"Unknown agent role: {role!r}")
    if role in SUPER_ROLES:
        from wimbl.config import settings
        return settings.crusoe_model or ROUTES[role]
    return ROUTES[role]
