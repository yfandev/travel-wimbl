"use client";
import type { AgentNode, TripFact } from "@/lib/types";
import { usePrefersReducedMotion } from "@/lib/useRunReplay";

const W = 880, H = 420, NODE_W = 136, NODE_H = 48;
const CHILD_ORDER = ["tickets", "flights", "hotels", "transit", "price_watch", "coordination"];

/** Fixed positions: parents down the centre, controller and verifier beside them, children along the bottom. */
function layout(agents: AgentNode[]) {
  const pos: Record<string, { x: number; y: number }> = {
    controller: { x: 120, y: 54 },
    sports_parent: { x: 440, y: 54 },
    verifier: { x: 760, y: 54 },
    football_parent: { x: 440, y: 158 },
  };
  const kids = agents.filter((a) => CHILD_ORDER.includes(a.role)).sort((a, b) => CHILD_ORDER.indexOf(a.role) - CHILD_ORDER.indexOf(b.role));
  const gap = (W - 80) / Math.max(kids.length, 5);
  const slots = Math.max(kids.length, 5);
  kids.forEach((k, i) => { pos[k.id] = { x: 40 + gap * (i + 0.5) + (gap * (slots - kids.length)) / 2, y: 290 }; });
  return { pos, kids };
}

const FIXED: AgentNode[] = [
  { id: "controller", role: "controller", label: "Trip Controller", inherited: [] },
  { id: "verifier", role: "verifier", label: "Verifier", inherited: [] },
];

export function FamilyTree({ agents, activeId, facts, elapsed }: { agents: AgentNode[]; activeId: string | null; facts: (TripFact & { t: number })[]; elapsed: number }) {
  const reduced = usePrefersReducedMotion();
  const all = [...FIXED, ...agents];
  const { pos, kids } = layout(all);
  const inFlight = facts.filter((f) => elapsed - f.t < 1600);

  const edge = (from: string, to: string) => {
    const a = pos[from], b = pos[to];
    if (!a || !b) return null;
    const y1 = a.y + NODE_H / 2, y2 = b.y - NODE_H / 2, mid = (y1 + y2) / 2;
    return `M${a.x},${y1} C${a.x},${mid} ${b.x},${mid} ${b.x},${y2}`;
  };
  const sibling = (from: string, to: string) => {
    const a = pos[from], b = pos[to];
    if (!a || !b) return null;
    const y = a.y + NODE_H / 2 + 6;
    return `M${a.x},${y} Q${(a.x + b.x) / 2},${y + 70} ${b.x},${y}`;
  };

  return (
    <>
      {/* Desktop and tablet: the tree. */}
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="tree-title" className="hidden w-full md:block">
        <title id="tree-title">Agent family: Sports Parent, Football Parent, and {kids.length} trip children</title>
        <g fill="none" stroke="#0E3B2E" strokeOpacity="0.25" strokeWidth="1.5">
          {pos.football_parent && <path d={edge("sports_parent", "football_parent") ?? ""} />}
          {kids.map((k) => <path key={k.id} d={edge("football_parent", k.id) ?? ""} className="rise" />)}
        </g>
        <text x={760} y={100} textAnchor="middle" className="fill-muted text-[11px]">sees package + evidence only</text>

        {inFlight.flatMap((f) => f.to_agents.map((to) => {
          const d = sibling(f.from_agent, to);
          if (!d) return null;
          return (
            <g key={`${f.key}-${to}`}>
              <path d={d} fill="none" stroke="#C9A227" strokeWidth="2" strokeDasharray={reduced ? undefined : "4 4"} />
              {!reduced && (
                <circle r="5" fill="#C9A227">
                  <animateMotion dur="1.2s" repeatCount="1" fill="freeze" path={d} />
                </circle>
              )}
            </g>
          );
        }))}

        {all.map((a) => {
          const p = pos[a.id];
          if (!p) return null;
          const active = a.id === activeId;
          const isChild = CHILD_ORDER.includes(a.role);
          return (
            <g key={a.id} className={`${isChild ? "rise" : ""} ${active ? "agent-glow" : ""}`}>
              <rect x={p.x - NODE_W / 2} y={p.y - NODE_H / 2} width={NODE_W} height={NODE_H} rx="10"
                fill={active ? "#C9A227" : a.role === "football_parent" || a.role === "sports_parent" ? "#F5F7F4" : "#FFFFFF"}
                stroke={active ? "#C9A227" : "#0E3B2E"} strokeOpacity={active ? 1 : 0.3}
                strokeDasharray={a.role === "verifier" ? "5 4" : undefined} strokeWidth="1.5" />
              <text x={p.x} y={p.y + (a.version ? -2 : 5)} textAnchor="middle" className="fill-forest text-[14px] font-semibold">{a.label}</text>
              {a.version && <text x={p.x} y={p.y + 14} textAnchor="middle" className="fill-forest/70 font-mono text-[11px]">{a.version}</text>}
              {a.inherited.slice(0, 2).map((l, i) => (
                <g key={l.lesson_id}><title>{`${l.lesson_id}, inherited from ${l.parent_version}, influence ${l.influence.toFixed(2)}`}</title>
                  <rect x={p.x - 60} y={p.y + NODE_H / 2 + 8 + i * 22} width="120" height="18" rx="9" fill="#F6EFD6" />
                  <text x={p.x} y={p.y + NODE_H / 2 + 21 + i * 22} textAnchor="middle" className="fill-forest font-mono text-[11px]">
                    {l.lesson_id} · {l.influence.toFixed(2)}
                  </text>
                </g>
              ))}
            </g>
          );
        })}
      </svg>

      {/* Phones: the same family as a list. */}
      <ol className="space-y-2 md:hidden" aria-label="Agent family">
        {all.map((a) => (
          <li key={a.id} className={`rounded-lg border px-3 py-2 ${a.id === activeId ? "border-gold bg-pale-gold" : "border-line"} ${CHILD_ORDER.includes(a.role) ? "ml-6" : ""}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{a.label}{a.version && <span className="ml-1.5 font-mono text-xs text-muted">{a.version}</span>}</span>
              {a.id === activeId && <span className="text-micro font-medium uppercase">Working</span>}
            </div>
            {a.inherited.length > 0 && (
              <p className="mt-1 font-mono text-xs text-muted">Inherits {a.inherited.map((l) => `${l.lesson_id} (influence ${l.influence.toFixed(2)}, ${l.parent_version})`).join(", ")}</p>
            )}
          </li>
        ))}
      </ol>
    </>
  );
}
