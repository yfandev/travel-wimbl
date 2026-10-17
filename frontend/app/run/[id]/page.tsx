"use client";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApprovalModal } from "@/components/ApprovalModal";
import { Alerts, ChecksList, Decisions } from "@/components/DonePanel";
import { FamilyTree } from "@/components/FamilyTree";
import { Packages } from "@/components/Packages";
import { Card, Chip, Micro, Assumption, formatTime } from "@/components/ui";
import { getRun } from "@/lib/api";
import type { Run, TripPackage } from "@/lib/types";
import { useRunReplay } from "@/lib/useRunReplay";

const MODE_LABEL = { live: "Live", replayed: "Replayed", mock: "Mock" } as const;

function RunScreen() {
  const { id } = useParams<{ id: string }>();
  const goalParam = useSearchParams().get("goal");
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<TripPackage | null>(null);
  const [approved, setApproved] = useState<string | null>(null);
  const { view, playing, toggle, restart, skip } = useRunReplay(run);

  useEffect(() => { getRun(id).then(setRun).catch((e: Error) => setError(e.message)); }, [id]);

  if (error) return <p role="alert" className="text-red">Could not load run: {error}</p>;
  if (!run || !view) return <p className="text-muted">Loading run…</p>;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone={run.mode === "live" ? "pitch" : "rust"}>{MODE_LABEL[run.mode]}</Chip>
            <span className="font-mono text-xs text-muted">{run.run_id}</span>
          </div>
          <h1 className="mt-2 text-h1 font-semibold">{run.goal}</h1>
          {goalParam && goalParam !== run.goal && (
            <p className="mt-1 text-sm text-rust">You entered &ldquo;{goalParam}&rdquo;. The controller API isn&rsquo;t connected yet, so this shows the mock run.</p>
          )}
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={view.done ? restart : toggle} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-forest">
            {view.done ? "Replay" : playing ? "Pause" : "Resume"}
          </button>
          {!view.done && <button type="button" onClick={skip} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-forest">Skip to result</button>}
        </div>
      </header>

      <Card className="min-w-0">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="text-h2 font-semibold">The family at work</h2>
          <p className="flex flex-wrap gap-x-4 text-sm text-muted" aria-live="polite">
            <span>Stage: <span className="font-medium text-forest">{view.stage}</span></span>
            <span>Checks: <span className="font-medium text-forest">{view.checks.filter((c) => c.status === "passed").length}/{view.checks.length} passed</span></span>
          </p>
        </div>
        <FamilyTree agents={view.agents} activeId={view.activeId} facts={view.facts} elapsed={view.elapsed} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card><ChecksList checks={view.checks} hash={run.criteria_hash} /></Card>
        <div className="space-y-6">
          <Card>
            <Micro>Monitors</Micro>
            <div className="mt-2"><Alerts alerts={view.alerts} /></div>
            <div className="mt-5"><Decisions decisions={view.decisions} /></div>
          </Card>
          <Card>
            <Micro>Shared trip board</Micro>
            {!view.facts.length && <p className="mt-2 text-sm text-muted">No facts shared yet.</p>}
            <ul className="mt-2 space-y-3">
              {view.facts.map((f) => (
                <li key={f.key} className="rise text-sm">
                  <p><span className="font-medium">{f.key}:</span> {f.value}</p>
                  <p className="font-mono text-xs text-muted">{f.from_agent} → {f.to_agents.join(", ")} · {formatTime(f.observed_at)}</p>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      <section aria-labelledby="inferred" className="grid gap-6 rounded-xl bg-mist p-5 sm:grid-cols-3 sm:p-6">
        <div>
          <h2 id="inferred" className="font-semibold">Hard constraints</h2>
          <ul className="mt-2 space-y-1 text-sm">{run.constraints.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
        <div>
          <h2 className="font-semibold">Inferred defaults</h2>
          <ul className="mt-2 space-y-1">{run.assumptions.map((a) => <Assumption key={a}>{a}</Assumption>)}</ul>
          <p className="mt-2 text-xs text-muted">0 questions asked.</p>
        </div>
        <div>
          <h2 className="font-semibold">Budgets</h2>
          <dl className="mt-2 grid grid-cols-2 gap-1 text-sm">
            <dt className="text-muted">Retries</dt><dd>{run.budget.retries}</dd>
            <dt className="text-muted">Wall clock</dt><dd>{run.budget.wall_clock_s}s</dd>
            <dt className="text-muted">Tokens</dt><dd>{run.budget.tokens.toLocaleString()}</dd>
            <dt className="text-muted">Tool calls</dt><dd>{run.budget.tool_calls}</dd>
          </dl>
        </div>
      </section>

      <section aria-labelledby="results">
        <h2 id="results" className="text-h2 font-semibold">Ranked packages</h2>
        {approved && (
          <p role="status" className="mt-3 rounded-lg bg-pitch/10 px-4 py-3 text-sm text-pitch">
            Approved: {approved}. In live mode you&rsquo;d now get the provider links. Nothing has been booked or charged.
          </p>
        )}
        <div className="mt-4">
          {view.packages.length ? <Packages packages={view.packages} onRequestBooking={setPending} />
            : <p className="text-sm text-muted">Packages appear once every frozen check passes, or as a truthful partial result if the budget runs out.</p>}
        </div>
      </section>

      <ApprovalModal pkg={pending} onCancel={() => setPending(null)} onApprove={() => { setApproved(pending?.title ?? null); setPending(null); }} />
    </div>
  );
}

export default function RunPage() {
  return <Suspense fallback={<p className="text-muted">Loading run…</p>}><RunScreen /></Suspense>;
}
