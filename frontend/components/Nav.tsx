"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DATA_SOURCE } from "@/lib/api";

const LINKS = [
  { href: "/run/mock-run-0001", label: "Live run", match: "/run" },
  { href: "/brain", label: "Shared Brain", match: "/brain" },
  { href: "/lab", label: "N+1 lab", match: "/lab" },
  { href: "/model", label: "Nemotron", match: "/model" },
];

export function Nav() {
  const path = usePathname();
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      {DATA_SOURCE === "mock" && (
        <div role="status" className="bg-rust px-4 py-2 text-center text-sm font-medium text-white">
          Mock data, not from a real run. Sources point to example.org.
        </div>
      )}
      <header className="border-b border-line bg-white">
        <nav aria-label="Primary" className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-4 sm:px-6">
          <Link href="/" className="text-xl font-semibold tracking-tight text-forest">
            wimbl<span className="text-pitch">.</span>
          </Link>
          <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
            {LINKS.map((l) => {
              const active = path.startsWith(l.match);
              return (
                <li key={l.href}>
                  <Link href={l.href} aria-current={active ? "page" : undefined}
                    className={`border-b-2 pb-1 ${active ? "border-gold font-medium text-forest" : "border-transparent text-muted hover:text-forest"}`}>
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
