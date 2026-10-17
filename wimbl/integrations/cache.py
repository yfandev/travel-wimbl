"""Append-only TTL cache for provider responses. Keys hash the endpoint and request body; never store credentials."""
import hashlib
import json
import time
from pathlib import Path

class ResponseCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._rows: dict[str, dict] | None = None

    @staticmethod
    def key(endpoint: str, body: dict) -> str:
        raw = endpoint + "\n" + json.dumps(body, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load(self) -> dict[str, dict]:
        if self._rows is None:
            self._rows = {}
            if self.path.exists():
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    try:
                        row = json.loads(line)
                        self._rows[row["key"]] = row
                    except (json.JSONDecodeError, KeyError): continue
        return self._rows

    def get(self, key: str, ttl_seconds: int) -> dict | None:
        row = self._load().get(key)
        return row if row and time.time() - row["stored_at"] <= ttl_seconds else None

    def put(self, key: str, endpoint: str, payload, retrieved_at: str) -> None:
        row = {"key": key, "endpoint": endpoint, "stored_at": time.time(), "retrieved_at": retrieved_at, "payload": payload}
        self._load()[key] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
