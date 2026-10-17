"use client";
import { useEffect, useState } from "react";
import { Card, Chip, Micro, NotYetRun } from "@/components/ui";
import { getN1 } from "@/lib/api";
import type { EvalScore, N1Report } from "@/lib/types";

const fmt = (s: EvalScore | null) => (s == null ? <NotYetRun /> : <span className="tabular-nums">{s.mean.toFixed(2)} <span className="text-muted">± {s.spread.toFixed(2)} · n={s.runs}</span></span>);

export default function LabPage() {
  const [r, setR] = useState<N1Report | null | undefined>(undefined);
  useEffect(() => { getN1().then(setR); }, []);
  if (r === undefined) return <p className="text-muted">Loading…</p>;
  if (r === null) return (
    <div className="max-w-xl">
      <h1 className="text-h1 font-semibold">Version N+1 lab</h1>
      <p className="mt-3"><NotYetRun />. No gate decision has been recorded.</p>
    </div>
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-h1 font-semibold">Version N+1 lab</h1>
        <p className="mt-2 max-w-2xl text-muted">One isolated change at a time, evaluated against baseline on fixed benchmark scenarios and on held-out scenarios it was never tuned on, 3 runs each.</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <Micro>Candidate · {r.change.target.replace("_", " ")}</Micro>
          <h2 className="mt-2 text-h2 font-semibold">{r.candidate_version}</h2>
          <p className="mt-2">{r.change.summary}</p>
          <p className="mt-3 text-sm text-muted"><span className="font-medium text-forest">Hypothesis:</span> {r.change.hypothesis}</p>
        </Card>
        <Card>
          <Micro>Promotion gate · fixed before evaluation</Micro>
          <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm">{r.gate.map((g) => <li key={g}>{g}</li>)}</ol>
        </Card>
      </div>

      <Card>
        <h2 className="text-h2 font-semibold">Baseline vs candidate</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="text-left text-micro uppercase text-muted">
                <th className="pb-3 font-medium">Metric</th><th className="pb-3 font-medium">Split</th>
                <th className="pb-3 font-medium">Baseline · {r.baseline_version}</th>
                <th className="pb-3 font-medium">Candidate · {r.candidate_version}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {r.metrics.map((m) => (
                <tr key={m.name + m.split}>
                  <th scope="row" className="py-3 pr-3 text-left font-medium">{m.name}{m.lower_is_better && <span className="ml-1 text-xs font-normal text-muted">(lower is better)</span>}</th>
                  <td className="py-3 pr-3">{m.split === "heldout" ? <Chip tone="pale-gold">held-out</Chip> : <Chip>benchmark</Chip>}</td>
                  <td className="py-3 pr-3">{fmt(m.baseline)}</td>
                  <td className="py-3">{fmt(m.candidate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-6 rounded-lg bg-mist p-4">
          <Micro>Decision</Micro>
          {r.decision == null ? (
            <p className="mt-1 text-sm"><NotYetRun />. No promotion is made until the evaluation runs.</p>
          ) : (
            <p className="mt-1 text-sm">
              <span className={`font-semibold ${r.decision === "promoted" ? "text-pitch" : "text-red"}`}>{r.decision === "promoted" ? "✓ Promoted" : "✕ Rejected"}</span>
              {r.decision_reason && <span> · {r.decision_reason}</span>}
            </p>
          )}
          {r.caveat && <p className="mt-2 text-xs text-rust">⚠ {r.caveat}</p>}
          {r.evaluator && <p className="mt-1 text-xs text-muted">Evaluator: {r.evaluator}{r.report && <> · <span className="font-mono">{r.report}</span></>}</p>}
        </div>
      </Card>

      <Card>
        <h2 className="text-h2 font-semibold">Version history</h2>
        <ol className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-stretch">
          {r.history.map((h) => (
            <li key={h.version} className={`flex-1 rounded-lg border p-3 ${h.status === "active" ? "border-gold bg-pale-gold" : "border-line"}`}>
              <p className="text-sm font-semibold">{h.version}</p>
              <p className="mt-1 text-sm">{h.note}</p>
              <p className="mt-1 text-xs text-muted">{h.at.slice(0, 10)} · {h.status.replace("_", " ")}</p>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-xs text-muted">Every version is tagged; rolling back restores the previous parent version and its lessons.</p>
      </Card>
    </div>
  );
}
