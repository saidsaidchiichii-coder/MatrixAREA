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

from config import SOURCE_MIRROR, SNAPSHOT_DIR, MEMORY_DIR

PROMPT_FILE = MEMORY_DIR / "system_prompt.txt"

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


def update_system_prompt(new_prompt: str) -> str:
    old = get_system_prompt()
    snap = _snapshot("prompt", {"old": old, "new": new_prompt})
    PROMPT_FILE.write_text(new_prompt, encoding="utf-8")
    return f"system prompt updated (snapshot {snap})"


def evolve_source(rel_path: str, new_content: str) -> str:
    """Modify a mirrored source file, snapshotting the previous version."""
    target = (SOURCE_MIRROR / rel_path).resolve()
    if not str(target).startswith(str(SOURCE_MIRROR.resolve())):
        return "[error] path escapes self_source"
    old = target.read_text(encoding="utf-8") if target.exists() else ""
    snap = _snapshot("source", {"path": rel_path, "old": old, "new": new_content})
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")
    return f"source {rel_path} evolved (snapshot {snap})"


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
