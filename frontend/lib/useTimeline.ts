"use client";
import { useEffect, useState } from "react";

/** Plays elapsed time from `from` to `to` in real time; with reduced motion it jumps straight to `to`. */
export function useTimeline(from: number, to: number, reduced: boolean) {
  const [elapsed, setElapsed] = useState(from);

  useEffect(() => {
    if (reduced) { setElapsed(to); return; }
    setElapsed(from);
    const started = performance.now();
    let frame = 0;
    const tick = () => {
      const next = Math.min(from + performance.now() - started, to);
      setElapsed(next);
      if (next < to) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [from, to, reduced]);

  return elapsed;
}
