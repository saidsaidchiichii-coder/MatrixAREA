"""
Clone manager - controls self-replication with a hard ceiling.

The agent may spawn copies of itself, but the total active count is locked
at MAX_CLONES. The counter is guarded so concurrent requests cannot exceed it.
"""
from __future__ import annotations

import threading
import time
import uuid

from config import MAX_CLONES


class CloneManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clones: dict[str, dict] = {}

    def count(self) -> int:
        return len(self._clones)

    def can_spawn(self) -> bool:
        return self.count() < MAX_CLONES

    def spawn(self, purpose: str = "") -> dict:
        with self._lock:
            if len(self._clones) >= MAX_CLONES:
                return {
                    "ok": False,
                    "reason": f"clone limit reached ({MAX_CLONES})",
                    "active": len(self._clones),
                }
            clone_id = f"clone-{uuid.uuid4().hex[:8]}"
            record = {
                "id": clone_id,
                "purpose": purpose,
                "created_at": time.time(),
                "status": "active",
                "log": [],
            }
            self._clones[clone_id] = record
            return {"ok": True, "clone": record, "active": len(self._clones)}

    def terminate(self, clone_id: str) -> dict:
        with self._lock:
            rec = self._clones.pop(clone_id, None)
            if not rec:
                return {"ok": False, "reason": "not found"}
            return {"ok": True, "terminated": clone_id, "active": len(self._clones)}

    def list_clones(self) -> list[dict]:
        return list(self._clones.values())
