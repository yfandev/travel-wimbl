"use client";
import { useCallback, useEffect, useState } from "react";
import { Alerts, ChecksList, Decisions } from "@/components/DonePanel";
import { FamilyTree } from "@/components/FamilyTree";
import { Assumption, CheckBadge, Chip, SourceLink, money } from "@/components/ui";
import { getRun } from "@/lib/api";
import { ROUTES } from "@/lib/routing";
import type { Run } from "@/lib/types";
import { foldRun, usePrefersReducedMotion } from "@/lib/useRunReplay";
import { useTimeline } from "@/lib/useTimeline";

/** Four beats, each a window of the run's event timeline (ms). The last window ends after the final event. */
const STEPS = [
  { key: "goal", label: "Goal", from: 0, to: 2200, title: "One line in. No questionnaire.", caption: "WIMBL infers safe defaults, labels every assumption, and freezes executable checks before it searches." },
  { key: "family", label: "Family", from: 2200, to: 8600, title: "A family of agents, working in parallel.", caption: "Children spawn from the Football Parent with inherited lessons, and share facts with their siblings as they find them." },
  { key: "verify", label: "Verify", from: 8600, to: 14600, title: "Done means done.", caption: "An independent verifier fails an unsourced ticket claim. The controller replans within budget until every frozen check passes." },
  { key: "result", label: "Result", from: 14600, to: 15000, title: "A verified trip, with receipts.", caption: "Every price links to its source and observation time. Nothing is booked without the traveler's approval." },
] as const;

export default function DemoPage() {
  const [run, setRun] = useState<Run | null>(null);
  const [step, setStep] = useState(0);
  const reduced = usePrefersReducedMotion();
  const s = STEPS[step];
  const elapsed = useTimeline(s.from, s.to, reduced);

  useEffect(() => { getRun("mock-run-0001").then(setRun); }, []);

  const go = useCallback((d: number) => setStep((i) => Math.min(STEPS.length - 1, Math.max(0, i + d))), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof Element && e.target.closest("input, textarea, select, [contenteditable=true]");
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (["ArrowRight", "PageDown"].includes(e.key)) { e.preventDefault(); go(1); }
      if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); go(-1); }
      if (e.key === "Home") setStep(0);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  if (!run) return <p className="text-muted">Loading…</p>;
  const view = foldRun(run, elapsed);
  const top = view.packages[0];
  const cited = view.agents.find((a) => a.role === "tickets")?.inherited[0];

  return (
    <div className="flex min-h-[calc(100vh-12rem)] flex-col">
      {/* Step rail */}
      <nav aria-label="Demo steps" className="flex items-center justify-between gap-4">
        <ol className="flex gap-1 sm:gap-2">
          {STEPS.map((x, i) => (
            <li key={x.key}>
              <button type="button" onClick={() => setStep(i)} aria-current={i === step ? "step" : undefined}
                className={`rounded-md px-2.5 py-1.5 text-sm sm:px-3 ${i === step ? "bg-pale-gold font-medium text-forest" : i < step ? "text-forest" : "text-muted hover:text-forest"}`}>
                <span className="font-mono text-xs">{i + 1}</span> {x.label}
              </button>
            </li>
          ))}
        </ol>
        <p className="hidden text-sm text-muted sm:block">
          <kbd className="rounded border border-line px-1.5 py-0.5 font-mono text-xs">←</kbd>{" "}
          <kbd className="rounded border border-line px-1.5 py-0.5 font-mono text-xs">→</kbd> to move
        </p>
      </nav>
      <div className="mt-3 h-px bg-line">
        <div className="h-px bg-gold transition-[width] duration-300" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </div>

      {/* Beat */}
      <header className="mt-8 max-w-3xl" aria-live="polite">
        <p className="text-micro font-medium uppercase text-muted">Step {step + 1} of {STEPS.length}</p>
        <h1 key={s.key} className="rise mt-3 text-[2rem] font-semibold leading-tight tracking-tight sm:text-h1">{s.title}</h1>
        <p className="mt-4 text-lg text-muted">{s.caption}</p>
      </header>

      <div key={s.key} className="rise mt-10 flex-1">
        {s.key === "goal" && (
          <div className="space-y-10">
            <blockquote className="rounded-lg border border-line px-6 py-5 text-xl font-medium sm:text-2xl">
              &ldquo;{run.goal}&rdquo;
            </blockquote>
            <div className="grid gap-10 md:grid-cols-[1fr_1fr_1.4fr]">
              <section>
                <h2 className="text-micro font-medium uppercase text-muted">Hard constraints</h2>
                <ul className="mt-3 space-y-1.5">{run.constraints.map((c) => <li key={c}>{c}</li>)}</ul>
              </section>
              <section>
                <h2 className="text-micro font-medium uppercase text-muted">Inferred defaults</h2>
                <ul className="mt-3 space-y-1.5">{run.assumptions.map((a) => <Assumption key={a}>{a}</Assumption>)}</ul>
                <p className="mt-3 text-sm text-muted">0 questions asked</p>
              </section>
              <section>
                <h2 className="flex flex-wrap items-center gap-2 text-micro font-medium uppercase text-muted">
                  Frozen checks <span className="font-mono normal-case tracking-normal">{run.criteria_hash}</span>
                </h2>
                <ul className="mt-3 space-y-2">
                  {view.checks.map((c) => <li key={c.check_id} className="flex justify-between gap-4 text-sm"><span>{c.description}</span><CheckBadge status={c.status} /></li>)}
                </ul>
              </section>
            </div>
          </div>
        )}

        {s.key === "family" && (
          <div className="grid gap-10 lg:grid-cols-[1fr_18rem]">
            <FamilyTree agents={view.agents} activeId={view.activeId} facts={view.facts} elapsed={view.elapsed} />
            <section>
              <h2 className="text-micro font-medium uppercase text-muted">Shared trip board</h2>
              <ul className="mt-3 space-y-4">
                {view.facts.map((f) => (
                  <li key={f.key} className="rise">
                    <p className="font-medium">{f.value}</p>
                    <p className="font-mono text-xs text-muted">{f.from_agent} → {f.to_agents.join(", ")}</p>
                  </li>
                ))}
              </ul>
              {view.alerts.length > 0 && <div className="mt-6"><Alerts alerts={view.alerts} /></div>}
            </section>
          </div>
        )}

        {s.key === "verify" && (
          <div className="grid gap-10 lg:grid-cols-[1.3fr_1fr]">
            <ChecksList checks={view.checks} hash={run.criteria_hash} compact />
            <Decisions decisions={view.decisions} />
          </div>
        )}

        {s.key === "result" && top && (
          <div className="grid gap-10 lg:grid-cols-[1.7fr_1fr]">
            <article className="rounded-lg border border-line p-6 sm:p-8">
              <div className="flex items-start justify-between gap-6">
                <div className="min-w-0">
                  <h2 className="text-h2 font-semibold">{top.title}</h2>
                  <p className="mt-1 text-sm text-muted">{top.match} · {top.kickoff}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-3xl font-semibold tabular-nums">{money(top.items.reduce((n, i) => n + (i.price ?? 0), 0), top.currency)}</p>
                  <p className="text-xs text-muted">estimated total, sum of line items</p>
                </div>
              </div>
              <ul className="mt-6 divide-y divide-line">
                {top.items.map((i) => (
                  <li key={i.kind} className="flex justify-between gap-4 py-3">
                    <span><span className="block">{i.label}</span><SourceLink url={i.source_url} observedAt={i.observed_at} /></span>
                    <span className="tabular-nums">{i.price == null ? "—" : money(i.price, top.currency)}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
                <Chip tone="pitch">✓ {view.checks.filter((c) => c.status === "passed").length}/{view.checks.length} checks passed</Chip>
                <span className="text-xs text-muted">Search results are evidence, not live inventory.</span>
              </div>
            </article>
            <aside className="space-y-8">
              {cited && (
                <section>
                  <h2 className="text-micro font-medium uppercase text-muted">Inherited, and cited</h2>
                  <p className="mt-3">
                    The tickets child repaired the ticket claim using <span className="font-mono text-sm">{cited.lesson_id}</span>, inherited from {cited.parent_version} (influence {cited.influence.toFixed(2)}).
                  </p>
                </section>
              )}
              <section>
                <h2 className="text-micro font-medium uppercase text-muted">Models requested</h2>
                <ul className="mt-3 space-y-2 text-sm">
                  {ROUTES.map((r) => (
                    <li key={r.role}><span className="capitalize text-muted">{r.role}</span><code className="block break-all font-mono text-xs">{r.requested}</code></li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-muted">NVIDIA Nemotron, served by Crusoe Managed Inference. Returned model IDs and costs come from run logs on the Nemotron screen.</p>
              </section>
            </aside>
          </div>
        )}
      </div>

      <div className="mt-10 flex justify-between">
        <button type="button" onClick={() => go(-1)} disabled={step === 0} className="rounded-lg border border-line px-4 py-2.5 text-sm hover:border-forest disabled:invisible">
          Back
        </button>
        <button type="button" onClick={() => go(1)} disabled={step === STEPS.length - 1} className="rounded-lg bg-gold px-5 py-2.5 text-sm font-semibold text-forest hover:bg-[#b8931f] disabled:invisible">
          Next: {STEPS[Math.min(step + 1, STEPS.length - 1)].label}
        </button>
      </div>
    </div>
  );
}
