import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from wimbl.config import settings

SCOPES = {"global", "sports", "football", "user"}

class SharedMemory:
    """Append-only memory with provenance. Do not store secrets or private personal details."""
    def __init__(self, path: str | None = None):
        self.path = Path(path or settings.wimbl_memory_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, *, scope: str, lesson: str, source: str, confidence: float = 0.5,
            validated: bool = False, tags: list[str] | None = None) -> dict:
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {sorted(SCOPES)}")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        row = {"id": str(uuid4()), "scope": scope, "lesson": lesson[:2000], "source": source[:500],
               "confidence": confidence, "validated": validated, "tags": tags or [],
               "created_at": datetime.now(timezone.utc).isoformat()}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def list(self, scope: str | None = None, limit: int = 100) -> list[dict]:
        if not self.path.exists(): return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if scope is None or row.get("scope") == scope: rows.append(row)
            except json.JSONDecodeError: continue
        return rows[-max(1, min(limit, 500)):][::-1]
