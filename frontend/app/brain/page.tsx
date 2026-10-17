"use client";
import { useEffect, useMemo, useState } from "react";
import { Card, Chip, Micro, NotYetRun } from "@/components/ui";
import { getAblation, getLessons } from "@/lib/api";
import type { Lesson, MemoryAblation } from "@/lib/types";

const EVAL_TONE = { promoted: "pitch", candidate: "pale-gold", rejected: "red" } as const;
const day = (iso: string | null) => (iso ? iso.slice(0, 10) : "—");

function WeightBar({ weight }: { weight: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-line" aria-hidden="true">
        <div className="h-full bg-pitch" style={{ width: `${Math.round((weight / 2) * 100)}%` }} />
      </div>
      <span className="font-mono text-xs">weight {weight.toFixed(2)} / 2</span>
    </div>
  );
}

export default function BrainPage() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [ablation, setAblation] = useState<MemoryAblation | null>(null);
  const [scope, setScope] = useState<"all" | "football" | "sports">("all");

  useEffect(() => { getLessons().then(setLessons); getAblation().then(setAblation); }, []);

  const shown = useMemo(() => lessons.filter((l) => scope === "all" || l.scope === scope || l.scope.startsWith(`${scope}.`)).sort((a, b) => b.weight - a.weight), [lessons, scope]);
  const conflicts = lessons.filter((l) => l.status === "superseded" && l.superseded_by);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-h1 font-semibold">Shared Brain</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Every agent reads the lessons scoped to its lineage before working and proposes new ones after. Weight is bounded:
          lineage relevance × smoothed success × validation × recency, so raw trip counts can&rsquo;t dominate.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-labelledby="lessons">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="lessons" className="text-h2 font-semibold">Lessons</h2>
            <div role="group" aria-label="Filter by scope" className="flex gap-1 rounded-lg bg-mist p-1 text-sm">
              {(["all", "football", "sports"] as const).map((s) => (
                <button key={s} type="button" aria-pressed={scope === s} onClick={() => setScope(s)}
                  className={`rounded-md px-3 py-1 capitalize ${scope === s ? "bg-white font-medium shadow-sm" : "text-muted hover:text-forest"}`}>{s}</button>
              ))}
            </div>
          </div>
          <ul className="mt-4 space-y-3">
            {shown.map((l) => (
              <li key={l.lesson_id}>
                <Card as="article" className={l.status !== "active" ? "opacity-60" : ""}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-semibold">{l.lesson_id}</span>
                    <Chip tone={EVAL_TONE[l.evaluation_status]}>{l.evaluation_status}</Chip>
                    {l.status !== "active" && <Chip tone={l.status === "conflict" ? "rust" : "mist"}>{l.status}</Chip>}
                    <span className="font-mono text-xs text-muted">{l.scope} · {l.topic} · since v{l.version_introduced}</span>
                  </div>
                  <p className="mt-2">{l.lesson}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                    <WeightBar weight={l.weight} />
                    <span className="text-muted">{l.trips_validated} trips · {l.successes}✓ {l.failures}✕</span>
                    <span className="text-muted">validated {day(l.last_validated)} · expires {day(l.expires_at)}</span>
                  </div>
                  <details className="mt-3 text-sm">
                    <summary className="cursor-pointer text-pitch">Provenance ({l.evidence_urls.length} source{l.evidence_urls.length === 1 ? "" : "s"}, {l.source_type})</summary>
                    <ul className="mt-2 space-y-1 pl-4">
                      {l.evidence_urls.map((u) => (
                        <li key={u}><a href={u} target="_blank" rel="noopener noreferrer" className="break-all text-pitch underline underline-offset-2">{u}</a></li>
                      ))}
                    </ul>
                    <p className="mt-2 text-muted">From {l.from_agent} · confidence {l.confidence.toFixed(2)}{l.run_id && <> · run <span className="font-mono">{l.run_id}</span></>}{l.supersedes && <> · supersedes <span className="font-mono">{l.supersedes}</span></>}</p>
                  </details>
                </Card>
              </li>
            ))}
          </ul>
        </section>

        <aside className="space-y-6">
          <Card>
            <h2 className="font-semibold">Memory off vs on</h2>
            <p className="mt-1 text-xs text-muted">Same benchmark scenarios, measured from run logs.</p>
            {ablation && ablation.metrics.every((m) => m.memory_off == null && m.memory_on == null) ? (
              <p className="mt-4 text-sm"><NotYetRun />. The benchmark with memory off vs on hasn&rsquo;t been run, so no gain is shown.</p>
            ) : (
            <table className="mt-4 w-full text-sm">
              <thead><tr className="text-left text-micro uppercase text-muted"><th className="pb-2 font-medium">Metric</th><th className="pb-2 font-medium">Off</th><th className="pb-2 font-medium">On</th></tr></thead>
              <tbody className="divide-y divide-line">
                {ablation?.metrics.map((m) => (
                  <tr key={m.name}>
                    <th scope="row" className="py-2 pr-2 text-left font-normal">{m.name}</th>
                    <td className="py-2 pr-2">{m.memory_off == null ? <NotYetRun /> : `${m.memory_off} ${m.unit}`}</td>
                    <td className="py-2">{m.memory_on == null ? <NotYetRun /> : `${m.memory_on} ${m.unit}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            )}
          </Card>
          <Card>
            <h2 className="font-semibold">Conflicts resolved</h2>
            {!conflicts.length && <p className="mt-2 text-sm text-muted">None.</p>}
            <ul className="mt-3 space-y-3 text-sm">
              {conflicts.map((l) => (
                <li key={l.lesson_id}>
                  <span className="font-mono">{l.lesson_id}</span> superseded by <span className="font-mono">{l.superseded_by}</span>
                  <p className="text-xs text-muted">Kept the better-supported lesson; both are never active together.</p>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <Micro>Never weighted</Micro>
            <p className="mt-2 text-sm">Hard user constraints and safety rules aren&rsquo;t lessons. No lesson can override them.</p>
          </Card>
        </aside>
      </div>
    </div>
  );
}
