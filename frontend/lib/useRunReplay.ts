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
    stage: "REQUEST", agents: [], activeId: null, facts: [], alerts: [], decisions: [], packages: [],
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

export function useRunReplay(run: Run | null) {
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(true);
  const end = run?.events.at(-1)?.t ?? 0;

  useEffect(() => {
    if (!run || !playing || elapsed >= end) return;
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
  }, [run, playing, end]);

  const view = useMemo(() => (run ? foldRun(run, elapsed) : null), [run, elapsed]);
  return {
    view,
    playing: playing && elapsed < end,
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
