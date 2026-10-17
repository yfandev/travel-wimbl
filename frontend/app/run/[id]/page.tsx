"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApprovalModal } from "@/components/ApprovalModal";
import { Alerts, ChecksList, Decisions } from "@/components/DonePanel";
import { CandidateCard, EvidenceRow } from "@/components/Evidence";
import { FamilyTree } from "@/components/FamilyTree";
import { Packages } from "@/components/Packages";
import { Assumption, Card, Chip, Micro, formatTime } from "@/components/ui";
import { getRun } from "@/lib/api";
import type { Run, TripPackage } from "@/lib/types";
import { isScripted, useRunReplay } from "@/lib/useRunReplay";

const MODE_LABEL = { live: "Live · You.com", replayed: "Replayed", mock: "Sample data" } as const;

function RunScreen() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<TripPackage | null>(null);
  const [approved, setApproved] = useState<string | null>(null);
  const { view, playing, toggle, restart, skip } = useRunReplay(run ?? null);

  useEffect(() => { getRun(id).then(setRun).catch((e: Error) => setError(e.message)); }, [id]);

  if (error) return <p role="alert" className="text-red">Could not load run: {error}</p>;
  if (run === undefined) return <p className="text-muted">Loading run…</p>;
  if (run === null || !view) return (
    <div className="max-w-xl">
      <h1 className="text-h1 font-semibold">No runs yet</h1>
      <p className="mt-3 text-muted">Runs are recorded when a goal is planned. <Link href="/" className="text-pitch underline underline-offset-2">Enter a goal</Link> to start one.</p>
    </div>
  );

  const scripted = isScripted(run);
  const ledger = run.evidence_ledger ?? [];
  const budgetUnset = Object.values(run.budget).every((v) => v == null);

  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone={run.mode === "live" ? "pitch" : "rust"}>{MODE_LABEL[run.mode]}</Chip>
            <span className="font-mono text-xs text-muted">{run.run_id}</span>
            {run.started_at && <span className="text-xs text-muted">· {formatTime(run.started_at)}</span>}
            {run.elapsed_ms != null && <span className="text-xs text-muted">· {(run.elapsed_ms / 1000).toFixed(1)} s end to end</span>}
          </div>
          <h1 className="mt-2 text-h1 font-semibold">{run.goal}</h1>
        </div>
        {scripted && (
          <div className="flex gap-2">
            <button type="button" onClick={view.done ? restart : toggle} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-forest">
              {view.done ? "Replay" : playing ? "Pause" : "Resume"}
            </button>
            {!view.done && <button type="button" onClick={skip} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-forest">Skip to result</button>}
          </div>
        )}
      </header>

      <Card className="min-w-0">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="text-h2 font-semibold">The family at work</h2>
          <p className="flex flex-wrap gap-x-4 text-sm text-muted" aria-live="polite">
            <span>Stage: <span className="font-medium text-forest">{view.stage}</span></span>
            <span>Checks: <span className="font-medium text-forest">{view.checks.filter((c) => c.status === "passed").length}/{view.checks.length} passed</span></span>
          </p>
        </div>
        {view.agents.length || scripted
          ? <FamilyTree agents={view.agents} activeId={view.activeId} facts={view.facts} elapsed={view.elapsed} />
          : <p className="rounded-lg bg-mist px-5 py-4 text-sm text-muted">The family wasn&rsquo;t recorded for this run. Runs recorded from now on list the agents that ran.</p>}
        {!scripted && view.agents.some((a) => a.executed === false) && (
          <p className="mt-4 text-xs text-muted">Dashed parents are this run&rsquo;s lineage; they run no code yet. No trip children ran, and no inherited lessons were served on this path.</p>
        )}
        {run.timing_note && <p className="mt-2 text-xs text-muted">{run.timing_note}</p>}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card><ChecksList checks={view.checks} hash={run.criteria_hash} /></Card>
        <div className="space-y-6">
          <Card>
            <Micro>Controller</Micro>
            {run.steps && (
              <ol className="mt-3 space-y-1.5 text-sm">
                {run.steps.map((s, i) => <li key={i} className="flex gap-3"><span className="w-4 shrink-0 font-mono text-xs text-muted">{i + 1}</span><span>{s}</span></li>)}
              </ol>
            )}
            <div className="mt-5"><Decisions decisions={view.decisions} /></div>
            {scripted && <div className="mt-5"><Alerts alerts={view.alerts} /></div>}
          </Card>
          {run.findings && run.findings.length > 0 && (
            <Card>
              <Micro>Independent verifier</Micro>
              <ul className="mt-3 space-y-2">
                {run.findings.map((f) => (
                  <li key={f.code} className={`text-sm ${f.severity === "error" ? "text-red" : f.severity === "warning" ? "text-rust" : "text-muted"}`}>
                    <span className="font-mono text-xs font-semibold">{f.code}</span> · {f.message}
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card>
            <Micro>Shared trip board</Micro>
            {!view.facts.length && <p className="mt-2 text-sm text-muted">{scripted ? "No facts shared yet." : "No shared facts recorded. The controller runs no trip children yet."}</p>}
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

      <section aria-labelledby="inferred" className="grid gap-8 rounded-lg bg-mist p-6 sm:grid-cols-3 sm:p-8">
        <div>
          <h2 id="inferred" className="font-semibold">Constraints</h2>
          <ul className="mt-2 space-y-1 text-sm">{run.constraints.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
        <div>
          <h2 className="font-semibold">{scripted ? "Inferred defaults" : "Assumptions and caveats"}</h2>
          <ul className="mt-2 space-y-1">{run.assumptions.map((a) => <Assumption key={a}>{a}</Assumption>)}</ul>
          <p className="mt-2 text-xs text-muted">0 questions asked.</p>
        </div>
        <div>
          <h2 className="font-semibold">Budgets</h2>
          {budgetUnset ? (
            <p className="mt-2 text-sm text-muted">{run.budget_note ?? "Not enforced yet."}</p>
          ) : (
            <dl className="mt-2 grid grid-cols-2 gap-1 text-sm">
              <dt className="text-muted">Retries</dt><dd>{run.budget.retries ?? "—"}</dd>
              <dt className="text-muted">Wall clock</dt><dd>{run.budget.wall_clock_s == null ? "—" : `${run.budget.wall_clock_s}s`}</dd>
              <dt className="text-muted">Tokens</dt><dd>{run.budget.tokens?.toLocaleString() ?? "—"}</dd>
              <dt className="text-muted">Tool calls</dt><dd>{run.budget.tool_calls ?? "—"}</dd>
            </dl>
          )}
        </div>
      </section>

      <section aria-labelledby="results" className="space-y-4">
        <h2 id="results" className="text-h2 font-semibold">{scripted ? "Ranked packages" : "Result"}</h2>
        {approved && (
          <p role="status" className="rounded-lg bg-pitch/10 px-4 py-3 text-sm text-pitch">
            Approved: {approved}. In live mode you&rsquo;d now get the provider links. Nothing has been booked or charged.
          </p>
        )}
        {scripted ? (
          view.packages.length ? <Packages packages={view.packages} onRequestBooking={setPending} />
            : <p className="text-sm text-muted">Packages appear once every frozen check passes, or as a truthful partial result if the budget runs out.</p>
        ) : run.trip_result?.candidates.length ? (
          run.trip_result.candidates.map((c) => <CandidateCard key={c.title} c={c} />)
        ) : (
          <p className="text-sm text-muted">No candidates. The controller decided to {run.trip_result?.controller_decision ?? "stop"}.</p>
        )}
      </section>

      {!scripted && (
        <section aria-labelledby="ledger">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="ledger" className="text-h2 font-semibold">Evidence ledger</h2>
            <p className="text-sm text-muted">{ledger.length} source{ledger.length === 1 ? "" : "s"} · {ledger.filter((e) => e.verified).length} confirmed on the page</p>
          </div>
          {ledger.length ? <ul className="mt-2 divide-y divide-line">{ledger.map((e) => <EvidenceRow key={e.url} e={e} />)}</ul>
            : <p className="mt-2 text-sm text-muted">No evidence recorded.</p>}
          <p className="mt-6 text-sm text-muted">
            Model calls recorded for this run: {run.model_calls?.length ?? 0}.
            {!run.model_calls?.length && " Discovery uses You.com Search and Contents; no Nemotron call is on this path yet."}
          </p>
        </section>
      )}

      <ApprovalModal pkg={pending} onCancel={() => setPending(null)} onApprove={() => { setApproved(pending?.title ?? null); setPending(null); }} />
    </div>
  );
}

export default function RunPage() {
  return <Suspense fallback={<p className="text-muted">Loading run…</p>}><RunScreen /></Suspense>;
}
