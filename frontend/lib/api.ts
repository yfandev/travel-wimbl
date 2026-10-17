// The only place screens get data. Every read goes to the backend first (same-origin /api/*, forwarded to
// NEXT_PUBLIC_API_URL by next.config.ts). Mock data is used only when the API can't be reached, and each result
// reports its source so the sample-data bar shows exactly when mock data is on screen.
import { reportSource } from "./dataMode";
import { MOCK_ABLATION, MOCK_LESSONS, MOCK_N1, MOCK_RUN, MOCK_RUN_RECORDS } from "./mock";
import type { Lesson, MemoryAblation, N1Report, Run, RunRecord, RunSummary, TripRequest, TripResult } from "./types";

/** The backend answered, but not with data (e.g. 404). Shown as-is; never replaced with mocks. */
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** The backend is unreachable: network error, or the proxy's 5xx when nothing listens on NEXT_PUBLIC_API_URL. */
class Unreachable extends Error {}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { cache: "no-store", ...init });
  } catch (e) {
    throw new Unreachable(String(e));
  }
  const body = await res.json().catch(() => null);
  if (res.ok) return body as T;
  if (res.status >= 500 && body?.detail == null) throw new Unreachable(`${path} returned ${res.status}`);
  throw new ApiError(res.status, body?.detail ?? `${path} returned HTTP ${res.status}`);
}

async function load<T>(key: string, path: string, mock: () => T): Promise<T> {
  await Promise.resolve(); // report after the Nav's per-page reset, never before it
  try {
    const data = await fetchJson<T>(path);
    reportSource(key, "live");
    return data;
  } catch (e) {
    if (!(e instanceof Unreachable)) throw e;
    console.warn(`[wimbl] backend unreachable for ${path}; showing sample data`);
    reportSource(key, "mock");
    return mock();
  }
}

/** Recorded runs, newest first. Falls back to the mock run's id so the run screen still has something to open. */
export const listRuns = (): Promise<RunSummary[]> =>
  load("runs", "/api/runs", () => [{ run_id: MOCK_RUN.run_id, goal: MOCK_RUN.goal, mode: "mock", status: "verified",
    controller_decision: "stop", started_at: "", elapsed_ms: 0, candidates: 2, findings: 0, evidence: 8 } satisfies RunSummary]);

/** A recorded run. "latest" resolves to the newest run, or null when none has been recorded yet. */
export async function getRun(id: string): Promise<Run | null> {
  let runId = id;
  if (id === "latest") {
    const runs = await listRuns();
    if (!runs.length) return null;
    runId = runs[0].run_id;
  }
  if (runId === MOCK_RUN.run_id) { await Promise.resolve(); reportSource("run", "mock"); return { ...MOCK_RUN }; }
  const run = await load<Run>("run", `/api/runs/${encodeURIComponent(runId)}`, () => ({ ...MOCK_RUN }));
  // A run whose evidence is all backend demo fixtures is sample data too.
  reportSource("run", run.mode === "mock" ? "mock" : "live");
  return run;
}

export const getLessons = (): Promise<Lesson[]> =>
  load("lessons", "/api/memory/lessons", () => ({ entries: MOCK_LESSONS })).then((r) => r.entries);
export const getAblation = (): Promise<MemoryAblation> => load("ablation", "/api/memory/ablation", () => MOCK_ABLATION);
/** The latest N+1 gate decision, or null when none has been recorded (404). */
export const getN1 = (): Promise<N1Report | null> =>
  load<N1Report | null>("n1", "/api/improvement/latest", () => MOCK_N1).catch((e) => {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  });
export const getRunRecords = (): Promise<RunRecord[]> => load("runlog", "/api/runlog", () => MOCK_RUN_RECORDS);

/** Live discovery: You.com Search, then You.com Contents on official pages, then the verifier. Never falls back to mocks. */
export async function discoverTrip(request: TripRequest): Promise<TripResult> {
  try {
    return await fetchJson<TripResult>("/api/trips/discover", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
    });
  } catch (e) {
    if (e instanceof Unreachable) throw new Error("The backend isn't reachable. Start uvicorn on :8000 and try again.");
    throw e;
  }
}
