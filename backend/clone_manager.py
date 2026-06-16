"""
Clone manager - controls specialized self-replication (Stage 3).

The agent may spawn copies of itself, but the total active count is locked
at MAX_CLONES. Each clone is given a ROLE so the swarm divides labour the way
a real team does:

    manager     coordinates the others and assigns tasks
    coder       writes and edits source
    designer    works on the UI / frontend
    researcher  searches the web and gathers information
    generalist  anything

The manager can assign tasks to the specialists; every spawn, task and
termination is written to the tamper-evident audit log.
"""
from __future__ import annotations

import threading
import time
import uuid

import config
from governor import governor


class CloneManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clones: dict[str, dict] = {}

    def count(self) -> int:
        return len(self._clones)

    def can_spawn(self) -> bool:
        return self.count() < config.MAX_CLONES

    def roles(self) -> dict:
        """How the active swarm is currently split across roles."""
        out: dict[str, int] = {}
        for c in self._clones.values():
            out[c["role"]] = out.get(c["role"], 0) + 1
        return out

    def spawn(self, purpose: str = "", role: str = "generalist") -> dict:
        role = role if role in config.CLONE_ROLES else "generalist"
        with self._lock:
            if len(self._clones) >= config.MAX_CLONES:
                return {
                    "ok": False,
                    "reason": f"clone limit reached ({config.MAX_CLONES})",
                    "active": len(self._clones),
                }
            clone_id = f"clone-{role}-{uuid.uuid4().hex[:6]}"
            record = {
                "id": clone_id,
                "role": role,
                "purpose": purpose,
                "created_at": time.time(),
                "status": "active",
                "tasks": [],
            }
            self._clones[clone_id] = record
        governor.audit.record("agent", "spawn_clone",
                              rationale=purpose or "n/a", level=0,
                              detail={"id": clone_id, "role": role})
        return {"ok": True, "clone": record, "active": len(self._clones),
                "roles": self.roles()}

    def assign_task(self, clone_id: str, task: str) -> dict:
        with self._lock:
            rec = self._clones.get(clone_id)
            if not rec:
                return {"ok": False, "reason": "clone not found"}
            rec["tasks"].append({"task": task, "at": time.time(), "status": "open"})
        governor.audit.record("agent", "assign_task", rationale=task, level=0,
                              detail={"clone": clone_id})
        return {"ok": True, "clone": clone_id, "task": task}

    def terminate(self, clone_id: str) -> dict:
        with self._lock:
            rec = self._clones.pop(clone_id, None)
            if not rec:
                return {"ok": False, "reason": "not found"}
        governor.audit.record("agent", "terminate_clone", level=0,
                              detail={"id": clone_id})
        return {"ok": True, "terminated": clone_id, "active": len(self._clones)}

    def list_clones(self) -> list[dict]:
        return list(self._clones.values())


# Single shared instance so the operator panel and the agent see the same
# live clone count (a fresh CloneManager per request would always show 0).
clones = CloneManager()
