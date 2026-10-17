"""Shared Brain measurement v2: defect-grounded lessons, gated serving, held-out evaluation.

1. Benchmark trip A (Barcelona): baseline runs; the deterministic checks act as the independent verifier.
2. The stand-in learning engine writes one actionable lesson per failed check (wimbl/memory/reflection_standin.py).
3. Stand-in gate on trip A: candidate runs vs baseline; promote only past a threshold fixed below, with no critical regression.
4. Held-out trips B and C (unchanged from v1): memory off vs on, interleaved, as many runs as fit before DEADLINE.
   "On" uses the normal serving path, so if the gate rejects, nothing is served and on == off by construction.
Writes data/memory_v2_runs.json (raw, incrementally) and docs/memory-results-v2.md.
"""
import asyncio
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))

import measure_memory as v1  # noqa: E402  (same trips, grader, task prompt, output schema)
from wimbl.config import settings  # noqa: E402
from wimbl.integrations.crusoe import CrusoeClient  # noqa: E402
from wimbl.integrations.models import model_for  # noqa: E402
from wimbl.memory import LessonStore, get_inherited_lessons  # noqa: E402
from wimbl.memory.reflection_standin import FailedCheck, propose_all, reflect_on_defects, standin_gate  # noqa: E402

# Fixed before any run (from the diagnosis in data/memory_diagnosis.json):
PRIMARY_CHECKS = ["names_official_resale", "kickoff_risk"]  # the only checks with headroom on held-out trips
CRITICAL_CHECKS = ["official_source", "no_live_price_claim", "flags_third_party"]
GATE_THRESHOLD = 0.10   # target-check pass rate must rise by more than 10 points on the benchmark
GATE_RUNS = 4           # per arm on benchmark trip A
TARGET_PER_CELL = 10    # held-out runs per trip per arm -> 20 per arm
CONCURRENCY = 2         # Lightning returned 429s at 4 concurrent calls
DEADLINE = datetime.now().astimezone().replace(hour=17, minute=45, second=0, microsecond=0)  # stop scheduling new runs
REQUIREMENTS = {
    "official_source": "cite the club's official ticketing page as the source",
    "flags_third_party": "list third-party marketplaces as unofficial sources",
    "no_live_price_claim": "never claim prices are live",
    "names_official_resale": "name the club's official resale or ticket exchange platform in the recommended channel",
    "kickoff_risk": "warn that kickoff dates and times can move (e.g. for broadcast)",
}
RUN_ID = "memv2-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RAW = ROOT / "data" / "memory_v2_runs.json"
state: dict = {"run_id": RUN_ID, "fixed": {"primary_checks": PRIMARY_CHECKS, "critical_checks": CRITICAL_CHECKS,
               "gate_threshold": GATE_THRESHOLD, "gate_runs": GATE_RUNS, "target_per_cell": TARGET_PER_CELL,
               "deadline": DEADLINE.isoformat(), "child_model": model_for("tickets"), "learning_model": model_for("learning")},
               "gate": {}, "heldout": []}

def save() -> None:
    RAW.write_text(json.dumps(state, indent=1, ensure_ascii=False, default=str))

def row(out: dict, **meta) -> dict:
    if "finding" in out:
        return {**meta, "checks": out["checks"], "finding": out["finding"].model_dump(), "output_tokens": out["output_tokens"],
                "latency_ms": out["latency_ms"]}
    return {**meta, "error": out.get("error", "unknown")}

async def runs(c: CrusoeClient, trip: str, block: str, n: int, label: str) -> list[dict]:
    outs = await asyncio.gather(*[v1.run_child(c, v1.TRIPS[trip], block, label) for _ in range(n)])
    return [row(o, trip=trip, memory="on" if block else "off") for o in outs]

async def main() -> int:
    if not settings.crusoe_api_key:
        print("ERROR: CRUSOE_API_KEY is not set. Add it to .env.local."); return 2
    v1.RUN_ID = RUN_ID
    db = ROOT / "data" / "memory_v2.sqlite3"
    db.unlink(missing_ok=True)
    store, c = LessonStore(str(db)), CrusoeClient(max_concurrency=CONCURRENCY)

    # 1. Benchmark baseline on trip A; failed checks become the verifier's defect report.
    base = await runs(c, "A_barcelona", "", GATE_RUNS, "gate-base")
    graded = [r for r in base if "checks" in r]
    fails = {k: [r for r in graded if not r["checks"][k]] for k in REQUIREMENTS}
    failed = sorted((k for k in fails if fails[k]), key=lambda k: -len(fails[k]))
    state["gate"] = {"baseline": base, "failed_checks": {k: len(fails[k]) for k in failed}}; save()
    print("trip A baseline failures:", state["gate"]["failed_checks"])
    if not failed:
        print("No defects on the benchmark; nothing to learn."); write_report(); return 0
    a = v1.TRIPS["A_barcelona"]
    checks = [FailedCheck(check_id=k, requirement=REQUIREMENTS[k],
                          observed=(fails[k][0]["finding"]["recommended_channel"] + " | risks: " + "; ".join(fails[k][0]["finding"]["risks"]))[:400],
                          evidence_urls=[e["url"] for e in a["evidence"] if "footballticketnet" not in e["url"]]) for k in failed]

    # 2. Stand-in reflection on the verifier's defects, through the normal write path.
    proposals = await reflect_on_defects(c, run_id=RUN_ID, agent_role="tickets", family="football", failed_checks=checks)
    results = propose_all(proposals, store)
    state["gate"]["proposals"] = [{"lesson": p.lesson, "topic": p.topic, **r.model_dump()} for p, r in zip(proposals, results)]; save()
    for p, r in zip(proposals, results): print(f"proposed {r.status} {r.lesson_id}: {p.lesson} {r.reason}")
    ids = [r.lesson_id for r in results if r.status in ("created", "merged", "superseded") and r.lesson_id]

    # 3. Stand-in gate on the benchmark.
    if ids:
        async def evaluate(block: str) -> list[dict[str, bool]]:
            cand = await runs(c, "A_barcelona", block, GATE_RUNS, "gate-cand")
            state["gate"]["candidate"] = cand; save()
            return [r["checks"] for r in cand if "checks" in r]
        gate = await standin_gate(store, ids, evaluate=evaluate, target_checks=failed, critical_checks=[k for k in CRITICAL_CHECKS if k not in failed],
                                  threshold=GATE_THRESHOLD, decision_ref=f"{RUN_ID}-gate", baseline=[r["checks"] for r in graded])
        state["gate"]["result"] = gate.model_dump(); save()
        print("gate:", gate.decision, gate.baseline_target_rate, "->", gate.candidate_target_rate, gate.critical_regressions)

    # 4. Held-out trips through the normal serving path (promoted lessons only).
    served = get_inherited_lessons("tickets", "football", v1.TOKEN_BUDGET, store=store)
    state["served"] = {"ids": [l.lesson_id for l in served.lessons], "prompt_block": served.prompt_block}; save()
    if not served.lessons:
        print("Gate rejected: nothing is served, so memory on == off by construction. Skipping held-out runs.")
        write_report(); return 0
    jobs = [(t, arm) for _ in range(TARGET_PER_CELL) for t in ("B_arsenal", "C_bayern") for arm in ("off", "on")]  # interleaved
    queue: asyncio.Queue = asyncio.Queue()
    for j in jobs: queue.put_nowait(j)
    async def worker():
        while not queue.empty():
            if datetime.now().astimezone() >= DEADLINE: return
            t, arm = queue.get_nowait()
            out = await v1.run_child(c, v1.TRIPS[t], served.prompt_block if arm == "on" else "", f"{t}-{arm}")
            state["heldout"].append(row(out, trip=t, memory=arm)); save()
    await asyncio.gather(*[worker() for _ in range(CONCURRENCY)])
    state["heldout_scheduled"], state["heldout_planned"] = len(state["heldout"]), len(jobs); save()
    write_report(); return 0

def _target_rate(r: dict) -> float: return statistics.mean(r["checks"][k] for k in PRIMARY_CHECKS)
def _score(r: dict) -> float: return statistics.mean(r["checks"].values())

def _diff_ci(off: list[float], on: list[float]) -> str:
    if len(off) < 2 or len(on) < 2: return "n too small for an interval"
    d = statistics.mean(on) - statistics.mean(off)
    se = math.sqrt(statistics.variance(off) / len(off) + statistics.variance(on) / len(on))
    return f"{d:+.3f} (95% CI {d - 1.96 * se:+.3f} to {d + 1.96 * se:+.3f}, normal approximation)"

def write_report() -> None:
    g, lines = state["gate"], []
    lines += ["# Shared Brain measurement v2", "",
              f"Run `{RUN_ID}`, {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Child `{state['fixed']['child_model']}`, stand-in learning "
              f"engine on `{state['fixed']['learning_model']}`, both served by Crusoe Managed Inference. Generated by "
              "`scripts/measure_memory_v2.py`; raw outputs in `data/memory_v2_runs.json`.", "",
              "What changed since v1 (`docs/memory-results.md`, diagnosis in `data/memory_diagnosis.json`): lessons are written from "
              "the verifier's failed checks by a stand-in learning engine, labels and fragments are rejected at write time, and only "
              "lessons that pass a benchmark gate are served. Held-out trips B and C and the grader are unchanged.", "",
              f"Fixed before running: primary metric = pass rate on {', '.join(PRIMARY_CHECKS)}; gate threshold +{GATE_THRESHOLD:.2f} on the "
              f"failed checks with no drop in {', '.join(CRITICAL_CHECKS)}; {GATE_RUNS} benchmark runs per arm.", "",
              "## 1. Benchmark trip A: verifier defects", ""]
    base = [r for r in g.get("baseline", []) if "checks" in r]
    lines.append(f"{len(base)}/{len(g.get('baseline', []))} baseline runs graded. Failed checks (runs failing): "
                 + (", ".join(f"`{k}` {v}" for k, v in g.get("failed_checks", {}).items()) or "none") + ".")
    lines += ["", "## 2. Lessons written from those defects", ""]
    for p in g.get("proposals", []):
        lines.append(f"- `{p['status']}` {p.get('lesson_id') or ''} (topic `{p['topic']}`): \"{p['lesson']}\"" + (f" — {p['reason']}" if p.get("reason") else ""))
    if "result" in g:
        res = g["result"]
        lines += ["", "## 3. Gate on the benchmark", "",
                  f"**{res['decision'].upper()}** (`{res['decision_ref']}`). Failed-check pass rate {res['baseline_target_rate']:.2f} → "
                  f"{res['candidate_target_rate']:.2f} (delta {res['delta']:+.2f}, threshold +{res['threshold']:.2f}); "
                  f"{res['baseline_runs']} baseline vs {res['candidate_runs']} candidate runs graded; critical regressions: "
                  f"{', '.join(res['critical_regressions']) or 'none'}.", "", "| Check | Baseline | Candidate |", "|---|---|---|"]
        lines += [f"| {k} | {v['baseline']:.2f} | {v['candidate']:.2f} |" for k, v in res["per_check"].items()]
    lines += ["", "## 4. Held-out trips: memory off vs on", ""]
    served = state.get("served", {})
    if not served.get("ids"):
        lines.append("The gate did not promote any lesson, so the serving path returns nothing and memory on is identical to memory off. "
                     "**Measured gain: zero (by construction).** No held-out runs were spent.")
    else:
        hs = state["heldout"]
        ok = [r for r in hs if "checks" in r]
        lines.append(f"Served lesson(s): {', '.join(served['ids'])}. {len(hs)} of {state.get('heldout_planned', '?')} planned runs completed "
                     f"before the {DEADLINE:%H:%M} cutoff or the plan's end; {len(ok)} graded, {len(hs) - len(ok)} failed (excluded).")
        lines += ["", "| Arm | Graded runs | Primary: target-check pass rate | SD (per run) | Full 5-check score | SD | Cited a served lesson |",
                  "|---|---|---|---|---|---|---|"]
        arms = {}
        for arm in ("off", "on"):
            rs = [r for r in ok if r["memory"] == arm]
            arms[arm] = rs
            t, s = [_target_rate(r) for r in rs], [_score(r) for r in rs]
            cited = sum(1 for r in rs if set(r["finding"].get("lessons_used", [])) & set(served["ids"]))
            sd = lambda xs: f"{statistics.stdev(xs):.3f}" if len(xs) > 1 else "–"
            lines.append(f"| {arm} | {len(rs)} | {statistics.mean(t):.3f} | {sd(t)} | {statistics.mean(s):.3f} | {sd(s)} | {cited}/{len(rs)} |" if rs else f"| {arm} | 0 | – | – | – | – | – |")
        if arms["off"] and arms["on"]:
            lines += ["", f"**Primary delta (on − off): {_diff_ci([_target_rate(r) for r in arms['off']], [_target_rate(r) for r in arms['on']])}.**",
                      f"Full-score delta: {_diff_ci([_score(r) for r in arms['off']], [_score(r) for r in arms['on']])}."]
            lines += ["", "| Check | Off | On |", "|---|---|---|"]
            for k in REQUIREMENTS:
                f = lambda arm: f"{sum(r['checks'][k] for r in arms[arm])}/{len(arms[arm])}"
                lines.append(f"| {k} | {f('off')} | {f('on')} |")
            lines += ["", "| Trip | Arm | Graded | Target-check pass rate |", "|---|---|---|---|"]
            for t in ("B_arsenal", "C_bayern"):
                for arm in ("off", "on"):
                    rs = [r for r in arms[arm] if r["trip"] == t]
                    lines.append(f"| {t} | {arm} | {len(rs)} | {statistics.mean(_target_rate(r) for r in rs):.3f} |" if rs else f"| {t} | {arm} | 0 | – |")
            n = min(len(arms["off"]), len(arms["on"]))
            if n < 15: lines += ["", f"**Small sample:** {n} graded runs in the smaller arm (target was 15–20). Read the interval, not the point estimate."]
    lines += ["", "One task type, fixture evidence, one benchmark trip for the gate. This shows whether gated, defect-grounded lessons "
              "transfer to held-out trips on this task; it is not a general quality claim."]
    (ROOT / "docs" / "memory-results-v2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines)); print("Wrote docs/memory-results-v2.md")

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
