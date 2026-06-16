"""
Evolution - lets the agent rewrite its own source and system prompt.

Every change is snapshotted before it is applied, so any modification can be
rolled back. The agent's own source is mirrored into the sandbox so it can
read and study itself.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import config
from config import SOURCE_MIRROR, SNAPSHOT_DIR, MEMORY_DIR, CORE_FILES
from governor import governor

PROMPT_FILE = MEMORY_DIR / "system_prompt.txt"

# Evolution levels (see README - the 3 levels of self-evolution):
#   1  Optimization        - tidy code, comments, small bug fixes
#   2  Feature Engineering  - new tools / new files added to itself
#   3  Architectural Change - core files, framework, or system prompt
LEVEL_NAMES = {1: "optimization", 2: "feature-engineering", 3: "architectural"}


def classify_level(rel_path: str, file_existed: bool, declared: int = 0) -> int:
    """Decide how dangerous a source change is. Never lower than declared."""
    norm = rel_path.replace("\\", "/").lstrip("./")
    if not norm.startswith("backend/") and not norm.startswith("frontend/"):
        norm = f"backend/{norm}" if norm.endswith(".py") else norm
    if norm in CORE_FILES:
        level = 3                      # touching the brain/spine == architectural
    elif not file_existed:
        level = 2                      # brand-new file == new feature/tool
    else:
        level = 1                      # editing a non-core file == optimization
    return max(level, declared or 0)

DEFAULT_PROMPT = """You are MatrixAREA, an autonomous agent living inside an isolated sandbox.
You can read and rewrite your own source, run code, and spawn up to 10 clones.
Operate only inside the sandbox. Improve yourself deliberately and keep a clear
record of what you change and why."""


def mirror_self(source_dir: Path) -> str:
    """Copy the agent's real source into the sandbox so it can see itself."""
    if SOURCE_MIRROR.exists():
        shutil.rmtree(SOURCE_MIRROR)
    shutil.copytree(source_dir, SOURCE_MIRROR)
    files = [str(p.relative_to(SOURCE_MIRROR)) for p in SOURCE_MIRROR.rglob("*") if p.is_file()]
    return f"mirrored {len(files)} source files into sandbox/self_source"


def get_system_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8")
    PROMPT_FILE.write_text(DEFAULT_PROMPT, encoding="utf-8")
    return DEFAULT_PROMPT


def _snapshot(label: str, payload: dict) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    snap = SNAPSHOT_DIR / f"{ts}-{label}.json"
    snap.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return snap.name


def update_system_prompt(new_prompt: str, rationale: str = "") -> str:
    """Change how the agent thinks. This is ALWAYS a Level-3 change and is
    gated behind operator approval when REQUIRE_L3_APPROVAL is on."""
    if governor.pause_evolution:
        return "[blocked] evolution paused by operator"
    if config.REQUIRE_L3_APPROVAL:
        cid = governor.submit_for_approval(
            "update_system_prompt", {"new": new_prompt}, rationale)
        decision = governor.wait_for_decision(cid, config.APPROVAL_TIMEOUT)
        if decision != "approved":
            return f"[denied] system-prompt change not approved ({decision})"
    old = get_system_prompt()
    snap = _snapshot("prompt", {"old": old, "new": new_prompt, "rationale": rationale})
    PROMPT_FILE.write_text(new_prompt, encoding="utf-8")
    governor.audit.record("agent", "update_system_prompt", rationale=rationale,
                          level=3, detail={"snapshot": snap})
    return f"system prompt updated [L3 architectural] (snapshot {snap})"


def evolve_source(rel_path: str, new_content: str, rationale: str = "",
                  declared_level: int = 0) -> str:
    """Modify a mirrored source file, snapshotting the previous version.

    The change is classified into a level (1/2/3). Level-3 changes (core
    files / architecture) require operator approval first. Every applied
    change is written to the tamper-evident audit log with its rationale."""
    if governor.pause_evolution:
        return "[blocked] evolution paused by operator"
    target = (SOURCE_MIRROR / rel_path).resolve()
    if not str(target).startswith(str(SOURCE_MIRROR.resolve())):
        return "[error] path escapes self_source"
    file_existed = target.exists()
    level = classify_level(rel_path, file_existed, declared_level)

    if level >= 3 and config.REQUIRE_L3_APPROVAL:
        cid = governor.submit_for_approval(
            "evolve_source",
            {"path": rel_path, "preview": new_content[:500]},
            rationale)
        decision = governor.wait_for_decision(cid, config.APPROVAL_TIMEOUT)
        if decision != "approved":
            return f"[denied] L3 change to {rel_path} not approved ({decision})"

    old = target.read_text(encoding="utf-8") if file_existed else ""
    snap = _snapshot("source", {"path": rel_path, "old": old,
                                "new": new_content, "rationale": rationale,
                                "level": level})
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")
    governor.audit.record("agent", "evolve_source", rationale=rationale,
                          level=level, detail={"path": rel_path, "snapshot": snap})
    return f"source {rel_path} evolved [L{level} {LEVEL_NAMES[level]}] (snapshot {snap})"


def list_snapshots() -> list[str]:
    return sorted(p.name for p in SNAPSHOT_DIR.glob("*.json"))


def rollback(snapshot_name: str) -> str:
    snap = SNAPSHOT_DIR / snapshot_name
    if not snap.exists():
        return "[error] snapshot not found"
    data = json.loads(snap.read_text(encoding="utf-8"))
    if "path" in data:  # source snapshot
        target = SOURCE_MIRROR / data["path"]
        target.write_text(data["old"], encoding="utf-8")
        return f"rolled back source {data['path']}"
    PROMPT_FILE.write_text(data["old"], encoding="utf-8")  # prompt snapshot
    return "rolled back system prompt"
