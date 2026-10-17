"use client";
import { useEffect, useMemo, useState } from "react";
import { Card, Micro, NotYetRun } from "@/components/ui";
import { getRunRecords } from "@/lib/api";
import { ROUTES } from "@/lib/routing";
import type { RunRecord } from "@/lib/types";

const median = (xs: number[]) => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b), m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

export default function ModelPage() {
  const [records, setRecords] = useState<RunRecord[] | null>(null);
  useEffect(() => { getRunRecords().then(setRecords); }, []);

  // Only real model calls count; "demo" rows mean no call was made.
  const real = useMemo(() => (records ?? []).filter((r) => r.status !== "demo"), [records]);
  const byRole = useMemo(() => {
    const m = new Map<string, RunRecord[]>();
    for (const r of real) m.set(r.agent_role, [...(m.get(r.agent_role) ?? []), r]);
    return [...m.entries()];
  }, [real]);
  const returnedIds = [...new Set(real.map((r) => r.model_id_returned).filter(Boolean))] as string[];

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-h1 font-semibold">Nemotron panel</h1>
        <p className="mt-3 max-w-3xl text-lg">
          WIMBL runs NVIDIA Nemotron{" "}
          {returnedIds.length ? returnedIds.map((id, i) => <span key={id}>{i > 0 && ", "}<code className="font-mono text-base">{id}</code></span>) : <span className="text-muted">[model IDs appear here from run logs]</span>},
          served by Crusoe Managed Inference.
        </p>
      </header>

      <Card>
        <h2 className="text-h2 font-semibold">Routing by role</h2>
        <p className="mt-1 text-sm text-muted">What WIMBL requests, from <code className="font-mono">wimbl/integrations/models.py</code>. The returned ID below is the source of truth.</p>
        <ul className="mt-4 divide-y divide-line">
          {ROUTES.map((r) => (
            <li key={r.role} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-baseline sm:justify-between">
              <span className="font-medium capitalize">{r.role}</span>
              <span className="text-right">
                <code className="break-all font-mono text-sm">{r.requested}</code>
                {r.note && <span className="block text-xs text-muted">{r.note}</span>}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <h2 className="text-h2 font-semibold">From the run logs</h2>
        {records && !real.length ? (
          <p className="mt-3 text-sm"><NotYetRun />. No model calls are recorded in the run log this screen reads.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm">
              <thead>
                <tr className="text-left text-micro uppercase text-muted">
                  <th className="pb-3 font-medium">Role</th><th className="pb-3 font-medium">Model returned</th>
                  <th className="pb-3 text-right font-medium">Calls</th><th className="pb-3 text-right font-medium">Tokens</th>
                  <th className="pb-3 text-right font-medium">p50 ms</th><th className="pb-3 text-right font-medium">Errors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {byRole.map(([role, rs]) => (
                  <tr key={role}>
                    <th scope="row" className="py-2.5 pr-3 text-left font-medium">{role}</th>
                    <td className="py-2.5 pr-3 font-mono text-xs">{[...new Set(rs.map((r) => r.model_id_returned ?? "—"))].join(", ")}</td>
                    <td className="py-2.5 text-right tabular-nums">{rs.length}</td>
                    <td className="py-2.5 text-right tabular-nums">{rs.reduce((n, r) => n + (r.input_tokens ?? 0) + (r.output_tokens ?? 0), 0).toLocaleString()}</td>
                    <td className="py-2.5 text-right tabular-nums">{median(rs.flatMap((r) => (r.latency_ms == null ? [] : [r.latency_ms])))?.toLocaleString() ?? "—"}</td>
                    <td className="py-2.5 text-right tabular-nums">{rs.filter((r) => r.status !== "ok").length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <Micro>Cost per verified success</Micro>
        <p className="mt-2 text-sm"><NotYetRun />. It needs verified-package counts from the controller, which aren&rsquo;t connected yet.</p>
        <p className="mt-2 text-xs text-muted">Cost estimates exist only for Super and use a third-party price estimate, not Crusoe&rsquo;s pricing page.</p>
      </Card>
    </div>
  );
}
