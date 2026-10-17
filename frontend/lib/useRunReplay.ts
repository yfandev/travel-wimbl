"use client";
import { useEffect, useMemo, useState } from "react";
import type { AcceptanceCheck, AgentNode, ControllerDecision, MonitorAlert, Run, RunStage, TripFact, TripPackage } from "./types";

export interface RunView {
  stage: RunStage;
  agents: AgentNode[];
  activeId: string | null;
  facts: (TripFact & { t: number })[];
  checks: AcceptanceCheck[];
  alerts: MonitorAlert[];
  decisions: ControllerDecision[];
  packages: TripPackage[];
  elapsed: number;
  done: boolean;
}

/** Folds the run's event timeline up to `elapsed` ms. The same fold serves live streams and replays. */
export function foldRun(run: Run, elapsed: number): RunView {
  const view: RunView = {
    stage: "REQUEST", agents: [...(run.agents ?? [])], activeId: null, facts: [...(run.facts ?? []).map((f) => ({ ...f, t: 0 }))],
    alerts: [], decisions: [], packages: [],
    checks: run.checks.map((c) => ({ ...c })), elapsed, done: false,
  };
  for (const e of run.events) {
    if (e.t > elapsed) break;
    switch (e.type) {
      case "stage": view.stage = e.stage; break;
      case "spawn": view.agents.push(e.agent); break;
      case "active": view.activeId = e.agent_id; break;
      case "fact": view.facts.push({ ...e.fact, t: e.t }); break;
      case "alert": view.alerts.push(e.alert); break;
      case "decision": view.decisions.push(e.decision); break;
      case "packages": view.packages = e.packages; break;
      case "check": {
        const c = view.checks.find((x) => x.check_id === e.check_id);
        if (c) { c.status = e.status; c.detail = e.detail; }
      }
    }
  }
  view.done = elapsed >= (run.events.at(-1)?.t ?? 0);
  return view;
}

/** Only the sample run has a scripted timeline to play. Recorded runs measure just start and completion, so they
 *  open at their final state instead of animating invented timings. */
export const isScripted = (run: Run | null) => run?.mode === "mock" && !run.started_at;

export function useRunReplay(run: Run | null) {
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(true);
  const end = run?.events.at(-1)?.t ?? 0;

  const scripted = isScripted(run);

  useEffect(() => {
    if (!run || !scripted || !playing || elapsed >= end) return;
    const started = performance.now() - elapsed;
    let frame = 0;
    const tick = () => {
      const next = Math.min(performance.now() - started, end);
      setElapsed(next);
      if (next < end) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // elapsed is read once to resume from where playback paused
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, scripted, playing, end]);

  // Recorded runs are always shown at their final state.
  const shown = scripted ? elapsed : end;
  const view = useMemo(() => (run ? foldRun(run, shown) : null), [run, shown]);
  return {
    view,
    playing: scripted && playing && elapsed < end,
    toggle: () => setPlaying((p) => !p),
    restart: () => { setElapsed(0); setPlaying(true); },
    skip: () => { setElapsed(end); setPlaying(false); },
  };
}

export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const on = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}
