"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Assumption, Card, Chip, Micro, formatTime, money } from "@/components/ui";
import { discoverTrip } from "@/lib/api";
import { parseGoal } from "@/lib/goal";
import type { Evidence, TripResult } from "@/lib/types";

const STATUS = {
  verified: { tone: "pitch", text: "✓ Verified" },
  needs_review: { tone: "rust", text: "⚠ Needs review" },
  no_results: { tone: "rust", text: "No results" },
  error: { tone: "red", text: "✕ Error" },
} as const;

const host = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; } };
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }) : null);

function EvidenceRow({ e }: { e: Evidence }) {
  const demo = e.source === "demo";
  return (
    <li className="py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <a href={e.url} target="_blank" rel="noopener noreferrer" className="font-medium text-pitch underline decoration-pitch/30 underline-offset-2 hover:decoration-pitch">
            {e.title}<span className="sr-only"> (opens in new tab)</span>
          </a>
          <p className="mt-0.5 font-mono text-xs text-muted">{host(e.url)}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {e.verified && <Chip tone="pitch">✓ Confirmed on page</Chip>}
          {demo ? <Chip tone="rust">Demo source</Chip> : <Chip>You.com</Chip>}
          {e.cache_hit && <Chip>Cached</Chip>}
        </div>
      </div>
      {e.snippet && <p className="mt-2 line-clamp-3 text-sm text-muted">{e.snippet}</p>}
      <p className="mt-2 text-xs text-muted">
        Retrieved {formatTime(e.retrieved_at)}
        {e.page_age && <> · page updated {day(e.page_age)}</>}
        {e.verified && <> · You.com Contents fetched this page and it names the event</>}
      </p>
    </li>
  );
}

function TripScreen() {
  const goal = useSearchParams().get("goal") ?? "";
  const parsed = useMemo(() => parseGoal(goal), [goal]);
  const [result, setResult] = useState<TripResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!goal) return;
    let cancelled = false;
    setResult(null); setError(null);
    discoverTrip(parsed.request)
      .then((r) => { if (!cancelled) setResult(r); })
      .catch((e: Error) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [goal, parsed]);

  if (!goal) return <p className="text-muted">Enter a goal on the home page.</p>;
  const evidence = result?.candidates.flatMap((c) => c.evidence) ?? [];
  const live = evidence.some((e) => e.source !== "demo");

  return (
    <div className="space-y-10">
      <header>
        <div className="flex flex-wrap items-center gap-2">
          {result && (live ? <Chip tone="pitch">Live · You.com</Chip> : <Chip tone="rust">Demo sources</Chip>)}
          {result && <span className="font-mono text-xs text-muted">{result.run_id}</span>}
        </div>
        <h1 className="mt-3 text-h1 font-semibold">{goal}</h1>
      </header>

      <section aria-labelledby="read" className="grid gap-8 rounded-lg bg-mist p-6 sm:grid-cols-2 sm:p-8">
        <div>
          <h2 id="read" className="font-semibold">What you asked for</h2>
          <ul className="mt-3 space-y-1.5">{parsed.stated.map((s) => <li key={s}>{s}</li>)}</ul>
        </div>
        <div>
          <h2 className="font-semibold">Assumed, so you weren&rsquo;t asked</h2>
          <ul className="mt-3 space-y-1.5">{parsed.assumptions.map((a) => <Assumption key={a}>{a}</Assumption>)}</ul>
          <p className="mt-3 text-xs text-muted">Read in the browser for now; the controller&rsquo;s goal compiler will replace this step.</p>
        </div>
      </section>

      {error && (
        <p role="alert" className="rounded-lg border border-red/30 bg-red/5 px-5 py-4 text-sm text-red">Discovery failed: {error}</p>
      )}

      {!result && !error && (
        <p role="status" className="text-muted">Searching You.com and checking official pages…</p>
      )}

      {result && (
        <>
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-h2 font-semibold">Controller</h2>
              <div className="flex gap-2">
                <Chip tone={STATUS[result.status].tone}>{STATUS[result.status].text}</Chip>
                <Chip>decision: {result.controller_decision}</Chip>
              </div>
            </div>
            <ol className="mt-5 space-y-2 text-sm">
              {result.steps.map((s, i) => (
                <li key={i} className="flex gap-3"><span className="w-5 shrink-0 font-mono text-xs text-muted">{i + 1}</span><span>{s}</span></li>
              ))}
            </ol>
            {result.findings.length > 0 && (
              <div className="mt-6 border-t border-line pt-5">
                <Micro>Independent verifier</Micro>
                <ul className="mt-3 space-y-2">
                  {result.findings.map((f) => (
                    <li key={f.code} className={`text-sm ${f.severity === "error" ? "text-red" : f.severity === "warning" ? "text-rust" : "text-muted"}`}>
                      <span className="font-mono text-xs font-semibold">{f.code}</span> · {f.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          {result.candidates.length === 0 && <p className="text-muted">No candidates. The controller decided to {result.controller_decision}.</p>}

          {result.candidates.map((c) => (
            <Card key={c.title} as="article">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <Micro>Event found</Micro>
                  <h2 className="mt-2 text-h2 font-semibold">{c.event}</h2>
                  <p className="mt-1 text-muted">{c.destination}{c.dates && <> · {c.dates}</>}</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-semibold">{c.estimated_total == null ? "Not priced yet" : money(c.estimated_total, c.currency)}</p>
                  <p className="text-xs text-muted">flights, hotel and tickets not yet searched</p>
                </div>
              </div>
              <p className="mt-4">{c.rationale}</p>
              {c.caveats.length > 0 && <ul className="mt-4 space-y-1.5">{c.caveats.map((x) => <Assumption key={x}>{x}</Assumption>)}</ul>}

              <div className="mt-8 flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="font-semibold">Evidence ({c.evidence.length})</h3>
                <p className="text-sm text-muted">{c.evidence.filter((e) => e.verified).length} confirmed on the page itself</p>
              </div>
              <ul className="divide-y divide-line">{c.evidence.map((e) => <EvidenceRow key={e.url} e={e} />)}</ul>
              <p className="mt-4 text-xs text-muted">Search results are evidence, not proof of availability. Nothing is booked.</p>
            </Card>
          ))}

          <Card>
            <Micro>Acceptance criteria</Micro>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">{result.acceptance_criteria.map((a) => <li key={a}>{a}</li>)}</ul>
          </Card>
        </>
      )}
    </div>
  );
}

export default function TripPage() {
  return <Suspense fallback={<p className="text-muted">Loading…</p>}><TripScreen /></Suspense>;
}
