"""
MatrixAREA server - FastAPI backend that connects the operator panel to the
agent. The operator issues orders over a WebSocket and watches the agent's
think-act-observe stream in real time.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
import evolution
from agent import Agent

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="MatrixAREA")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/state")
async def state() -> dict:
    agent = Agent()
    return {
        "model": config.GEMINI_MODEL,
        "key_set": bool(config.GEMINI_API_KEY),
        "max_clones": config.MAX_CLONES,
        "active_clones": agent.clones.count(),
        "snapshots": evolution.list_snapshots()[-20:],
        "system_prompt": evolution.get_system_prompt(),
        "source_files": agent.sandbox.list_files("self_source"),
    }


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
                "active_clones": agent.clones.count(),
                "max_clones": config.MAX_CLONES,
            }))
    except WebSocketDisconnect:
        return


# serve static assets (styles.css, app.js)
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
