"""One JSONL record per model call (setup spec §6). Metadata only: never prompts, outputs, or credentials."""
import json
from datetime import datetime, timezone
from pathlib import Path
from wimbl.config import settings
from wimbl.integrations.models import SUPER

FIELDS = ("run_id", "agent_role", "model_id_requested", "model_id_returned", "version_tag", "prompt_version",
          "input_tokens", "output_tokens", "latency_ms", "cost_estimate_usd", "tool_calls", "status", "error", "timestamp")

# USD per 1M (input, output) tokens. Third-party estimate (ComputePrices), not Crusoe's pricing page; models without
# a known price get cost_estimate_usd = None rather than a guess.
PRICE_ESTIMATES = {SUPER: (0.30, 2.40)}

def estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    price = PRICE_ESTIMATES.get(model)
    if not price or input_tokens is None or output_tokens is None: return None
    return round((input_tokens * price[0] + output_tokens * price[1]) / 1_000_000, 6)

class RunLog:
    def __init__(self, path: str | None = None):
        self.path = Path(path or settings.wimbl_run_log_path)

    def write(self, **fields) -> dict:
        unknown = set(fields) - set(FIELDS) - {"attempts"}
        if unknown: raise ValueError(f"Unknown run record fields: {sorted(unknown)}")
        row = {k: fields.get(k) for k in FIELDS}
        row["attempts"] = fields.get("attempts", 1)
        row["version_tag"] = row["version_tag"] or settings.wimbl_version_tag
        row["timestamp"] = row["timestamp"] or datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def read(self, run_id: str | None = None) -> list[dict]:
        if not self.path.exists(): return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try: row = json.loads(line)
            except json.JSONDecodeError: continue
            if run_id is None or row.get("run_id") == run_id: rows.append(row)
        return rows
