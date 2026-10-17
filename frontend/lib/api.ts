// The only place screens get data. NEXT_PUBLIC_WIMBL_DATA=live reads the FastAPI backend and falls back to mocks
// if a request fails; every result reports its source so the mock banner shows only while mock data is on screen.
import { reportSource } from "./dataMode";
import { MOCK_ABLATION, MOCK_LESSONS, MOCK_N1, MOCK_RUN, MOCK_RUN_RECORDS } from "./mock";
import type { Lesson, MemoryAblation, N1Report, Run, RunRecord } from "./types";

const LIVE = process.env.NEXT_PUBLIC_WIMBL_DATA === "live";
const API = process.env.NEXT_PUBLIC_WIMBL_API ?? "http://localhost:8000";

async function load<T>(key: string, path: string, mock: () => T): Promise<T> {
  await Promise.resolve(); // report after the Nav's per-page reset, never before it
  if (LIVE) {
    try {
      const res = await fetch(`${API}${path}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`${path} returned ${res.status}`);
      const data = (await res.json()) as T;
      reportSource(key, "live");
      return data;
    } catch (e) {
      console.warn(`[wimbl] ${path} unavailable, showing mock data`, e);
    }
  }
  reportSource(key, "mock");
  return mock();
}

// Live runs carry their own mode ("live" or "replayed"); only a mock run raises the mock banner.
export const getRun = async (id: string): Promise<Run> => {
  const run = await load("run", `/api/runs/${encodeURIComponent(id)}`, () => ({ ...MOCK_RUN, run_id: id }));
  reportSource("run", run.mode === "mock" ? "mock" : "live");
  return run;
};
export const getLessons = (): Promise<Lesson[]> =>
  load("lessons", "/api/memory", () => ({ entries: MOCK_LESSONS })).then((r) => r.entries);
export const getAblation = (): Promise<MemoryAblation> => load("ablation", "/api/memory/ablation", () => MOCK_ABLATION);
export const getN1 = (): Promise<N1Report> => load("n1", "/api/improvement/latest", () => MOCK_N1);
export const getRunRecords = (): Promise<RunRecord[]> => load("runlog", "/api/runlog", () => MOCK_RUN_RECORDS);
