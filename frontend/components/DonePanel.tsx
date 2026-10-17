import type { AcceptanceCheck, ControllerDecision, MonitorAlert } from "@/lib/types";
import { CheckBadge, Micro, formatTime } from "./ui";

export function ChecksList({ checks, hash }: { checks: AcceptanceCheck[]; hash: string }) {
  const passed = checks.filter((c) => c.status === "passed").length;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-h2 font-semibold">Definition of done</h2>
        <span className="text-sm text-muted" aria-live="polite">{passed}/{checks.length} passed</span>
      </div>
      <p className="mt-1 text-sm text-muted">
        Frozen at run start · <span className="font-mono">{hash}</span> · never relaxed after a failure
      </p>
      <ul className="mt-4 divide-y divide-line">
        {checks.map((c) => (
          <li key={c.check_id} className="flex items-start justify-between gap-4 py-3">
            <div className="min-w-0">
              <p className="text-sm font-medium">{c.description}</p>
              <p className="mt-0.5 font-mono text-xs text-muted">{c.check_id}</p>
              {c.detail && <p className={`mt-1 text-sm ${c.status === "failed" ? "text-red" : "text-muted"}`}>{c.detail}</p>}
            </div>
            <CheckBadge status={c.status} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Alerts({ alerts }: { alerts: MonitorAlert[] }) {
  if (!alerts.length) return <p className="text-sm text-muted">No drift or loops detected.</p>;
  return (
    <ul className="space-y-2">
      {alerts.map((a, i) => (
        <li key={i} className="rise flex gap-2 rounded-lg bg-rust/5 px-3 py-2 text-sm text-rust">
          <span aria-hidden="true">{a.kind === "loop" ? "⟳" : "⚠"}</span>
          <span><strong className="font-semibold">{a.kind === "loop" ? "Loop" : "Drift"}:</strong> {a.message}</span>
        </li>
      ))}
    </ul>
  );
}

const DECISION_STYLE = { continue: "text-forest", replan: "text-rust", stop: "text-pitch", escalate: "text-red" } as const;

export function Decisions({ decisions }: { decisions: ControllerDecision[] }) {
  return (
    <div>
      <Micro>Controller decisions</Micro>
      {!decisions.length && <p className="mt-2 text-sm text-muted">None yet.</p>}
      <ol className="mt-2 space-y-3">
        {decisions.map((d, i) => (
          <li key={i} className="rise border-l-2 border-line pl-3">
            <p className="text-sm">
              <span className={`font-mono text-xs font-semibold uppercase ${DECISION_STYLE[d.decision]}`}>{d.decision}</span>
              <span className="ml-2 text-xs text-muted">{formatTime(d.at)} · {d.stage.toLowerCase()}</span>
            </p>
            <p className="mt-0.5 text-sm">{d.reason}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
