"""
Governor - the Boss Panel brain (the Human Feedback Loop).

This module is the operator's authority over the agent. It holds:

  * the live FOCUS directive ("work only on memory management right now"),
  * control switches the operator can flip at any moment
        - pause_cloning      : agent may not spawn new clones
        - pause_evolution    : agent may not change its own source / prompt
        - halt               : agent must stop the current run immediately,
  * an approval queue for Level-3 (architectural) changes, which the agent
    is NOT allowed to apply until the boss explicitly approves them,
  * an append-only, tamper-evident AUDIT LOG that records every order,
    decision, evolution and override - the agent can never hide what it did.

There is a single shared GOVERNOR instance used by the whole process so the
HTTP endpoints, the WebSocket loop and the agent thread all see the same
state in real time.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from typing import Optional

import config


# ---------------------------------------------------------------------------
# Audit log - append-only ledger with a hash chain (tamper-evident).
# Each record embeds the hash of the previous record, so removing or editing
# any line breaks the chain and is detectable. The file lives OUTSIDE the
# sandbox world, so the agent's confined file tools cannot reach it.
# ---------------------------------------------------------------------------
class AuditLog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.path = config.AUDIT_LOG
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def _last_hash(self) -> str:
        last = "GENESIS"
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    last = json.loads(line).get("hash", last)
        except Exception:  # noqa: BLE001
            pass
        return last

    def record(self, actor: str, action: str, rationale: str = "",
               level: int = 0, detail: Optional[dict] = None) -> dict:
        """Append one immutable entry. `rationale` answers WHY it happened."""
        with self._lock:
            prev = self._last_hash()
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "actor": actor,            # "operator" or "agent"
                "action": action,
                "level": level,            # 0=info 1=optimize 2=feature 3=arch
                "rationale": rationale,    # the "why" - mandatory for changes
                "detail": detail or {},
                "prev": prev,
            }
            entry["hash"] = hashlib.sha256(
                (prev + json.dumps(entry, sort_keys=True)).encode("utf-8")
            ).hexdigest()[:16]
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
            return entry

    def tail(self, n: int = 100) -> list[dict]:
        try:
            lines = [l for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]
        except Exception:  # noqa: BLE001
            return []
        return [json.loads(l) for l in lines[-n:]]

    def verify(self) -> dict:
        """Walk the chain and confirm nothing was tampered with."""
        prev = "GENESIS"
        count = 0
        for line in [l for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]:
            rec = json.loads(line)
            stored = rec.pop("hash", "")
            recomputed = hashlib.sha256(
                (rec.get("prev", "") + json.dumps(rec, sort_keys=True)).encode("utf-8")
            ).hexdigest()[:16]
            if rec.get("prev") != prev or recomputed != stored:
                return {"intact": False, "broken_at": count}
            prev = stored
            count += 1
        return {"intact": True, "entries": count}


# ---------------------------------------------------------------------------
# Governor - the operator's live control surface.
# ---------------------------------------------------------------------------
class Governor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.audit = AuditLog()

        self.focus: str = ""            # current directive, "" = no override
        self.pause_cloning: bool = False
        self.pause_evolution: bool = False
        self.halt: bool = False

        self._directives: list[dict] = []     # history of operator overrides
        self._pending: dict[str, dict] = {}    # id -> L3 change awaiting approval

    # -- operator overrides ---------------------------------------------
    def set_focus(self, text: str) -> dict:
        with self._lock:
            self.focus = (text or "").strip()
            self._directives.append({"ts": time.time(), "focus": self.focus})
        self.audit.record("operator", "set_focus", rationale="operator override",
                          detail={"focus": self.focus})
        return {"ok": True, "focus": self.focus}

    def set_control(self, *, pause_cloning=None, pause_evolution=None, halt=None) -> dict:
        with self._lock:
            if pause_cloning is not None:
                self.pause_cloning = bool(pause_cloning)
            if pause_evolution is not None:
                self.pause_evolution = bool(pause_evolution)
            if halt is not None:
                self.halt = bool(halt)
            snap = self.controls()
        self.audit.record("operator", "set_control", rationale="operator override",
                          detail=snap)
        return {"ok": True, **snap}

    def clear_halt(self) -> dict:
        with self._lock:
            self.halt = False
        self.audit.record("operator", "clear_halt", rationale="operator resumed run")
        return {"ok": True}

    def controls(self) -> dict:
        return {
            "focus": self.focus,
            "pause_cloning": self.pause_cloning,
            "pause_evolution": self.pause_evolution,
            "halt": self.halt,
        }

    # -- Level-3 approval queue -----------------------------------------
    def submit_for_approval(self, kind: str, payload: dict, rationale: str) -> str:
        """Agent parks a Level-3 change here and must wait for a decision."""
        with self._lock:
            cid = f"chg-{uuid.uuid4().hex[:8]}"
            self._pending[cid] = {
                "id": cid, "kind": kind, "payload": payload,
                "rationale": rationale, "status": "pending",
                "created_at": time.time(),
            }
        self.audit.record("agent", "request_approval", rationale=rationale, level=3,
                          detail={"id": cid, "kind": kind})
        return cid

    def resolve(self, cid: str, approved: bool, note: str = "") -> dict:
        with self._lock:
            rec = self._pending.get(cid)
            if not rec:
                return {"ok": False, "reason": "not found"}
            rec["status"] = "approved" if approved else "rejected"
            rec["note"] = note
        self.audit.record("operator", "approve" if approved else "reject",
                          rationale=note or "operator decision", level=3,
                          detail={"id": cid, "kind": rec["kind"]})
        return {"ok": True, "id": cid, "status": rec["status"]}

    def wait_for_decision(self, cid: str, timeout: int) -> str:
        """Block (poll) until the boss approves/rejects, halts, or times out."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self.halt:
                    return "halted"
                rec = self._pending.get(cid, {})
                if rec.get("status") in ("approved", "rejected"):
                    return rec["status"]
            time.sleep(1)
        return "timeout"

    def pending(self) -> list[dict]:
        with self._lock:
            return [r for r in self._pending.values() if r["status"] == "pending"]


# Single shared instance for the whole process.
governor = Governor()
