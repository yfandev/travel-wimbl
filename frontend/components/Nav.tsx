"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { resetSources, useShowingMockData } from "@/lib/dataMode";

const LINKS = [
  { href: "/demo", label: "Demo", match: "/demo" },
  { href: "/run/latest", label: "Live run", match: "/run" },
  { href: "/brain", label: "Shared Brain", match: "/brain" },
  { href: "/lab", label: "N+1 lab", match: "/lab" },
  { href: "/model", label: "Nemotron", match: "/model" },
];

export function Nav() {
  const path = usePathname();
  const mock = useShowingMockData();
  useEffect(() => { resetSources(); }, [path]);
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-line bg-white/95 backdrop-blur">
        {mock && (
          <p role="status" className="bg-pale-gold px-4 py-1 text-center text-xs text-rust">
            Sample data, not from a live run
          </p>
        )}
        <nav aria-label="Primary" className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-6 px-4 sm:px-8">
          <Link href="/" className="text-lg font-semibold tracking-tight text-forest">
            wimbl<span className="text-pitch">.</span>
          </Link>
          <ul className="flex min-w-0 gap-x-4 overflow-x-auto text-sm sm:gap-x-7">
            {LINKS.map((l) => {
              const active = path.startsWith(l.match);
              return (
                <li key={l.href} className="shrink-0">
                  <Link href={l.href} aria-current={active ? "page" : undefined}
                    className={`inline-block py-1 ${active ? "font-medium text-forest shadow-[inset_0_-2px_0_var(--color-gold)]" : "text-muted hover:text-forest"}`}>
                    {l.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
    </>
  );
}
