"""
main.py — The Boss Panel API (واجهة المدير)
===========================================
FastAPI server that ties everything together and serves the dashboard.

Endpoints:
  POST /run            start an autonomous goal; streams thinking + actions (SSE)
  GET  /resources      live CPU/RAM snapshot for the resource charts
  GET  /events         recent shared-memory events (thinking timeline)
  POST /clone          spawn a specialised clone (respects MAX_CLONES)
  GET  /clones         status of active clones
  POST /kill           Boss kill switch — halt the sandbox immediately
  POST /revive         clear the kill switch
  GET  /               serves the frontend dashboard

The Boss watches; the AI acts. The kill switch lives here, outside the AI's
reach, exactly as the constitution requires.
"""

import json
from pathlib import Path

# Load the API key from .env if present (the file is git-ignored, never committed).
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent / ".env")
except Exception:
    pass

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import engine
import sandbox
import monitor
import memory
import clones

app = FastAPI(title="MATRIX — Project Mirror")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND = Path(__file__).parent.parent / "frontend"


class RunRequest(BaseModel):
    goal: str


class CloneRequest(BaseModel):
    name: str
    goal: str
    specialty: str = "generalist"


@app.post("/run")
def run(req: RunRequest):
    """Stream the autonomous agent loop as Server-Sent Events."""

    def gen():
        for ev in engine.run_agent(req.goal, author="master"):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        yield "data: {\"type\": \"stream_end\"}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/resources")
def resources():
    return monitor.snapshot()


@app.get("/events")
def events(limit: int = 50):
    return {"events": memory.recent_events(limit)}


@app.post("/clone")
def clone(req: CloneRequest):
    return clones.spawn(req.name, req.goal, req.specialty)


@app.get("/clones")
def clone_status():
    return {"active": clones.active_count(), "max": clones.MAX_CLONES, "clones": clones.status()}


@app.get("/clone_events")
def clone_events(name: str, limit: int = 100):
    """Live thinking/activity stream for a single clone (for the Boss Panel)."""
    return {"name": name, "events": clones.clone_events(name, limit)}


@app.get("/best_clone")
def best_clone():
    """Evolutionary Selection — the winning clone whose approach to promote."""
    return {"best": clones.best_result()}


@app.post("/kill")
def kill():
    """Hard kill switch — instantly halts all sandbox activity."""
    sandbox.set_killed(True)
    memory.log_event("kill_switch", {"state": "KILLED"}, "boss")
    return {"status": "KILLED"}


@app.post("/revive")
def revive():
    sandbox.set_killed(False)
    memory.log_event("kill_switch", {"state": "ALIVE"}, "boss")
    return {"status": "ALIVE"}


# Serve the dashboard at the root.
@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
