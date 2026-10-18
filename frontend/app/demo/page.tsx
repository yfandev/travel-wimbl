"use client";
import { useCallback, useEffect, useState } from "react";
import { Alerts, ChecksList, Decisions } from "@/components/DonePanel";
import { CandidateCard, EvidenceRow } from "@/components/Evidence";
import { FamilyTree } from "@/components/FamilyTree";
import { Assumption, CheckBadge, Chip, Micro, SourceLink, formatTime, money } from "@/components/ui";
import { discoverTrip, getAblation, getN1, getRun, getRunRecords } from "@/lib/api";
import { parseGoal } from "@/lib/goal";
import { MOCK_RUN } from "@/lib/mock";
import { ROUTES } from "@/lib/routing";
import type { MemoryAblation, N1Report, Run, RunRecord } from "@/lib/types";
import { foldRun, isScripted, usePrefersReducedMotion } from "@/lib/useRunReplay";
import { useTimeline } from "@/lib/useTimeline";

const DEMO_GOAL = "See Barcelona at the Camp Nou in March, under $2,500 from SFO";
/** One agent per beat when step 2 replays a live run's order. A presentation pace, not a measured duration. */
const REVEAL_MS = 700;

/** Four beats. `from`/`to` are windows of the sample run's scripted timeline; a live run is shown complete at each beat. */
const STEPS = [
  { key: "goal", label: "Goal", from: 0, to: 2200, title: "One line in. No questionnaire.", caption: "WIMBL infers safe defaults, labels every assumption, and freezes executable checks before it searches." },
  { key: "family", label: "Family", from: 2200, to: 8600, title: "The family goes to work.", caption: "The controller runs discovery under the Football Parent's lineage. Every source comes from You.com, with the time it was observed." },
  { key: "verify", label: "Verify", from: 8600, to: 14600, title: "Done means done.", caption: "An independent verifier checks the result against the frozen criteria. The controller acts on what fails, and never relaxes a check." },
  { key: "result", label: "Result", from: 14600, to: 15000, title: "A sourced result, with receipts.", caption: "Every claim links to its source. The Shared Brain and N+1 numbers are measured, with their sample sizes. Nothing is booked." },
] as const;

/** `recorded` is set when the demo shows a run recorded earlier instead of one planned just now. */
type Live = { run: Run; ablation: MemoryAblation | null; n1: N1Report | null; records: RunRecord[]; recorded: boolean };

let started: Promise<Live> | null = null; // one run per page load, even under React's dev double-effects

async function withContext(run: Run | null, recorded: boolean): Promise<Live> {
  if (!run) throw new Error("No recorded run is available.");
  const [ablation, n1, records] = await Promise.all([getAblation(), getN1(), getRunRecords()]);
  return { run, ablation, n1, records, recorded };
}

/** Plans the demo goal live. `?run=<id>` shows that recorded run instead; if live planning fails while the API is
 *  up (no You.com key, You.com error), the newest recorded run is shown, labelled as recorded. */
async function startLive(pinned: string | null): Promise<Live> {
  if (pinned) return withContext(await getRun(pinned), true);
  try {
    const result = await discoverTrip(parseGoal(DEMO_GOAL).request);
    return await withContext(await getRun(result.run_id), false);
  } catch (e) {
    if (/isn't reachable/.test((e as Error).message)) throw e;
    console.warn("[wimbl] live planning failed; showing the newest recorded run", e);
    return withContext(await getRun("latest"), true);
  }
}

export default function DemoPage() {
  const [live, setLive] = useState<Live | null>(null);
  const [sample, setSample] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const reduced = usePrefersReducedMotion();
  const parsed = parseGoal(DEMO_GOAL);

  useEffect(() => {
    started ??= startLive(new URLSearchParams(window.location.search).get("run"));
    started.then(setLive).catch(async (e: Error) => {
      started = null;
      setError(e.message);
      if (/isn't reachable/.test(e.message)) setSample(await getRun(MOCK_RUN.run_id)); // API down: labelled sample run
    });
  }, []);

  const run = live?.run ?? sample;
  const scripted = isScripted(run);
  const s = STEPS[step];
  const elapsed = useTimeline(scripted ? s.from : 1e9, scripted ? s.to : 1e9, reduced || !scripted);

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

  const view = run ? foldRun(run, elapsed) : null;
  // A live run records no per-agent timings, so step 2 reveals its agents in the order the run used them (the backend
  // lists them in that order), and the newest one that ran code glows. No durations are invented.
  const agentCount = view?.agents.length ?? 0;
  const reveal = useTimeline(0, agentCount * REVEAL_MS, reduced || scripted || s.key !== "family");
  const revealed = view && !scripted ? view.agents.slice(0, Math.min(agentCount, Math.floor(reveal / REVEAL_MS) + 1)) : view?.agents ?? [];
  const newest = revealed.at(-1);
  const revealActive = !scripted && reveal < agentCount * REVEAL_MS && newest && newest.executed !== false ? newest.id : null;
  const childRan = view?.agents.some((a) => a.role === "tickets") ?? false;
  const waiting = <p role="status" className="text-muted">{error ?? "Searching You.com and checking official pages…"}</p>;
  const returnedModels = [...new Set((live?.records ?? []).filter((r) => r.status === "ok").map((r) => r.model_id_returned).filter(Boolean))] as string[];

  return (
    <div className="flex min-h-[calc(100vh-12rem)] flex-col">
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
        <p className="hidden items-center gap-3 text-sm text-muted sm:flex">
          {live && !live.recorded && <Chip tone="pitch">Live · You.com · {((live.run.elapsed_ms ?? 0) / 1000).toFixed(1)} s</Chip>}
          {live?.recorded && <Chip tone="rust">Recorded run{live.run.started_at && <> · {formatTime(live.run.started_at)}</>}</Chip>}
          {sample && <Chip tone="rust">Sample run</Chip>}
          <span><kbd className="rounded border border-line px-1.5 py-0.5 font-mono text-xs">←</kbd>{" "}<kbd className="rounded border border-line px-1.5 py-0.5 font-mono text-xs">→</kbd> to move</span>
        </p>
      </nav>
      <div className="mt-3 h-px bg-line">
        <div className="h-px bg-gold transition-[width] duration-300" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </div>

      <header className="mt-8 max-w-3xl" aria-live="polite">
        <p className="text-micro font-medium uppercase text-muted">Step {step + 1} of {STEPS.length}</p>
        <h1 key={s.key} className="rise mt-3 text-[2rem] font-semibold leading-tight tracking-tight sm:text-h1">{s.title}</h1>
        <p className="mt-4 text-lg text-muted">{s.caption}</p>
      </header>

      <div key={s.key} className="rise mt-10 flex-1">
        {s.key === "goal" && (
          <div className="space-y-10">
            <blockquote className="rounded-lg border border-line px-6 py-5 text-xl font-medium sm:text-2xl">&ldquo;{DEMO_GOAL}&rdquo;</blockquote>
            <div className="grid gap-10 md:grid-cols-[1fr_1fr_1.4fr]">
              <section>
                <h2 className="text-micro font-medium uppercase text-muted">What was asked</h2>
                <ul className="mt-3 space-y-1.5">{(sample ? sample.constraints : parsed.stated).map((c) => <li key={c}>{c}</li>)}</ul>
              </section>
              <section>
                <h2 className="text-micro font-medium uppercase text-muted">Assumed, not asked</h2>
                <ul className="mt-3 space-y-1.5">{(sample ? sample.assumptions : parsed.assumptions).map((a) => <Assumption key={a}>{a}</Assumption>)}</ul>
                <p className="mt-3 text-sm text-muted">0 questions asked</p>
              </section>
              <section>
                <h2 className="flex flex-wrap items-center gap-2 text-micro font-medium uppercase text-muted">
                  Frozen checks {run && <span className="font-mono normal-case tracking-normal">{run.criteria_hash}</span>}
                </h2>
                {run ? (
                  <ul className="mt-3 space-y-2">
                    {run.checks.map((c) => <li key={c.check_id} className="flex justify-between gap-4 text-sm"><span>{c.description}</span><CheckBadge status="pending" /></li>)}
                  </ul>
                ) : <div className="mt-3">{waiting}</div>}
              </section>
            </div>
          </div>
        )}

        {s.key === "family" && (!run || !view ? waiting : (
          <div className="grid gap-10 lg:grid-cols-[1fr_22rem]">
            <div>
              <FamilyTree agents={scripted ? view.agents : revealed} activeId={scripted ? view.activeId : revealActive} facts={view.facts} elapsed={view.elapsed} />
              {!scripted && (
                <p className="mt-3 text-xs text-muted">
                  Agents appear in the order this run used them, not to scale. Dashed parents are lineage only.
                  {childRan ? " The tickets agent read the You.com facts on NVIDIA Nemotron, served by Crusoe." : " No trip children ran on this run."}
                </p>
              )}
            </div>
            <section>
              {scripted ? (
                <>
                  <h2 className="text-micro font-medium uppercase text-muted">Shared trip board</h2>
                  <ul className="mt-3 space-y-4">
                    {view.facts.map((f) => <li key={f.key} className="rise"><p className="font-medium">{f.value}</p><p className="font-mono text-xs text-muted">{f.from_agent} → {f.to_agents.join(", ")}</p></li>)}
                  </ul>
                  {view.alerts.length > 0 && <div className="mt-6"><Alerts alerts={view.alerts} /></div>}
                </>
              ) : (
                <>
                  <h2 className="text-micro font-medium uppercase text-muted">Evidence ledger · You.com</h2>
                  <ul className="mt-1 divide-y divide-line">
                    {(run.evidence_ledger ?? []).map((e, i) => (
                      <EvidenceRow key={e.url} e={e} compact className="rise" style={{ animationDelay: `${i * 120}ms` }} />
                    ))}
                  </ul>
                </>
              )}
            </section>
          </div>
        ))}

        {s.key === "verify" && (!run || !view ? waiting : (
          <div className="grid gap-10 lg:grid-cols-[1.3fr_1fr]">
            <ChecksList checks={view.checks} hash={run.criteria_hash} compact />
            <div className="space-y-8">
              {!scripted && run.findings && run.findings.length > 0 && (
                <section>
                  <Micro>Verifier findings</Micro>
                  <ul className="mt-3 space-y-2">
                    {run.findings.map((f) => (
                      <li key={f.code} className={`text-sm ${f.severity === "error" ? "text-red" : "text-rust"}`}><span className="font-mono text-xs font-semibold">{f.code}</span> · {f.message}</li>
                    ))}
                  </ul>
                </section>
              )}
              <Decisions decisions={view.decisions} />
            </div>
          </div>
        ))}

        {s.key === "result" && (!run || !view ? waiting : (
          <div className="grid gap-10 lg:grid-cols-[1.6fr_1fr]">
            {scripted ? <SamplePackage view={view} /> : run.trip_result?.candidates[0]
              ? <CandidateCard c={run.trip_result.candidates[0]} />
              : <p className="text-muted">No candidates. The controller decided to {run.trip_result?.controller_decision}.</p>}
            <aside className="space-y-8">
              {live?.ablation?.primary_delta != null && (
                <section>
                  <Micro>Shared Brain, measured</Micro>
                  <p className="mt-2 text-3xl font-semibold tabular-nums">+{live.ablation.primary_delta.toFixed(2)}</p>
                  <p className="text-sm">held-out target-check pass rate with memory on</p>
                  <p className="mt-1 text-xs text-muted">
                    {live.ablation.primary_ci95 && <>95% CI {live.ablation.primary_ci95[0].toFixed(2)} to {live.ablation.primary_ci95[1].toFixed(2)} · </>}
                    {live.ablation.n && <>n = {live.ablation.n.off} / {live.ablation.n.on} runs</>}
                  </p>
                  {live.ablation.caveat && <p className="mt-1 text-xs text-rust">⚠ {live.ablation.caveat}</p>}
                </section>
              )}
              {live?.n1?.decision && (
                <section>
                  <Micro>Version N+1</Micro>
                  <p className={`mt-2 font-semibold ${live.n1.decision === "promoted" ? "text-pitch" : "text-red"}`}>{live.n1.decision === "promoted" ? "✓ Promoted" : "✕ Rejected"}</p>
                  <p className="text-sm text-muted">{live.n1.decision_reason}</p>
                </section>
              )}
              <section>
                <Micro>Models</Micro>
                {returnedModels.length ? (
                  <>
                    <p className="mt-2 text-sm">WIMBL runs NVIDIA Nemotron, served by Crusoe Managed Inference. Returned in the run log:</p>
                    <ul className="mt-2 space-y-1">{returnedModels.map((m) => <li key={m}><code className="break-all font-mono text-xs">{m}</code></li>)}</ul>
                  </>
                ) : (
                  <ul className="mt-2 space-y-2 text-sm">
                    {ROUTES.map((r) => <li key={r.role}><span className="capitalize text-muted">{r.role}</span> (requested)<code className="block break-all font-mono text-xs">{r.requested}</code></li>)}
                  </ul>
                )}
              </section>
            </aside>
          </div>
        ))}
      </div>

      <div className="mt-10 flex justify-between">
        <button type="button" onClick={() => go(-1)} disabled={step === 0} className="rounded-lg border border-line px-4 py-2.5 text-sm hover:border-forest disabled:invisible">Back</button>
        <button type="button" onClick={() => go(1)} disabled={step === STEPS.length - 1} className="rounded-lg bg-gold px-5 py-2.5 text-sm font-semibold text-forest hover:bg-[#b8931f] disabled:invisible">
          Next: {STEPS[Math.min(step + 1, STEPS.length - 1)].label}
        </button>
      </div>
    </div>
  );
}

/** The sample run's top package (used only when the API is down). */
function SamplePackage({ view }: { view: ReturnType<typeof foldRun> }) {
  const top = view.packages[0];
  if (!top) return null;
  return (
    <article className="rounded-lg border border-line p-6 sm:p-8">
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0"><h2 className="text-h2 font-semibold">{top.title}</h2><p className="mt-1 text-sm text-muted">{top.match} · {top.kickoff}</p></div>
        <div className="shrink-0 text-right"><p className="text-3xl font-semibold tabular-nums">{money(top.items.reduce((n, i) => n + (i.price ?? 0), 0), top.currency)}</p><p className="text-xs text-muted">sum of line items</p></div>
      </div>
      <ul className="mt-6 divide-y divide-line">
        {top.items.map((i) => (
          <li key={i.kind} className="flex justify-between gap-4 py-3">
            <span><span className="block">{i.label}</span><SourceLink url={i.source_url} observedAt={i.observed_at} /></span>
            <span className="tabular-nums">{i.price == null ? "—" : money(i.price, top.currency)}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}
