"""Shared Brain: the family lesson registry (SQLite).

Agents read with get_inherited_lessons() before working and write with propose_lesson() after. The write path keeps
memory current (expiry, recency), lean (merge near-duplicates, per-scope cap) and conflict-free (one active lesson per
scope+topic; user-origin preferences beat internet-derived lessons; contradictions are quarantined until resolved).
Every decision is appended to an audit table.
"""
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field, ValidationError
from wimbl.agents import registry
from wimbl.config import settings
from wimbl.memory.lessons import (PROMPT_HEADER, TTL_DAYS, Lesson, LessonProposal, estimate_tokens, expiry, guard,
                                  influence, now_utc, render, similarity)

DUPLICATE_SIMILARITY = 0.75

class ProposalResult(BaseModel):
    status: Literal["created", "merged", "superseded", "conflict", "rejected"]
    lesson_id: str | None = None
    reason: str = ""
    conflicts_with: list[str] = Field(default_factory=list)
    archived: list[str] = Field(default_factory=list)

class InheritedLesson(BaseModel):
    lesson_id: str
    lesson: str
    topic: str
    scope: str
    from_agent: str
    source_type: str
    evaluation_status: str
    confidence: float
    influence: float
    evidence_urls: list[str]
    version_introduced: int

class InheritedLessons(BaseModel):
    agent_role: str
    scope: str
    lineage: list[str]
    scope_versions: dict[str, int]
    lessons: list[InheritedLesson]
    prompt_block: str
    tokens_used: int
    token_budget: int
    omitted: int = Field(description="Eligible lessons left out to fit the token budget.")
    generated_at: str

class LessonStore:
    def __init__(self, path: str | None = None, per_scope_cap: int | None = None):
        self.path = Path(path or settings.wimbl_lessons_db)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cap = per_scope_cap or settings.wimbl_lessons_per_scope
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS lessons (lesson_id TEXT PRIMARY KEY, scope TEXT, topic TEXT, status TEXT, data TEXT);
            CREATE INDEX IF NOT EXISTS lessons_scope ON lessons(scope, status);
            CREATE TABLE IF NOT EXISTS scope_versions (scope TEXT PRIMARY KEY, version INTEGER);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, kind TEXT, lesson_id TEXT, detail TEXT);
        """)

    # --- storage helpers -------------------------------------------------------------------------------------
    def _save(self, l: Lesson) -> None:
        self._db.execute("INSERT OR REPLACE INTO lessons VALUES (?, ?, ?, ?, ?)",
                         (l.lesson_id, l.scope, l.topic, l.status, l.model_dump_json()))

    def _event(self, kind: str, lesson_id: str | None, **detail) -> None:
        self._db.execute("INSERT INTO events (at, kind, lesson_id, detail) VALUES (?, ?, ?, ?)",
                         (now_utc().isoformat(), kind, lesson_id, json.dumps(detail, ensure_ascii=False)))

    def _query(self, sql: str, args: tuple = ()) -> list[Lesson]:
        return [Lesson.model_validate_json(row[0]) for row in self._db.execute(sql, args)]

    def get(self, lesson_id: str) -> Lesson | None:
        rows = self._query("SELECT data FROM lessons WHERE lesson_id = ?", (lesson_id,))
        return rows[0] if rows else None

    def active(self, scopes: list[str]) -> list[Lesson]:
        marks = ",".join("?" * len(scopes))
        return self._query(f"SELECT data FROM lessons WHERE status = 'active' AND scope IN ({marks})", tuple(scopes))

    def all(self, scope: str | None = None) -> list[Lesson]:
        if scope: return self._query("SELECT data FROM lessons WHERE scope = ? ORDER BY rowid", (scope,))
        return self._query("SELECT data FROM lessons ORDER BY rowid")

    def events(self, lesson_id: str | None = None) -> list[dict]:
        sql, args = "SELECT at, kind, lesson_id, detail FROM events", ()
        if lesson_id: sql, args = sql + " WHERE lesson_id = ?", (lesson_id,)
        return [{"at": a, "kind": k, "lesson_id": i, **json.loads(d)} for a, k, i, d in self._db.execute(sql + " ORDER BY id", args)]

    def version(self, scope: str) -> int:
        row = self._db.execute("SELECT version FROM scope_versions WHERE scope = ?", (scope,)).fetchone()
        return row[0] if row else 1

    def _bump(self, scope: str) -> int:
        v = self.version(scope) + 1
        self._db.execute("INSERT OR REPLACE INTO scope_versions VALUES (?, ?)", (scope, v))
        return v

    # --- write path ------------------------------------------------------------------------------------------
    def propose(self, record: dict | LessonProposal, now: datetime | None = None) -> ProposalResult:
        now = now or now_utc()
        try:
            p = record if isinstance(record, LessonProposal) else LessonProposal.model_validate(record)
        except ValidationError as exc:
            return ProposalResult(status="rejected", reason=f"invalid lesson record: {exc.errors()[0]['msg']}")
        if not registry.valid_scope(p.scope):
            return ProposalResult(status="rejected", reason=f"unknown scope {p.scope!r}")
        if reason := guard(p):
            with self._lock, self._db:
                self._event("rejected", None, reason=reason, from_agent=p.from_agent, scope=p.scope, topic=p.topic)
            return ProposalResult(status="rejected", reason=reason)
        with self._lock, self._db:
            peers = [l for l in self.active([p.scope]) if not _expired(l, now)]
            dup = max(peers, key=lambda l: similarity(l.lesson, p.lesson), default=None)
            if dup and similarity(dup.lesson, p.lesson) >= DUPLICATE_SIMILARITY:
                dup.evidence_urls = list(dict.fromkeys(dup.evidence_urls + p.evidence_urls))[:10]
                dup.confidence = max(dup.confidence, p.confidence)
                dup.lineage = list(dict.fromkeys(dup.lineage + p.lineage))
                self._save(dup)
                self._event("merged", dup.lesson_id, from_agent=p.from_agent, run_id=p.run_id)
                return ProposalResult(status="merged", lesson_id=dup.lesson_id, reason="near-duplicate of an active lesson; evidence merged")
            same_topic = next((l for l in peers if l.topic == p.topic), None)
            explicit = self.get(p.supersedes) if p.supersedes else None
            if p.supersedes and (not explicit or explicit.scope != p.scope or explicit.status != "active"):
                return ProposalResult(status="rejected", reason=f"supersedes {p.supersedes!r} is not an active lesson in scope {p.scope!r}")
            lesson = self._new(p, now)
            if same_topic is None and explicit is None:
                self._save(lesson)
                self._event("created", lesson.lesson_id, from_agent=p.from_agent, run_id=p.run_id)
                return ProposalResult(status="created", lesson_id=lesson.lesson_id, archived=self._compact(p.scope, now))
            old = explicit or same_topic
            if old.source_type == "user" and p.source_type != "user":
                self._event("rejected", None, reason="user preference takes precedence", conflicts_with=old.lesson_id, from_agent=p.from_agent)
                return ProposalResult(status="rejected", reason="a traveler-origin preference on this topic takes precedence",
                                      conflicts_with=[old.lesson_id])
            if explicit or p.source_type == "user":
                self._supersede(old, lesson, why="explicit supersede" if explicit else "traveler-origin update")
                return ProposalResult(status="superseded", lesson_id=lesson.lesson_id, conflicts_with=[old.lesson_id],
                                      archived=self._compact(p.scope, now))
            lesson.status = "conflict"
            self._save(lesson)
            self._event("conflict", lesson.lesson_id, conflicts_with=old.lesson_id, from_agent=p.from_agent, run_id=p.run_id)
            return ProposalResult(status="conflict", lesson_id=lesson.lesson_id, conflicts_with=[old.lesson_id],
                                  reason="contradicts an active lesson on the same topic; quarantined until the learning engine resolves it")

    def _new(self, p: LessonProposal, now: datetime) -> Lesson:
        return Lesson(**p.model_dump(), lesson_id="L-" + uuid4().hex[:8], created_at=now.isoformat(),
                      expires_at=expiry(p.source_type, now), version_introduced=self.version(p.scope))

    def _supersede(self, old: Lesson, new: Lesson, why: str) -> None:
        old.status, old.superseded_by = "superseded", new.lesson_id
        new.lineage = list(dict.fromkeys([*new.lineage, old.lesson_id]))
        self._save(old); self._save(new)
        self._event("superseded", old.lesson_id, by=new.lesson_id, why=why)

    def _compact(self, scope: str, now: datetime) -> list[str]:
        """Keep each scope lean: archive expired lessons, then the weakest beyond the cap. User and promoted lessons are kept."""
        live = self.active([scope])
        archived = [l for l in live if _expired(l, now)]
        rest = sorted((l for l in live if not _expired(l, now)), key=lambda l: influence(l, now))
        evictable = [l for l in rest if l.source_type != "user" and l.evaluation_status != "promoted"]
        archived += evictable[:max(0, len(rest) - self.cap)]
        for l in archived:
            l.status = "archived"; self._save(l)
            self._event("archived", l.lesson_id, why="expired" if _expired(l, now) else f"over per-scope cap of {self.cap}")
        return [l.lesson_id for l in archived]

    # --- learning-engine hooks -------------------------------------------------------------------------------
    def record_outcome(self, lesson_ids: list[str], *, success: bool, run_id: str, independent: bool = False,
                       now: datetime | None = None) -> None:
        """Count a trip outcome for lessons an agent cited. Only independent (verifier-confirmed) outcomes validate a
        lesson and refresh its recency and expiry."""
        now = now or now_utc()
        with self._lock, self._db:
            for lesson_id in dict.fromkeys(lesson_ids):
                l = self.get(lesson_id)
                if not l: continue
                if success: l.successes += 1
                else: l.failures += 1
                if independent:
                    l.trips_validated += 1
                    l.last_validated = now.isoformat()
                    l.expires_at = expiry(l.source_type, now)
                self._save(l)
                self._event("outcome", lesson_id, success=success, independent=independent, run_id=run_id)

    def promote(self, lesson_id: str, *, decision_ref: str, to_scope: str | None = None) -> Lesson:
        """Mark a lesson promoted after it passes the N+1 gate. With to_scope (an ancestor scope), teach it to that parent:
        a copy lands there with lineage back to the original, and the parent's version is bumped."""
        with self._lock, self._db:
            l = self.get(lesson_id)
            if not l or l.status != "active": raise ValueError(f"{lesson_id} is not an active lesson")
            if to_scope is None:
                l.evaluation_status = "promoted"; self._save(l)
                self._event("promoted", lesson_id, decision_ref=decision_ref)
                return l
            if to_scope not in _ancestors(l.scope): raise ValueError(f"{to_scope!r} is not a parent scope of {l.scope!r}")
            version = self._bump(to_scope)
            taught = l.model_copy(update=dict(lesson_id="L-" + uuid4().hex[:8], scope=to_scope, evaluation_status="promoted",
                                              version_introduced=version, created_at=now_utc().isoformat(), superseded_by=None))
            existing = next((x for x in self.active([to_scope]) if x.topic == l.topic), None)
            if existing and existing.source_type == "user": raise ValueError(f"{to_scope} holds a traveler preference on this topic")
            if existing: self._supersede(existing, taught, why=f"promotion {decision_ref}")
            self._supersede(l, taught, why=f"taught to {to_scope} ({decision_ref})")
            self._event("taught", taught.lesson_id, from_lesson=lesson_id, to_scope=to_scope, scope_version=version, decision_ref=decision_ref)
            return taught

    def reject(self, lesson_id: str, *, decision_ref: str) -> None:
        with self._lock, self._db:
            l = self.get(lesson_id)
            if not l: raise ValueError(f"unknown lesson {lesson_id}")
            l.evaluation_status, l.status = "rejected", "archived"
            self._save(l)
            self._event("rejected", lesson_id, decision_ref=decision_ref)

    def resolve_conflict(self, winner_id: str, loser_id: str, *, decision_ref: str) -> None:
        """Settle a quarantined contradiction: the winner becomes the one active lesson for its scope+topic."""
        with self._lock, self._db:
            w, lo = self.get(winner_id), self.get(loser_id)
            if not w or not lo or w.scope != lo.scope or w.topic != lo.topic:
                raise ValueError("winner and loser must be lessons on the same scope and topic")
            w.status = "active"
            self._supersede(lo, w, why=f"conflict resolved ({decision_ref})")

    # --- read path -------------------------------------------------------------------------------------------
    def inherited(self, agent_role: str, scope: str, token_budget: int, now: datetime | None = None) -> InheritedLessons:
        now = now or now_utc()
        scopes = [*registry.lineage(agent_role, scope), registry.USER_SCOPE]
        with self._lock:
            live = [l for l in self.active(scopes) if not _expired(l, now) and l.evaluation_status != "rejected"]
            versions = {s: self.version(s) for s in scopes}
        # Conflict-free across scopes: per topic, a traveler preference wins, then the most specific scope.
        rank = {s: i for i, s in enumerate(scopes)}  # user is last, so it ranks most specific
        by_topic: dict[str, Lesson] = {}
        for l in sorted(live, key=lambda l: rank[l.scope]):
            by_topic[l.topic] = l
        scored = sorted(by_topic.values(), key=lambda l: influence(l, now), reverse=True)
        header_cost = estimate_tokens(PROMPT_HEADER) + 1
        chosen, used = [], header_cost
        for l in scored:
            cost = estimate_tokens(render(l)) + 1
            if used + cost <= token_budget:
                chosen.append(l); used += cost
        lessons = [InheritedLesson(**l.model_dump(include=set(InheritedLesson.model_fields) - {"influence"}),
                                   influence=influence(l, now)) for l in chosen]
        block = "\n".join([PROMPT_HEADER, *map(render, chosen)]) if chosen else ""
        return InheritedLessons(agent_role=agent_role, scope=scope, lineage=scopes, scope_versions=versions, lessons=lessons,
                                prompt_block=block, tokens_used=used if chosen else 0, token_budget=token_budget,
                                omitted=len(scored) - len(chosen), generated_at=now.isoformat())

def _expired(l: Lesson, now: datetime) -> bool:
    return bool(l.expires_at) and datetime.fromisoformat(l.expires_at) <= now

def _ancestors(scope: str) -> list[str]:
    out, cur = [], registry.parent_scope(scope)
    while cur:
        out.append(cur); cur = registry.parent_scope(cur)
    return out

_default: LessonStore | None = None

def default_store() -> LessonStore:
    global _default
    if _default is None: _default = LessonStore()
    return _default

def get_inherited_lessons(agent_role: str, scope: str, token_budget: int, *, store: LessonStore | None = None,
                          now: datetime | None = None) -> InheritedLessons:
    """Lessons an agent should read before working, ranked by influence and packed into token_budget.

    agent_role: a registry role (e.g. "tickets", "verifier"). scope: the trip's family scope (e.g. "football").
    Put `prompt_block` in the agent's prompt; ask the agent to cite lesson IDs; pass cited IDs to record_outcome().
    """
    return (store or default_store()).inherited(agent_role, scope, token_budget, now)

def propose_lesson(lesson_record: dict | LessonProposal, *, store: LessonStore | None = None,
                   now: datetime | None = None) -> ProposalResult:
    """Submit a lesson after work. Returns created / merged / superseded / conflict / rejected with a reason."""
    return (store or default_store()).propose(lesson_record, now)
