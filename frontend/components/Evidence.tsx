import type { Evidence, Fact, PriceLine, PriceTotal, TicketAdvice, TripCandidate } from "@/lib/types";
import { Assumption, Chip, Micro, formatTime } from "./ui";

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

const ADVERTISED = "advertised price, not live inventory";
/** Cents are kept when the source shows them, so the line items visibly add up to the sum. */
const exact = (n: number, currency: string) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, minimumFractionDigits: Number.isInteger(n) ? 0 : 2 }).format(n);
const link = "text-pitch underline decoration-pitch/30 underline-offset-2 hover:decoration-pitch";

/** One line item: the advertised price with its quote, source link and observation time, or "price not published" with
 *  the source that was checked. */
function PriceRow({ l }: { l: PriceLine }) {
  const priced = l.status === "advertised" && l.amount != null && l.subtotal != null && l.currency;
  return (
    <li className="py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <p className="min-w-0 font-medium">{l.label}</p>
        {priced
          ? <p className="text-right tabular-nums">
              {l.quantity > 1 && <span className="text-sm text-muted">{exact(l.amount!, l.currency!)} {l.unit} × {l.quantity} = </span>}
              <span className="font-semibold">{exact(l.subtotal!, l.currency!)}</span>
            </p>
          : <p className="text-sm font-medium text-rust">{l.status === "not_searched" ? "not looked up" : "price not published"}</p>}
      </div>
      {priced && l.quote && <p className="mt-1 text-sm italic text-muted">“{l.quote}”</p>}
      {!priced && l.note && <p className="mt-1 text-sm text-muted">{l.note}</p>}
      <p className="mt-1 text-xs text-muted">
        {l.url
          ? <a href={l.url} target="_blank" rel="noopener noreferrer" className={link}>{l.title || host(l.url)}<span className="sr-only"> (opens in new tab)</span></a>
          : "No source"}
        {l.official && " · official"}
        {l.observed_at && <> · seen {formatTime(l.observed_at)}</>}
        {l.via && <> · {l.via}</>}
        {priced && <> · <span className="font-medium text-rust">{ADVERTISED}</span></>}
      </p>
    </li>
  );
}

/** Package line items and their computed sum. The total covers only the priced lines in the trip currency; other
 *  currencies are listed, never converted. */
export function PriceTable({ lines, total }: { lines: PriceLine[]; total: PriceTotal | null | undefined }) {
  const sum = lines.reduce((acc, l) => (l.subtotal != null && l.currency === total?.currency ? acc + l.subtotal : acc), 0);
  const mismatch = total?.amount != null && Math.abs(total.amount - sum) > 0.01;
  return (
    <section className="mt-8" aria-labelledby="prices">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 id="prices" className="font-semibold">Package prices</h4>
        <Chip tone="pale-gold">Advertised prices, not live inventory</Chip>
      </div>
      <ul className="divide-y divide-line">{lines.map((l) => <PriceRow key={l.item} l={l} />)}</ul>
      {total && (
        <div className="border-t-2 border-forest pt-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-semibold">Sum of line items{!total.complete && " (partial)"}</p>
            <p className="text-2xl font-semibold tabular-nums">{total.amount != null ? exact(total.amount, total.currency) : "—"}</p>
          </div>
          <p className="mt-1 text-sm text-muted">
            {total.priced} of {total.lines} line items priced in {total.currency}
            {Object.entries(total.other_currencies).map(([c, v]) => <span key={c}> · plus {exact(v, c)} not converted</span>)}
            {!total.complete && " · unpriced lines are not counted, so this is not the trip total"}
          </p>
          {mismatch && <p role="alert" className="mt-1 text-sm text-red">The recorded total does not equal the sum of the line items ({exact(sum, total.currency)}).</p>}
        </div>
      )}
    </section>
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
          {c.price_total?.amount != null
            ? <>
                <p className="text-2xl font-semibold tabular-nums">{exact(c.price_total.amount, c.price_total.currency)}</p>
                <p className="text-xs text-muted">sum of {c.price_total.priced} of {c.price_total.lines} line items · {ADVERTISED}</p>
              </>
            : <>
                <p className="text-2xl font-semibold">{c.line_items?.length ? "Price not published" : "Not priced yet"}</p>
                {!c.line_items?.length && <p className="text-xs text-muted">flights, hotel and tickets not yet searched</p>}
              </>}
        </div>
      </div>
      <p className="mt-4">{c.rationale}</p>
      {c.caveats.length > 0 && <ul className="mt-4 space-y-1.5">{c.caveats.map((x) => <Assumption key={x}>{x}</Assumption>)}</ul>}
      {c.line_items && c.line_items.length > 0 && <PriceTable lines={c.line_items} total={c.price_total} />}
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
