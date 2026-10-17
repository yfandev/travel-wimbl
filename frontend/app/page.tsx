"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

const EXAMPLES = [
  "See Barcelona at the Camp Nou in March, under $2,500 from SFO",
  "A Premier League derby this autumn, flying from JFK",
  "The cheapest big European match this season",
];

export default function Home() {
  const router = useRouter();
  const [goal, setGoal] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!goal.trim()) return;
    // Until the controller API exists, every goal opens the mock run.
    router.push(`/run/mock-run-0001?goal=${encodeURIComponent(goal.trim())}`);
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center pt-12 text-center sm:pt-24">
      <h1 className="text-[2.25rem] font-semibold leading-tight tracking-tight sm:text-display">Where do you want to cheer?</h1>
      <p className="mt-4 max-w-xl text-lg text-muted">
        One line is enough. WIMBL infers sensible defaults, labels every assumption, and checks its own work before it answers.
      </p>

      <form onSubmit={submit} className="mt-10 flex w-full flex-col gap-3 sm:flex-row">
        <label htmlFor="goal" className="sr-only">Your football trip goal</label>
        <input id="goal" value={goal} onChange={(e) => setGoal(e.target.value)} maxLength={200}
          placeholder="Barcelona at the Camp Nou in March, under $2,500 from SFO"
          className="min-w-0 flex-1 rounded-xl border border-line bg-white px-4 py-3.5 text-base placeholder:text-muted/70 focus:border-forest" />
        <button type="submit" className="rounded-xl bg-gold px-6 py-3.5 font-semibold text-forest transition-colors hover:bg-[#b8931f] disabled:opacity-50" disabled={!goal.trim()}>
          Plan my trip
        </button>
      </form>

      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <span className="sr-only">Examples:</span>
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" onClick={() => setGoal(ex)}
            className="rounded-full border border-line bg-mist px-3.5 py-1.5 text-sm text-forest hover:border-forest">
            {ex}
          </button>
        ))}
      </div>

      <dl className="mt-24 grid w-full gap-px overflow-hidden rounded-xl border border-line bg-line text-left sm:grid-cols-3">
        {[
          ["Done means done", "Your goal becomes frozen, executable checks. An independent verifier can fail the plan."],
          ["A family that learns", "Children inherit proven lessons from the Football Parent, with weights and sources."],
          ["Version N+1", "A change ships only if it beats baseline on scenarios it was never tuned on."],
        ].map(([t, d]) => (
          <div key={t} className="bg-white p-6">
            <dt className="font-semibold">{t}</dt>
            <dd className="mt-2 text-sm text-muted">{d}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
