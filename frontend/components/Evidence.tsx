import type { Evidence, TripCandidate } from "@/lib/types";
import { Assumption, Chip, Micro, formatTime, money } from "./ui";

export const host = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; } };
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }) : null);

/** One evidence-ledger row: the source URL, where it came from, when it was observed, and whether its page was confirmed. */
export function EvidenceRow({ e, compact = false, className = "", style }: { e: Evidence; compact?: boolean; className?: string; style?: React.CSSProperties }) {
  const demo = e.source === "demo";
  return (
    <li className={`${compact ? "py-2.5" : "py-4"} ${className}`} style={style}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <a href={e.url} target="_blank" rel="noopener noreferrer" className="font-medium text-pitch underline decoration-pitch/30 underline-offset-2 hover:decoration-pitch">
            {e.title}<span className="sr-only"> (opens in new tab)</span>
          </a>
          <p className="mt-0.5 break-all font-mono text-xs text-muted">{compact ? host(e.url) : e.url}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {e.verified && <Chip tone="pitch">✓ Confirmed on page</Chip>}
          {demo ? <Chip tone="rust">Demo source</Chip> : <Chip>{e.source}</Chip>}
          {e.cache_hit && <Chip>Cached</Chip>}
        </div>
      </div>
      {!compact && e.snippet && <p className="mt-2 line-clamp-3 text-sm text-muted">{e.snippet}</p>}
      <p className="mt-1.5 text-xs text-muted">
        Retrieved {formatTime(e.retrieved_at)}
        {e.page_age && <> · page updated {day(e.page_age)}</>}
        {!compact && e.verified && <> · You.com Contents fetched this page and it names the event</>}
      </p>
    </li>
  );
}

export function CandidateCard({ c }: { c: TripCandidate }) {
  const confirmed = c.evidence.filter((e) => e.verified).length;
  return (
    <article className="rounded-lg border border-line bg-white p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Micro>Event found</Micro>
          <h3 className="mt-2 text-h2 font-semibold">{c.event}</h3>
          <p className="mt-1 text-muted">{c.destination}{c.dates && <> · {c.dates}</>}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-semibold">{c.estimated_total == null ? "Not priced yet" : money(c.estimated_total, c.currency)}</p>
          {c.estimated_total == null && <p className="text-xs text-muted">flights, hotel and tickets not yet searched</p>}
        </div>
      </div>
      <p className="mt-4">{c.rationale}</p>
      {c.caveats.length > 0 && <ul className="mt-4 space-y-1.5">{c.caveats.map((x) => <Assumption key={x}>{x}</Assumption>)}</ul>}
      <div className="mt-8 flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="font-semibold">Evidence ({c.evidence.length})</h4>
        <p className="text-sm text-muted">{confirmed} confirmed on the page itself</p>
      </div>
      <ul className="divide-y divide-line">{c.evidence.map((e) => <EvidenceRow key={e.url} e={e} />)}</ul>
      <p className="mt-4 text-xs text-muted">Search results are evidence, not proof of availability. Nothing is booked.</p>
    </article>
  );
}
