// Turns the one-line goal into the backend's TripRequest. Temporary: the controller's goal compiler (Phase 2, on
// Nemotron Super) replaces this. Every value it fills in without the traveler saying so is returned as an assumption.
import type { TripRequest } from "./types";

const MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december";
const DEFAULT_ORIGIN = "SFO";
const DEFAULT_BUDGET = 2500;

export interface ParsedGoal { request: TripRequest; stated: string[]; assumptions: string[] }

export function parseGoal(goal: string): ParsedGoal {
  let rest = ` ${goal.trim()} `;
  const stated: string[] = [];
  const assumptions: string[] = [];
  const take = (re: RegExp) => { const m = rest.match(re); if (m) rest = rest.replace(m[0], " "); return m; };

  const budget = take(/\b(?:under|below|max(?:imum)?|budget(?: of)?|for|<)?\s*\$\s?([\d,]+(?:\.\d+)?)\s*(k)?\b/i);
  const budgetValue = budget ? Number(budget[1].replace(/,/g, "")) * (budget[2] ? 1000 : 1) : DEFAULT_BUDGET;
  if (budget) stated.push(`Budget ≤ $${budgetValue.toLocaleString()}`);
  else assumptions.push(`Budget $${DEFAULT_BUDGET.toLocaleString()} (not stated)`);

  const origin = take(/\b(?:flying |departing )?from\s+([A-Z]{3})\b/i);
  if (origin) stated.push(`Origin ${origin[1].toUpperCase()}`);
  else assumptions.push(`Origin ${DEFAULT_ORIGIN} (not stated)`);

  const when = take(new RegExp(`\\b(?:in\\s+)?((?:${MONTHS})(?:\\s+\\d{4})?|this (?:season|autumn|fall|spring|summer|winter|weekend|month)|next (?:season|month|year))\\b`, "i"));
  if (when) stated.push(`When: ${when[1]}`);
  else assumptions.push("Dates flexible (not stated)");

  if (/\b(?:cheapest|cheap|care most about price|lowest price)\b/i.test(goal)) stated.push("Priority: lowest price");

  const interest = rest
    .replace(/^\s*(?:i\s+(?:want|would like|'d like)\s+to\s+)?(?:see|watch|go to|catch|attend)\s+/i, " ")
    .replace(/\b(?:i care most about \w+|cheapest|cheap)\b/gi, " ")
    .replace(/[,.;]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 80) || goal.trim().slice(0, 80);
  assumptions.push("1 traveler, 4 days (backend defaults)");

  // WIMBL is football-only, but the backend picks the football family by keyword ("match", "football", "derby"...).
  // A goal that names only a club or stadium would otherwise run under the generic sports family.
  const isFootball = /\b(football|soccer|f[uú]tbol|match|derby|league|liga|uefa|fifa|bundesliga|serie a|ligue 1)\b/i.test(interest);
  const searchInterest = isFootball ? interest : `${interest} football match`.slice(0, 80);

  return {
    request: { interest: searchInterest, origin: origin ? origin[1].toUpperCase() : DEFAULT_ORIGIN, budget: budgetValue, currency: "USD", days: 4, dates: when ? when[1] : null, traveler_context: goal.slice(0, 1000) },
    stated: [`Looking for: ${interest}`, ...stated],
    assumptions,
  };
}
