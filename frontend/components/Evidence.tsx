import type { Evidence, Fact, TicketAdvice, TripCandidate } from "@/lib/types";
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

/** One extracted fact: the value, whether code confirmed its quote, the quote itself, and the page it came from. */
export function FactRow({ f }: { f: Fact }) {
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <p className="min-w-0"><span className="font-medium">{f.kind.replace(/_/g, " ")}:</span> {f.value}
          {f.amount != null && <span className="text-muted"> · {f.currency ?? ""} {f.amount.toLocaleString("en-US")}</span>}</p>
        <div className="flex flex-wrap gap-1.5">
          {f.verified ? <Chip tone="pitch">✓ Quote confirmed</Chip> : <Chip tone="rust">Not confirmed</Chip>}
          {f.official && <Chip>Official</Chip>}
          {f.kind === "ticket_price" && <Chip tone="pale-gold">Listed price, not live</Chip>}
        </div>
      </div>
      {f.quote && <p className="mt-1 text-sm italic text-muted">“{f.quote}”</p>}
      <p className="mt-1 text-xs text-muted">
        <a href={f.url} target="_blank" rel="noopener noreferrer" className="text-pitch underline decoration-pitch/30 underline-offset-2 hover:decoration-pitch">
          {f.title || host(f.url)}<span className="sr-only"> (opens in new tab)</span>
        </a> · seen {formatTime(f.observed_at)} · {f.check}
      </p>
    </li>
  );
}

/** The tickets child's reading of the facts. It names the exact model; it does not confirm any fact. */
export function TicketAdviceBox({ a }: { a: TicketAdvice }) {
  return (
    <div className="mt-6 rounded-lg border border-line p-4">
      <Micro>Ticket advice · NVIDIA Nemotron {a.model ?? ""}, served by Crusoe Managed Inference</Micro>
      <p className="mt-2"><span className="font-medium">Buy from:</span> {a.recommended_channel}{" "}
        <a href={a.official_source_url} target="_blank" rel="noopener noreferrer" className="text-pitch underline decoration-pitch/30 underline-offset-2">official source</a></p>
      {a.unofficial_sources.length > 0 && <p className="mt-1 text-sm text-muted">Unofficial: {a.unofficial_sources.join(", ")}</p>}
      {a.risks.length > 0 && <ul className="mt-2 space-y-1.5">{a.risks.map((r) => <Assumption key={r}>{r}</Assumption>)}</ul>}
      {a.price_is_live && <p className="mt-2 text-sm text-red">The model claimed a live price; search results do not prove availability.</p>}
    </div>
  );
}

export function CandidateCard({ c }: { c: TripCandidate }) {
  const confirmed = c.evidence.filter((e) => e.verified).length;
  const facts = c.facts ?? [];
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
      {c.ticket_advice && <TicketAdviceBox a={c.ticket_advice} />}
      {facts.length > 0 && <>
        <div className="mt-8 flex flex-wrap items-baseline justify-between gap-2">
          <h4 className="font-semibold">Match and ticket facts from You.com ({facts.length})</h4>
          <p className="text-sm text-muted">{facts.filter((f) => f.verified).length} quotes confirmed by code</p>
        </div>
        <ul className="divide-y divide-line">{facts.map((f, i) => <FactRow key={`${f.kind}-${i}`} f={f} />)}</ul>
      </>}
      <div className="mt-8 flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="font-semibold">Evidence ({c.evidence.length})</h4>
        <p className="text-sm text-muted">{confirmed} confirmed on the page itself</p>
      </div>
      <ul className="divide-y divide-line">{c.evidence.map((e) => <EvidenceRow key={e.url} e={e} />)}</ul>
      <p className="mt-4 text-xs text-muted">Search results are evidence, not proof of availability. Nothing is booked.</p>
    </article>
  );
}
