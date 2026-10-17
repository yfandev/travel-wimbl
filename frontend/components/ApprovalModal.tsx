"use client";
import { useEffect, useRef } from "react";
import type { TripPackage } from "@/lib/types";
import { money } from "./ui";

/** The traveler-facing half of the approval gate. The backend gate is enforced in controller code, not here. */
export function ApprovalModal({ pkg, onCancel, onApprove }: { pkg: TripPackage | null; onCancel: () => void; onApprove: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (pkg && !dialog.open) dialog.showModal();
    if (!pkg && dialog.open) dialog.close();
  }, [pkg]);

  return (
    // showModal() gives focus trapping and Esc-to-close natively.
    <dialog ref={ref} onClose={onCancel} aria-labelledby="approve-title"
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-line bg-white p-0 text-forest backdrop:bg-forest/40">
      {pkg && (
        <div className="p-6">
          <h2 id="approve-title" className="text-h2 font-semibold">Approve booking request?</h2>
          <p className="mt-3 text-sm">
            <strong>WIMBL does not book.</strong> Approving lets WIMBL hand you off to each provider&rsquo;s own page for{" "}
            <em>{pkg.title}</em>. Nothing is purchased, reserved or charged unless you complete it there.
          </p>
          <ul className="mt-4 space-y-1 text-sm text-muted">
            {pkg.items.map((i) => (
              <li key={i.kind} className="flex justify-between gap-4">
                <span>{i.label}</span>
                <span>{i.price == null ? "unpriced" : money(i.price, pkg.currency)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-rust">Prices were observed at search time and may have changed. They are not live inventory.</p>
          <div className="mt-6 flex justify-end gap-3">
            <button type="button" onClick={onCancel} autoFocus className="rounded-lg border border-line px-4 py-2.5 text-sm font-medium hover:border-forest">
              Cancel
            </button>
            <button type="button" onClick={onApprove} className="rounded-lg bg-gold px-4 py-2.5 text-sm font-semibold text-forest hover:bg-[#b8931f]">
              I approve
            </button>
          </div>
        </div>
      )}
    </dialog>
  );
}
