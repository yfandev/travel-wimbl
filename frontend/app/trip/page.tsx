"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Assumption } from "@/components/ui";
import { discoverTrip } from "@/lib/api";
import { parseGoal } from "@/lib/goal";

// One request per goal, even when React runs the effect twice in development.
const inflight = new Map<string, ReturnType<typeof discoverTrip>>();

/** Starts a live discovery for the goal, then opens the recorded run. Never falls back to sample data. */
function TripScreen() {
  const router = useRouter();
  const goal = useSearchParams().get("goal") ?? "";
  const parsed = useMemo(() => parseGoal(goal), [goal]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!goal) return;
    let cancelled = false;
    if (!inflight.has(goal)) inflight.set(goal, discoverTrip(parsed.request).finally(() => setTimeout(() => inflight.delete(goal), 1000)));
    inflight.get(goal)!
      .then((r) => { if (!cancelled) router.replace(`/run/${r.run_id}`); })
      .catch((e: Error) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [goal, parsed, router]);

  if (!goal) return <p className="text-muted">Enter a goal on the home page.</p>;

  return (
    <div className="space-y-10">
      <h1 className="text-h1 font-semibold">{goal}</h1>
      <section aria-labelledby="read" className="grid gap-8 rounded-lg bg-mist p-6 sm:grid-cols-2 sm:p-8">
        <div>
          <h2 id="read" className="font-semibold">What you asked for</h2>
          <ul className="mt-3 space-y-1.5">{parsed.stated.map((s) => <li key={s}>{s}</li>)}</ul>
        </div>
        <div>
          <h2 className="font-semibold">Assumed, so you weren&rsquo;t asked</h2>
          <ul className="mt-3 space-y-1.5">{parsed.assumptions.map((a) => <Assumption key={a}>{a}</Assumption>)}</ul>
          <p className="mt-3 text-xs text-muted">Read in the browser for now; the controller&rsquo;s goal compiler will replace this step.</p>
        </div>
      </section>
      {error
        ? <p role="alert" className="rounded-lg border border-red/30 bg-red/5 px-5 py-4 text-sm text-red">Discovery failed: {error}</p>
        : <p role="status" className="text-muted">Searching You.com and checking official pages…</p>}
    </div>
  );
}

export default function TripPage() {
  return <Suspense fallback={<p className="text-muted">Loading…</p>}><TripScreen /></Suspense>;
}
