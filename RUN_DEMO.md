# Run the WIMBL demo

Copy-paste steps for a fresh Mac. You'll run two terminals: the backend (FastAPI, port 8000) and the web app (Next.js, port 3000), then open http://localhost:3000/demo.

## 1. Prerequisites (once)

You need Python 3.11+, Node 20+, and git. With [Homebrew](https://brew.sh):

```bash
brew install python@3.12 node git
python3.12 --version   # 3.12.x
node --version         # v20 or newer
```

You also need read access to the GitHub repo `yfandev/travel-wimbl`.

## 2. Get the code

Everything the demo needs is on one branch, `demo/wimbl-recording`. It merges the web app (`feat/wimbl-frontend`) with the backend endpoints (`feat/wimbl-agent-family`).

```bash
git clone https://github.com/yfandev/travel-wimbl.git
cd travel-wimbl
git checkout demo/wimbl-recording
```

## 3. Backend setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env.local
```

Open `.env.local` and fill in these two values (ask the team for them; never commit this file, it's gitignored):

- `YOU_API_KEY`: You.com Search and Contents
- `CRUSOE_API_KEY`: Crusoe Managed Inference (NVIDIA Nemotron)

Without `YOU_API_KEY` the app still runs, but new searches return labelled demo sources and `/demo` falls back to the recorded run (see "What's live" below).

## 4. Web app setup

```bash
cd frontend
npm install
cp .env.example .env.local   # sets NEXT_PUBLIC_API_URL=http://localhost:8000
npm run build
cd ..
```

## 5. Start the demo

Terminal 1, from the repo root (the `travel-wimbl` folder):

```bash
./scripts/start_demo_backend.sh
```

It seeds any missing file in `data/` from `demo_data/` (one recorded You.com run, the model-call log, and the Shared Brain lesson database), sets `WIMBL_LESSONS_DB=./data/memory_v2.sqlite3`, and starts the backend on http://localhost:8000. Leave it running.

Terminal 2, from the repo root:

```bash
cd frontend && npm start
```

Open **http://localhost:3000/demo**. Move between the four steps with **→** and **←** (a presentation clicker's PageDown/PageUp works too).

## What's live and what's recorded

- With `YOU_API_KEY` set, opening `/demo` plans the goal live through You.com. The top-right chip reads **Live · You.com** with the measured time.
- If live planning fails, `/demo` shows the newest recorded run. The chip reads **Recorded run** with the time it ran.
- To record the video from the same run every take, pin the packaged run:
  http://localhost:3000/demo?run=557b1afb-8af2-4ecb-b5e0-1c79dcd10be8
- If the backend isn't running at all, the app shows sample data with a pale gold "Sample data, not from a live run" bar. Don't record in that state.
- The Shared Brain and N+1 numbers come from a recorded evaluation (`data/memory_v2_runs.json`, n=20 runs per arm) and are shown with their sample sizes and caveat.

## Before you record

1. Open http://localhost:3000/demo once and step through all four screens so the first live search is done.
2. Reload the page, then record.
3. Other screens worth a look: `/` (enter any goal), `/run/latest`, `/brain`, `/lab`, `/model`.

## Troubleshooting

- **"Address already in use"**: something is already on port 8000 or 3000. Find it with `lsof -i :8000` (or `:3000`) and stop it, or start the backend with `PORT=8001 ./scripts/start_demo_backend.sh` and set `NEXT_PUBLIC_API_URL=http://localhost:8001` in `frontend/.env.local`, then run `npm run build` again.
- **The page shows the pale gold sample-data bar**: the backend isn't reachable. Check Terminal 1.
- **`python3.12: command not found`**: run `brew install python@3.12`, or use any `python3` that reports 3.11 or newer.
