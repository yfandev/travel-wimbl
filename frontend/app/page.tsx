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
    <div className="mx-auto flex max-w-3xl flex-col items-center pt-8 text-center sm:pt-20">
      <h1 className="text-[2.5rem] font-semibold leading-[1.1] tracking-tight sm:text-display">Where do you want to cheer?</h1>
      <p className="mt-6 max-w-xl text-lg text-muted sm:text-xl">
        One line is enough. WIMBL infers sensible defaults, labels every assumption, and checks its own work before it answers.
      </p>

      <form onSubmit={submit} className="mt-12 flex w-full flex-col gap-3 sm:flex-row">
        <label htmlFor="goal" className="sr-only">Your football trip goal</label>
        <input id="goal" value={goal} onChange={(e) => setGoal(e.target.value)} maxLength={200}
          placeholder="Barcelona at the Camp Nou in March, under $2,500 from SFO"
          className="min-w-0 flex-1 rounded-lg border border-line bg-white px-5 py-4 text-base placeholder:text-muted/70 focus:border-forest" />
        <button type="submit" className="rounded-lg bg-gold px-7 py-4 font-semibold text-forest transition-colors hover:bg-[#b8931f] disabled:opacity-50" disabled={!goal.trim()}>
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

      <dl className="mt-28 grid w-full gap-px overflow-hidden rounded-lg border border-line bg-line text-left sm:grid-cols-3">
        {[
          ["Done means done", "Your goal becomes frozen, executable checks. An independent verifier can fail the plan."],
          ["A family that learns", "Children inherit proven lessons from the Football Parent, with weights and sources."],
          ["Version N+1", "A change ships only if it beats baseline on scenarios it was never tuned on."],
        ].map(([t, d]) => (
          <div key={t} className="bg-white p-7">
            <dt className="font-semibold">{t}</dt>
            <dd className="mt-2 text-sm text-muted">{d}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
