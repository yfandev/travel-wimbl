#!/usr/bin/env bash
# Start the WIMBL backend for the demo on http://localhost:8000.
# Any live data file missing from data/ is seeded from demo_data/ (a recorded You.com run, the model-call log, and the
# Shared Brain lesson DB). Existing files in data/ are never overwritten.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p data
for f in runs.jsonl run_log.jsonl memory_v2.sqlite3; do
  if [ ! -e "data/$f" ]; then
    cp "demo_data/$f" "data/$f"
    echo "Seeded data/$f from demo_data/"
  fi
done

if [ ! -x .venv/bin/uvicorn ]; then
  echo "Missing .venv. Run: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

export WIMBL_LESSONS_DB=./data/memory_v2.sqlite3
exec .venv/bin/uvicorn wimbl.api:app --port "${PORT:-8000}"
