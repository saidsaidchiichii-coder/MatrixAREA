"""
clones.py — The Cloning Logic (نظام الاستنساخ)
==============================================
Manages parallel "clone" agents with a HARD cap so the system can never spawn
an infinite number of workers and exhaust CPU/RAM/API quota.

Each clone runs the same engine loop but on its own sub-goal and writes to the
same shared memory, so the team learns collectively. A simple scoreboard backs
the "Evolutionary Selection" idea: clones report a score (lower time / fewer
errors = better) and the best result can be promoted.
"""

import threading
import time
from typing import Optional

import engine
import memory

# Hard limit — never exceed this many active clones at once.
MAX_CLONES = 10

_lock = threading.Lock()
_active: dict[str, dict] = {}


def active_count() -> int:
    with _lock:
        return len(_active)


def spawn(name: str, goal: str, specialty: str = "generalist") -> dict:
    """Start a clone if we are under the hard limit."""
    with _lock:
        if len(_active) >= MAX_CLONES:
            return {"error": f"Clone limit reached ({MAX_CLONES})."}
        if name in _active:
            return {"error": f"Clone '{name}' already exists."}
        record = {
            "name": name,
            "goal": goal,
            "specialty": specialty,
            "started": time.time(),
            "status": "running",
            "score": None,
            "events": [],
        }
        _active[name] = record

    def _worker():
        errors = 0
        for ev in engine.run_agent(goal, author=name):
            record["events"].append(ev)
            if ev.get("type") == "error":
                errors += 1
        elapsed = time.time() - record["started"]
        # Lower is better: weight time and errors.
        record["score"] = round(elapsed + errors * 30, 2)
        record["status"] = "done"
        memory.add_lesson(
            topic=f"clone-result:{specialty}",
            content=f"Clone {name} finished goal '{goal}' in {elapsed:.1f}s with {errors} errors.",
            author=name,
            score=-record["score"],  # better score => higher rank
        )
        with _lock:
            _active.pop(name, None)

    threading.Thread(target=_worker, daemon=True).start()
    return {"spawned": name, "specialty": specialty}


def status() -> list[dict]:
    with _lock:
        return [
            {k: v for k, v in rec.items() if k != "events"}
            for rec in _active.values()
        ]
