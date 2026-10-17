from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from wimbl.config import settings
from wimbl.controller import TripController
from wimbl.memory import SharedMemory
from wimbl.schemas import TripRequest
from wimbl.improvement import evaluate_candidate

app = FastAPI(title="Wimbl", version="0.1.0", description="Evidence-backed event-led travel discovery and agent improvement.")
controller = TripController()
memory = SharedMemory()

@app.get("/api/health")
async def health():
    return {"ok": True, "app": "Wimbl", "demo_mode": settings.wimbl_demo_mode,
            "you_configured": bool(settings.you_api_key), "crusoe_configured": bool(settings.crusoe_api_key)}

@app.post("/api/trips/discover")
async def discover(request: TripRequest):
    try: return await controller.run(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Trip discovery failed: {type(exc).__name__}: {exc}") from exc

@app.get("/api/memory")
async def get_memory(scope: str | None = None, limit: int = 50):
    return {"entries": memory.list(scope=scope, limit=limit)}

@app.post("/api/improvement/evaluate")
async def improvement(payload: dict):
    return evaluate_candidate(payload or {"checks": {}})

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse((Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8"))
