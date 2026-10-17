import type { ReactNode } from "react";
import type { CheckStatus } from "@/lib/types";

export function Micro({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <p className={`text-micro font-medium uppercase text-muted ${className}`}>{children}</p>;
}

export function Card({ children, className = "", as: Tag = "section" }: { children: ReactNode; className?: string; as?: "section" | "article" | "div" }) {
  return <Tag className={`rounded-lg border border-line bg-white p-6 sm:p-8 ${className}`}>{children}</Tag>;
}

const CHECK_STYLE: Record<CheckStatus, { icon: string; word: string; cls: string }> = {
  passed: { icon: "✓", word: "Passed", cls: "text-pitch" },
  failed: { icon: "✕", word: "Failed", cls: "text-red" },
  pending: { icon: "…", word: "Pending", cls: "text-muted" },
};

/** Status is always icon + word, never colour alone. */
export function CheckBadge({ status }: { status: CheckStatus }) {
  const s = CHECK_STYLE[status];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 text-sm font-medium ${s.cls}`}>
      <span aria-hidden="true">{s.icon}</span>
      {s.word}
    </span>
  );
}

export function Chip({ children, tone = "mist" }: { children: ReactNode; tone?: "mist" | "pale-gold" | "pitch" | "rust" | "red" }) {
  const tones = {
    mist: "bg-mist text-forest",
    "pale-gold": "bg-pale-gold text-forest",
    pitch: "bg-pitch/10 text-pitch",
    rust: "bg-rust/10 text-rust",
    red: "bg-red/10 text-red",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-micro font-medium ${tones[tone]}`}>{children}</span>;
}

export function Assumption({ children }: { children: ReactNode }) {
  return (
    <li className="flex gap-2 text-sm text-rust">
      <span aria-hidden="true">⚠</span>
      <span><span className="sr-only">Assumption: </span>{children}</span>
    </li>
  );
}

export function NotYetRun() {
  return <span className="text-sm italic text-muted">not yet run</span>;
}

export function SourceLink({ url, observedAt }: { url: string | null; observedAt: string | null }) {
  if (!url) return <span className="text-sm text-red">No source</span>;
  return (
    <span className="text-sm">
      <a href={url} target="_blank" rel="noopener noreferrer" className="text-pitch underline decoration-pitch/30 underline-offset-2 hover:decoration-pitch">
        source<span className="sr-only"> (opens in new tab)</span>
      </a>
      {observedAt && <span className="text-muted"> · observed {formatTime(observedAt)}</span>}
    </span>
  );
}

export function formatTime(iso: string) {
  return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC", hour12: false }) + " UTC";
}

export const money = (n: number, currency = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(n);
