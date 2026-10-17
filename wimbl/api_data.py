"""Read-only demo data endpoints for the Next.js app (travel-wimbl-frontend). Shapes follow frontend/lib/types.ts.

Every number comes from a recorded file: runs (data/runs.jsonl, written by POST /api/trips/discover), model calls
(data/run_log.jsonl), lessons (the configured lesson DB), and the memory evaluation (data/memory_v2_runs.json).
Nothing here calls a model or changes state.
"""
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from wimbl.agents.verifier import IndependentVerifier
from wimbl.config import settings
from wimbl.memory import default_store
from wimbl.runlog import RunLog
from wimbl.schemas import TripRequest, TripResult

router = APIRouter(prefix="/api")
ROOT = Path(__file__).resolve().parents[1]
MEMORY_EVAL = ROOT / "data" / "memory_v2_runs.json"

# --- run store -------------------------------------------------------------------------------------------------------
class RunStore:
    """One JSONL row per discovery run: the request, the controller's result, and measured wall-clock timing."""
    def __init__(self, path: str | None = None):
        self.path = Path(path or settings.wimbl_runs_path)

    def record(self, request: TripRequest, result: TripResult, started_at: datetime, elapsed_ms: int) -> None:
        row = {"run_id": result.run_id, "started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms,
               "request": request.model_dump(), "result": result.model_dump()}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass  # a read-only host still returns the result; the run just isn't listed later

    def rows(self) -> list[dict]:
        if not self.path.exists(): return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try: out.append(json.loads(line))
            except json.JSONDecodeError: continue
        return out

    def get(self, run_id: str) -> dict | None:
        return next((r for r in reversed(self.rows()) if r["run_id"] == run_id), None)

runs = RunStore()

def _mode(result: dict) -> str:
    evidence = [e for c in result["candidates"] for e in c["evidence"]]
    return "mock" if evidence and all(e["source"] == "demo" for e in evidence) else "live"

# Verifier finding codes -> index of the acceptance criterion they fail (IndependentVerifier.acceptance_criteria order).
FINDING_TO_CRITERION = {"NO_EVIDENCE": 0, "NO_OFFICIAL_SOURCE": 1, "OFFICIAL_SOURCE_UNCONFIRMED": 1, "DATES_UNSET": 2,
                        "DESTINATION_UNCONFIRMED": 2, "PRICE_UNCONFIRMED": 3, "OVER_BUDGET": 3}
UNCHECKED = {4}       # availability labelling: no verifier check yet
ALWAYS_PASSED = {5}   # no booking or payment action exists in the system

def _checks(result: dict) -> list[dict]:
    failed: dict[int, list[str]] = {}
    for f in result["findings"]:
        if f["code"] in FINDING_TO_CRITERION: failed.setdefault(FINDING_TO_CRITERION[f["code"]], []).append(f["message"])
    out = []
    for i, text in enumerate(result["acceptance_criteria"]):
        if i in failed: status, detail = "failed", " ".join(failed[i])
        elif i in ALWAYS_PASSED: status, detail = "passed", "No booking or payment action is available."
        elif i in UNCHECKED or not result["candidates"]: status, detail = "pending", "Not checked by the verifier yet."
        else: status, detail = "passed", None
        out.append({"check_id": f"C{i + 1}", "description": text, "status": status, "detail": detail})
    return out

def _run_summary(r: dict) -> dict:
    res = r["result"]
    return {"run_id": r["run_id"], "goal": r["request"]["interest"], "mode": _mode(res), "status": res["status"],
            "controller_decision": res["controller_decision"], "started_at": r["started_at"], "elapsed_ms": r["elapsed_ms"],
            "candidates": len(res["candidates"]), "findings": len(res["findings"]),
            "evidence": sum(len(c["evidence"]) for c in res["candidates"])}

def _run_detail(r: dict) -> dict:
    req, res, end = r["request"], r["result"], r["elapsed_ms"]
    checks = _checks(res)
    ledger = [{"candidate": c["title"], **e} for c in res["candidates"] for e in c["evidence"]]
    # The controller does not timestamp its steps yet, so only REQUEST (t=0) and completion (t=elapsed) are measured;
    # every intermediate event is placed at completion, in recorded order, rather than at invented times.
    events = [{"t": 0, "type": "stage", "stage": "REQUEST"}, {"t": end, "type": "stage", "stage": "DISCOVER"},
              {"t": end, "type": "stage", "stage": "VERIFY"}]
    events += [{"t": end, "type": "check", "check_id": c["check_id"], "status": c["status"], "detail": c["detail"]} for c in checks]
    events += [{"t": end, "type": "decision", "decision": {"at": r["started_at"], "stage": "VERIFY", "decision": res["controller_decision"],
                                                          "reason": res["steps"][-1] if res["steps"] else ""}},
               {"t": end, "type": "stage", "stage": "FINAL RESULT"}]
    constraints = [f"Budget {req['budget']:.0f} {req['currency']}", f"From {req['origin']}", f"{req['days']} days"]
    if req.get("dates"): constraints.append(f"Dates {req['dates']}")
    return {"run_id": r["run_id"], "goal": req["interest"], "mode": _mode(res),
            "criteria_hash": hashlib.sha256(json.dumps(res["acceptance_criteria"]).encode()).hexdigest()[:16],
            "constraints": constraints, "assumptions": sorted({cv for c in res["candidates"] for cv in c["caveats"]}),
            "budget": {"retries": None, "wall_clock_s": None, "tokens": None, "tool_calls": None},
            "checks": checks, "events": events,
            # Beyond frontend/lib/types.ts Run:
            "started_at": r["started_at"], "elapsed_ms": end, "status": res["status"], "steps": res["steps"],
            "findings": res["findings"], "evidence_ledger": ledger, "model_calls": RunLog().read(r["run_id"]),
            "timing_note": "Only start and completion are measured; the controller does not timestamp intermediate steps yet.",
            "budget_note": "Run budgets are not enforced yet (Phase 2).", "trip_result": res}

@router.get("/runs")
async def list_runs(limit: int = 50):
    return [_run_summary(r) for r in reversed(runs.rows())][:max(1, min(limit, 500))]

@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    r = runs.get(run_id)
    if not r: raise HTTPException(status_code=404, detail=f"No recorded run {run_id!r}.")
    return _run_detail(r)

@router.get("/runlog")
async def get_runlog(run_id: str | None = None, limit: int = 500):
    return RunLog().read(run_id)[-max(1, min(limit, 5000)):][::-1]

# --- memory ----------------------------------------------------------------------------------------------------------
@router.get("/memory/lessons")
async def get_lessons(scope: str | None = None):
    """Lesson records in the frontend's {entries: Lesson[]} envelope. (GET /api/memory keeps returning the run journal.)"""
    return {"entries": [l.model_dump() for l in default_store().all(scope)], "lessons_db": settings.wimbl_lessons_db}

def _memory_eval() -> dict:
    if not MEMORY_EVAL.exists(): raise HTTPException(status_code=404, detail="No memory evaluation recorded (data/memory_v2_runs.json).")
    return json.loads(MEMORY_EVAL.read_text(encoding="utf-8"))

def _stats(xs: list[float]) -> dict:
    return {"mean": round(statistics.mean(xs), 4), "spread": round(statistics.stdev(xs), 4) if len(xs) > 1 else 0.0, "runs": len(xs)}

def _ci(off: list[float], on: list[float]) -> list[float] | None:
    if len(off) < 2 or len(on) < 2: return None
    d = statistics.mean(on) - statistics.mean(off)
    se = math.sqrt(statistics.variance(off) / len(off) + statistics.variance(on) / len(on))
    return [round(d - 1.96 * se, 4), round(d + 1.96 * se, 4)]

def _arms(d: dict) -> dict[str, list[dict]]:
    ok = [r for r in d["heldout"] if "checks" in r]
    return {arm: [r for r in ok if r["memory"] == arm] for arm in ("off", "on")}

def _target(d: dict, r: dict) -> float: return statistics.mean(r["checks"][k] for k in d["fixed"]["primary_checks"])
def _score(r: dict) -> float: return statistics.mean(r["checks"].values())

@router.get("/memory/ablation")
async def memory_ablation():
    d = _memory_eval()
    arms = _arms(d)
    served = set(d.get("served", {}).get("ids", []))
    col = lambda f: ([f(r) for r in arms["off"]], [f(r) for r in arms["on"]])
    t_off, t_on = col(lambda r: _target(d, r))
    s_off, s_on = col(_score)
    cite = lambda rs: statistics.mean(bool(set(r["finding"].get("lessons_used", [])) & served) for r in rs)
    tok_off, tok_on = col(lambda r: r["output_tokens"] or 0)
    lat_off, lat_on = col(lambda r: r["latency_ms"])
    mean = lambda xs: round(statistics.mean(xs), 4) if xs else None
    return {"metrics": [
                {"name": "Held-out target-check pass rate (primary)", "memory_off": mean(t_off), "memory_on": mean(t_on), "unit": "rate"},
                {"name": "Held-out full 5-check score", "memory_off": mean(s_off), "memory_on": mean(s_on), "unit": "rate"},
                {"name": "Runs citing a served lesson", "memory_off": round(cite(arms["off"]), 4) if arms["off"] else None,
                 "memory_on": round(cite(arms["on"]), 4) if arms["on"] else None, "unit": "rate"},
                {"name": "Mean output tokens", "memory_off": mean(tok_off), "memory_on": mean(tok_on), "unit": "tokens"},
                {"name": "Median latency", "memory_off": statistics.median(lat_off) if lat_off else None,
                 "memory_on": statistics.median(lat_on) if lat_on else None, "unit": "ms"}],
            # Beyond frontend/lib/types.ts MemoryAblation:
            "run_id": d["run_id"], "n": {"off": len(arms["off"]), "on": len(arms["on"])},
            "primary_checks": d["fixed"]["primary_checks"],
            "primary_delta": round(mean(t_on) - mean(t_off), 4) if t_off and t_on else None, "primary_ci95": _ci(t_off, t_on),
            "full_score_ci95": _ci(s_off, s_on), "served_lessons": sorted(served), "child_model": d["fixed"]["child_model"],
            "caveat": "Small sample, one task type; lessons mirror the acceptance criteria; memory on uses about 1.7x output tokens.",
            "report": "docs/memory-results-v2.md"}

# --- N+1 evaluation ---------------------------------------------------------------------------------------------------
@router.get("/improvement/latest")
async def improvement_latest():
    """The latest recorded gate decision, as an N1Report. Today that is the memory stand-in gate (Patrick's learning
    engine replaces it); POST /api/improvement/evaluate is unchanged."""
    d = _memory_eval()
    gate, arms = d.get("gate", {}), _arms(d)
    res = gate.get("result")
    if not res: raise HTTPException(status_code=404, detail="The latest evaluation has no gate decision.")
    base = [r for r in gate.get("baseline", []) if "checks" in r]
    cand = [r for r in gate.get("candidate", []) if "checks" in r]
    targets = res["target_checks"]
    bench = lambda rs: _stats([statistics.mean(r["checks"][k] for k in targets) for r in rs]) if rs else None
    held = lambda arm: _stats([_target(d, r) for r in arms[arm]]) if arms[arm] else None
    full = lambda arm: _stats([_score(r) for r in arms[arm]]) if arms[arm] else None
    lessons = [p for p in gate.get("proposals", []) if p.get("lesson_id") in res["lesson_ids"]]
    at = datetime.fromtimestamp(MEMORY_EVAL.stat().st_mtime, timezone.utc).isoformat()
    return {"candidate_version": f"football.tickets + {', '.join(res['lesson_ids'])}", "baseline_version": "football.tickets (no lessons)",
            "change": {"target": "playbook", "summary": " / ".join(p["lesson"] for p in lessons),
                       "hypothesis": "Lessons written from the verifier's failed checks on one trip raise those checks' pass rate on other clubs' trips."},
            "gate": [f"Failed-check pass rate on the benchmark rises by more than {res['threshold']:+.2f}",
                     f"No drop in critical checks: {', '.join(d['fixed']['critical_checks'])}",
                     "Held-out trips evaluated only after the gate decision"],
            "metrics": [
                {"name": "Failed-check pass rate (trip A)", "baseline": bench(base), "candidate": bench(cand), "split": "benchmark"},
                {"name": "Target-check pass rate (trips B, C)", "baseline": held("off"), "candidate": held("on"), "split": "heldout"},
                {"name": "Full 5-check score (trips B, C)", "baseline": full("off"), "candidate": full("on"), "split": "heldout"}],
            "decision": "promoted" if res["decision"] == "promote" else "rejected",
            "decision_reason": (f"Benchmark failed-check pass rate {res['baseline_target_rate']:.2f} -> {res['candidate_target_rate']:.2f} "
                                f"(threshold {res['threshold']:+.2f}); critical regressions: {', '.join(res['critical_regressions']) or 'none'}."),
            "history": [{"version": f"football.tickets + {', '.join(res['lesson_ids'])}", "at": at,
                         "note": f"Stand-in gate {res['decision_ref']}", "status": "active" if res["decision"] == "promote" else "retired"}],
            # Beyond frontend/lib/types.ts N1Report:
            "evaluator": "stand-in gate (wimbl/memory/reflection_standin.py)", "report": "docs/memory-results-v2.md",
            "caveat": "The gate scored both lessons as one bundle; on the benchmark one check rose and one fell. Small samples."}
