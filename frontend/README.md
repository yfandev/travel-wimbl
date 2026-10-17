# WIMBL frontend

Next.js (App Router) + Tailwind v4. Screens: home, live run (family tree, definition of done, packages, approval modal), Shared Brain, Version N+1 lab, Nemotron panel.

```bash
cd frontend && npm install
npm run dev                                   # mock data, labelled "Mock" on every screen
NEXT_PUBLIC_WIMBL_DATA=live npm run dev   # read the backend at NEXT_PUBLIC_API_URL (frontend/.env.local)
npm run lint                                  # contrast rule (no gold text on white, no white on gold) + eslint
```

All data goes through `lib/api.ts`. Mocks in `lib/mock.ts` mirror the backend's record shapes (`lib/types.ts`); mock sources point to example.org, and model metrics stay "not yet run" until real run logs exist.

Live endpoints the screens expect (not all exist yet): `GET /api/runs/{id}`, `GET /api/runlog`, `GET /api/memory`, `GET /api/memory/ablation`, `GET /api/improvement/latest`.
