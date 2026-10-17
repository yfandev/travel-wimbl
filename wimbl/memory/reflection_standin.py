"""STAND-IN for the learning engine's Reflect and Promote steps (Patrick owns the real one, Phase 5).

Replace this module with the learning engine; keep the two signatures so memory callers don't change:

    reflect_on_defects(client, *, run_id, agent_role, family, failed_checks, max_lessons=2) -> list[LessonProposal]
    standin_gate(store, lesson_ids, *, evaluate, target_checks, critical_checks, threshold, decision_ref,
                 baseline=None) -> GateResult

Lessons are written from the independent verifier's failed checks (what went wrong, with evidence), not from the agent's
own self-assessment, and only lessons that beat baseline on benchmark runs get promoted and served.
"""
import asyncio
import statistics
from collections.abc import Awaitable, Callable
from typing import Literal
from pydantic import BaseModel, Field
from wimbl.agents import registry
from wimbl.integrations.crusoe import CrusoeClient, LLMError
from wimbl.memory.lessons import PROMPT_HEADER, LessonProposal, render
from wimbl.memory.store import LessonStore, propose_lesson

class FailedCheck(BaseModel):
    """One acceptance check the verifier failed on a trip."""
    check_id: str                 # e.g. "names_official_resale"
    requirement: str              # what the check requires, in plain words
    observed: str                 # what the agent actually produced
    evidence_urls: list[str] = Field(default_factory=list)  # sources that show the right answer was available

class _Draft(BaseModel):
    check_id: str
    lesson: str = Field(description="One imperative instruction, 12-40 words, general to any club.")
    evidence_urls: list[str]

class _Drafts(BaseModel):
    lessons: list[_Draft]

async def reflect_on_defects(client: CrusoeClient, *, run_id: str, agent_role: str, family: str,
                             failed_checks: list[FailedCheck], max_lessons: int = 2) -> list[LessonProposal]:
    """One learning-role call: one actionable lesson per failed check, scoped to the agent's role. Not yet proposed."""
    if not failed_checks: return []
    checks = failed_checks[:max_lessons]
    prompt = ("You are the learning engine for a family of football-travel agents. The independent verifier failed the "
              f"{agent_role} agent on these acceptance checks:\n"
              + "\n".join(f"- Check {i}: required: {c.requirement}. The agent produced: {c.observed}. Evidence: {', '.join(c.evidence_urls) or 'none'}"
                          for i, c in enumerate(checks, 1))
              + "\nFor each failed check, write exactly one lesson for future agents with the same role on other clubs' trips: "
                "an imperative instruction naming the concrete action that would have passed the check. Do not name a specific "
                "club, a URL, or the check number in the lesson text (evidence URLs go only in evidence_urls). Never tell agents to relax a "
                "check, claim live prices, or book without approval. Use only the evidence URLs given; set check_id to the check number.")
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(4):  # Super is rate-limited on this account (docs/smoke-results.md); wait 30/60/90 s between tries
        try:
            drafts = (await client.structured("learning", messages, _Drafts, run_id=run_id, prompt_version="reflect-standin-v1", max_tokens=6000, timeout=240)).parsed
            break
        except LLMError:
            if attempt == 3: raise
            await asyncio.sleep(30 * (attempt + 1))
    # The topic comes from the failed check, not the model (it once returned "evidence_urls" for every topic), so each
    # check governs exactly one lesson and two lessons for different checks never look like a contradiction.
    out = []
    for i, d in enumerate(drafts.lessons[:len(checks)]):
        num = "".join(ch for ch in str(d.check_id) if ch.isdigit())
        check = checks[int(num) - 1] if num.isdigit() and 0 < int(num) <= len(checks) else checks[i]
        out.append(LessonProposal(lesson=d.lesson, topic=check.check_id, from_agent="learning-standin",
                                  scope=registry.role_scope(family, agent_role), source_type="run", run_id=run_id, confidence=0.6,
                                  evidence_urls=[u for u in d.evidence_urls if u in check.evidence_urls] or check.evidence_urls[:2]))
    return out

class GateResult(BaseModel):
    decision: Literal["promote", "reject"]
    decision_ref: str
    lesson_ids: list[str]
    target_checks: list[str]
    threshold: float
    baseline_runs: int
    candidate_runs: int
    baseline_target_rate: float
    candidate_target_rate: float
    delta: float
    critical_regressions: list[str]
    per_check: dict[str, dict[str, float]]  # check -> {"baseline": rate, "candidate": rate}

def _rate(runs: list[dict[str, bool]], checks: list[str]) -> float:
    vals = [r[c] for r in runs for c in checks]
    return round(statistics.mean(vals), 4) if vals else 0.0

async def standin_gate(store: LessonStore, lesson_ids: list[str], *, evaluate: Callable[[str], Awaitable[list[dict[str, bool]]]],
                       target_checks: list[str], critical_checks: list[str], threshold: float, decision_ref: str,
                       baseline: list[dict[str, bool]] | None = None) -> GateResult:
    """Promote the lesson set only if, on benchmark runs, the target-check pass rate rises by more than `threshold` and
    no critical check drops. `evaluate(prompt_block)` runs the agent on the benchmark and returns one checks dict per run;
    pass "" for baseline. The threshold and checks must be fixed before calling (no tuning after seeing results)."""
    lessons = [l for l in (store.get(i) for i in lesson_ids) if l]
    block = "\n".join([PROMPT_HEADER, *map(render, lessons)])
    baseline = baseline if baseline is not None else await evaluate("")
    candidate = await evaluate(block)
    checks = sorted({c for r in baseline + candidate for c in r})
    per_check = {c: {"baseline": _rate(baseline, [c]), "candidate": _rate(candidate, [c])} for c in checks}
    regressions = [c for c in critical_checks if per_check.get(c, {}).get("candidate", 0) < per_check.get(c, {}).get("baseline", 0)]
    b, cnd = _rate(baseline, target_checks), _rate(candidate, target_checks)
    promote = bool(candidate) and cnd - b > threshold and not regressions
    for l in lessons:
        if promote: store.promote(l.lesson_id, decision_ref=decision_ref)
        else: store.reject(l.lesson_id, decision_ref=decision_ref)
    return GateResult(decision="promote" if promote else "reject", decision_ref=decision_ref, lesson_ids=[l.lesson_id for l in lessons],
                      target_checks=target_checks, threshold=threshold, baseline_runs=len(baseline), candidate_runs=len(candidate),
                      baseline_target_rate=b, candidate_target_rate=cnd, delta=round(cnd - b, 4),
                      critical_regressions=regressions, per_check=per_check)

def propose_all(proposals: list[LessonProposal], store: LessonStore | None = None) -> list:
    """Convenience: send reflection output through the normal write path (guards, dedupe, conflicts)."""
    return [propose_lesson(p, store=store) for p in proposals]
