import time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from wimbl import api_data
from wimbl.config import settings
from wimbl.controller import TripController
from wimbl.memory import SharedMemory
from wimbl.schemas import TripRequest
from wimbl.improvement import evaluate_candidate

app = FastAPI(title="Wimbl", version="0.1.0", description="Evidence-backed event-led travel discovery and agent improvement.")
# The Next.js app (travel-wimbl-frontend) proxies /api/* through its dev server; CORS also allows direct browser calls.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(api_data.router)  # read-only demo data: runs, run log, lessons, memory ablation, latest N+1 report
controller = TripController()
memory = SharedMemory()

@app.get("/api/health")
async def health():
    return {"ok": True, "app": "Wimbl", "demo_mode": settings.wimbl_demo_mode,
            "you_configured": bool(settings.you_api_key), "crusoe_configured": bool(settings.crusoe_api_key)}

@app.post("/api/trips/discover")
async def discover(request: TripRequest):
    started_at, t0 = datetime.now(timezone.utc), time.monotonic()
    try: result = await controller.run(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Trip discovery failed: {type(exc).__name__}: {exc}") from exc
    api_data.runs.record(request, result, started_at, round((time.monotonic() - t0) * 1000))
    return result

@app.get("/api/memory")
async def get_memory(scope: str | None = None, limit: int = 50):
    return {"entries": memory.list(scope=scope, limit=limit)}

@app.post("/api/improvement/evaluate")
async def improvement(payload: dict):
    return evaluate_candidate(payload or {"checks": {}})

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse((Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8"))
