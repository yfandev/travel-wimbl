"use client";
// Tracks whether any data on screen came from mocks. The banner reads this, so it disappears
// on its own once every loaded source is real, and reappears if a live fetch falls back to mocks.
import { useSyncExternalStore } from "react";

const mockSources = new Set<string>();
const listeners = new Set<() => void>();
let snapshot = false;

export function reportSource(key: string, mode: "live" | "mock") {
  if (mode === "mock") mockSources.add(key);
  else mockSources.delete(key);
  const next = mockSources.size > 0;
  if (next !== snapshot) {
    snapshot = next;
    listeners.forEach((l) => l());
  }
}

/** Called on navigation: the banner describes the current page's data only. */
export function resetSources() {
  mockSources.clear();
  if (snapshot) { snapshot = false; listeners.forEach((l) => l()); }
}

export function useShowingMockData() {
  return useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    () => snapshot,
    () => false,
  );
}
