import type { TripPackage } from "@/lib/types";
import { Assumption, Chip, SourceLink, money } from "./ui";

const KIND_LABEL = { flight: "Flight", hotel: "Hotel", ticket: "Ticket", transit: "Local transit" } as const;

const lineSum = (p: TripPackage) => p.items.reduce((n, i) => n + (i.price ?? 0), 0);

export function Packages({ packages, onRequestBooking }: { packages: TripPackage[]; onRequestBooking: (p: TripPackage) => void }) {
  return (
    <ol className="space-y-4">
      {packages.map((p) => (
        <li key={p.rank} className="rise rounded-lg border border-line bg-white p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-mono text-xs text-muted">#{p.rank}</p>
              <h3 className="text-lg font-semibold">{p.title}</h3>
              <p className="text-sm text-muted">{p.match} · {p.kickoff}</p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-semibold tabular-nums">{p.estimated_total == null ? "—" : money(p.estimated_total, p.currency)}</p>
              <p className="text-xs text-muted">estimated total</p>
              <div className="mt-1">{p.status === "verified" ? <Chip tone="pitch">✓ Verified</Chip> : <Chip tone="rust">⚠ Needs review</Chip>}</div>
            </div>
          </div>

          <table className="mt-5 w-full text-sm">
            <caption className="sr-only">Cost breakdown for {p.title}</caption>
            <tbody className="divide-y divide-line">
              {p.items.map((i) => (
                <tr key={i.kind}>
                  <th scope="row" className="w-28 py-2.5 pr-3 text-left align-top font-medium">{KIND_LABEL[i.kind]}</th>
                  <td className="py-2.5 pr-3 align-top">
                    {i.label}
                    <div className="mt-0.5"><SourceLink url={i.source_url} observedAt={i.observed_at} /></div>
                  </td>
                  <td className="py-2.5 text-right align-top tabular-nums">{i.price == null ? "—" : money(i.price, p.currency)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-line">
                <th scope="row" colSpan={2} className="pt-3 text-left font-medium">
                  Sum of line items{p.items.some((i) => i.price == null) && <span className="ml-1 font-normal text-rust">(some items unpriced)</span>}
                </th>
                <td className="pt-3 text-right font-semibold tabular-nums">{money(lineSum(p), p.currency)}</td>
              </tr>
              {p.estimated_total != null && Math.abs(p.estimated_total - lineSum(p)) > 1 && (
                <tr><td colSpan={3} className="pt-1 text-right text-sm text-red">✕ Stated total {money(p.estimated_total, p.currency)} doesn&rsquo;t match the line items</td></tr>
              )}
            </tfoot>
          </table>

          {(p.assumptions.length > 0 || p.risks.length > 0) && (
            <ul className="mt-4 space-y-1.5">
              {p.assumptions.map((a) => <Assumption key={a}>{a}</Assumption>)}
              {p.risks.map((r) => (
                <li key={r} className="flex gap-2 text-sm text-rust"><span aria-hidden="true">!</span><span><span className="sr-only">Risk: </span>{r}</span></li>
              ))}
            </ul>
          )}

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <p className="text-xs text-muted">Search results are evidence, not proof of availability.</p>
            <button type="button" onClick={() => onRequestBooking(p)} className="rounded-lg bg-gold px-4 py-2.5 text-sm font-semibold text-forest hover:bg-[#b8931f]">
              Request booking
            </button>
          </div>
        </li>
      ))}
    </ol>
  );
}
