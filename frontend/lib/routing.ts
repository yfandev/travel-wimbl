// Requested model per role, copied from wimbl/integrations/models.py (the backend's single routing file).
// These are what WIMBL *asks* for. The panel shows what Crusoe *returned* only from run records.
export const SUPER = "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B";
export const NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B";
export const LIGHTNING = "nvidia/Nemotron-3.5-Lightning-30B-A3B";

export const ROUTES: { role: string; requested: string; note?: string }[] = [
  { role: "controller", requested: SUPER },
  { role: "verifier", requested: SUPER },
  { role: "learning", requested: SUPER },
  { role: "trip children", requested: LIGHTNING, note: `Pinned over ${NANO} by the child-model bakeoff (docs/smoke-results.md)` },
];
