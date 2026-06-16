"""
clones.py — The Cloning Logic & Evolutionary Selection (الاستنساخ والتطور الدارويني)
====================================================================================
Manages parallel "clone" agents with a HARD cap so the system can never spawn
an infinite number of workers and exhaust CPU/RAM/API quota.

Each clone runs the same engine loop but with its OWN optimized system prompt
(see prompts.generate_clone_prompt) on its own sub-goal, and writes to the same
shared memory so the team learns collectively.

Evolutionary Selection: clones report a score (lower time / fewer errors is
better). `best_result()` returns the winning clone so its approach can be
promoted as the reference ("Master Code") strategy.
"""

import threading
import time

import engine
import memory
import prompts

# Hard limit — never exceed this many active clones at once.
MAX_CLONES = 10

_lock = threading.Lock()
_active: dict[str, dict] = {}
_finished: list[dict] = []  # scoreboard history for evolutionary selection


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

    # Recursive Prompt Optimization: build a tailored prompt for this clone.
    clone_prompt = prompts.generate_clone_prompt(specialty, goal)

    def _worker():
        errors = 0
        for ev in engine.run_agent(goal, author=name, system_prompt=clone_prompt):
            record["events"].append(ev)
            if ev.get("type") == "error":
                errors += 1
        elapsed = time.time() - record["started"]
        record["score"] = round(elapsed + errors * 30, 2)  # lower is better
        record["status"] = "done"
        memory.add_lesson(
            topic=f"clone-result:{specialty}",
            content=f"Clone {name} finished '{goal}' in {elapsed:.1f}s, {errors} errors.",
            author=name,
            score=-record["score"],
        )
        with _lock:
            _finished.append({k: v for k, v in record.items() if k != "events"})
            _active.pop(name, None)

    threading.Thread(target=_worker, daemon=True).start()
    return {"spawned": name, "specialty": specialty, "prompt_preview": clone_prompt[:160]}


def clone_events(name: str, limit: int = 100) -> list[dict]:
    """Live event stream of a single clone (for showing its thinking in the UI)."""
    with _lock:
        rec = _active.get(name)
        if rec:
            return rec["events"][-limit:]
    return []


def status() -> list[dict]:
    with _lock:
        return [
            {k: v for k, v in rec.items() if k != "events"}
            for rec in _active.values()
        ]


def best_result() -> dict | None:
    """Evolutionary Selection: the finished clone with the best (lowest) score."""
    with _lock:
        if not _finished:
            return None
        return min(_finished, key=lambda r: (r["score"] is None, r["score"]))
