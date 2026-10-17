// The only place screens get data. NEXT_PUBLIC_WIMBL_DATA=live reads the FastAPI backend; anything else serves mocks.
// Live endpoints below are placeholders until the backend (Phases 2–5) publishes them.
import { MOCK_ABLATION, MOCK_LESSONS, MOCK_N1, MOCK_RUN, MOCK_RUN_RECORDS } from "./mock";
import type { Lesson, MemoryAblation, N1Report, Run, RunRecord } from "./types";

export const DATA_SOURCE: "live" | "mock" = process.env.NEXT_PUBLIC_WIMBL_DATA === "live" ? "live" : "mock";
const API = process.env.NEXT_PUBLIC_WIMBL_API ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json() as Promise<T>;
}

export const getRun = (id: string): Promise<Run> =>
  DATA_SOURCE === "live" ? get(`/api/runs/${encodeURIComponent(id)}`) : Promise.resolve({ ...MOCK_RUN, run_id: id });
export const getLessons = (): Promise<Lesson[]> =>
  DATA_SOURCE === "live" ? get<{ entries: Lesson[] }>("/api/memory").then((r) => r.entries) : Promise.resolve(MOCK_LESSONS);
export const getAblation = (): Promise<MemoryAblation> =>
  DATA_SOURCE === "live" ? get("/api/memory/ablation") : Promise.resolve(MOCK_ABLATION);
export const getN1 = (): Promise<N1Report> =>
  DATA_SOURCE === "live" ? get("/api/improvement/latest") : Promise.resolve(MOCK_N1);
export const getRunRecords = (): Promise<RunRecord[]> =>
  DATA_SOURCE === "live" ? get("/api/runlog") : Promise.resolve(MOCK_RUN_RECORDS);
