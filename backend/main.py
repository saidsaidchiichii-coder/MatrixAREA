"""
MatrixAREA server - FastAPI backend that connects the operator panel to the
agent. The operator issues orders over a WebSocket and watches the agent's
think-act-observe stream in real time.

The Boss Panel talks to these HTTP endpoints:
  POST /api/override   set / clear the live FOCUS directive
  POST /api/control    flip pause_cloning, pause_evolution, halt
  POST /api/clear_halt resume after a halt
  GET  /api/pending    Level-3 changes awaiting approval
  POST /api/approve    approve / reject a pending Level-3 change
  GET  /api/audit      the tamper-evident audit ledger (+ integrity check)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
import evolution
import toolsmith
from agent import Agent
from clone_manager import clones as CLONES
from governor import governor

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="MatrixAREA")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/state")
async def state() -> dict:
    sb = Agent().sandbox
    return {
        "model": config.GEMINI_MODEL,
        "key_set": bool(config.GEMINI_API_KEY),
        "max_clones": config.MAX_CLONES,
        "active_clones": CLONES.count(),
        "clones": CLONES.list_clones(),
        "clone_roles": CLONES.roles(),
        "snapshots": evolution.list_snapshots()[-20:],
        "system_prompt": evolution.get_system_prompt(),
        "source_files": sb.list_files("self_source"),
        "ui_drafts": sb.list_files("self_source/frontend"),
        "tools": toolsmith.list_tools(),
        "search_provider": config.SEARCH_PROVIDER,
        "search_ready": bool(config.EXA_API_KEY),
        "controls": governor.controls(),
        "require_l3_approval": config.REQUIRE_L3_APPROVAL,
        "pending": governor.pending(),
    }


# --- Boss Panel control surface -----------------------------------------
@app.post("/api/override")
async def override(req: Request) -> dict:
    body = await req.json()
    return governor.set_focus(body.get("focus", ""))


@app.post("/api/control")
async def control(req: Request) -> dict:
    body = await req.json()
    return governor.set_control(
        pause_cloning=body.get("pause_cloning"),
        pause_evolution=body.get("pause_evolution"),
        halt=body.get("halt"),
    )


@app.post("/api/clear_halt")
async def clear_halt() -> dict:
    return governor.clear_halt()


@app.get("/api/pending")
async def pending() -> dict:
    return {"pending": governor.pending()}


@app.post("/api/approve")
async def approve(req: Request) -> dict:
    body = await req.json()
    return governor.resolve(
        body.get("id", ""), bool(body.get("approved", False)), body.get("note", ""))


@app.get("/api/audit")
async def audit() -> dict:
    return {"entries": governor.audit.tail(200), "integrity": governor.audit.verify()}


@app.websocket("/ws")
async def ws(socket: WebSocket) -> None:
    await socket.accept()
    loop = asyncio.get_event_loop()

    def emit(kind: str, payload: str) -> None:
        msg = json.dumps({"kind": kind, "payload": payload})
        asyncio.run_coroutine_threadsafe(socket.send_text(msg), loop)

    agent = Agent(emit=emit)
    try:
        while True:
            data = await socket.receive_text()
            order = json.loads(data).get("order", "").strip()
            if not order:
                continue
            # run the (blocking) agent loop in a worker thread
            await loop.run_in_executor(None, agent.run, order)
            emit("state", json.dumps({
                "active_clones": CLONES.count(),
                "max_clones": config.MAX_CLONES,
            }))
    except WebSocketDisconnect:
        return


# serve static assets (styles.css, app.js)
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
