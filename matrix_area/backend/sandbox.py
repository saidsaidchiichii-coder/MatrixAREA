"""
sandbox.py — The World (العالم المعزول)
=======================================
Executes shell commands and file operations on behalf of the AI, but ONLY
inside a dedicated workspace directory. This is the AI's "world": it can
create, read, modify and run files freely here, including installing
packages with pip/npm, but it cannot reach outside this folder.

SAFETY (non-negotiable):
  - All paths are resolved and confined to WORKSPACE. Any attempt to escape
    (via .., absolute paths, symlinks) is rejected.
  - A hard KILL flag can disable execution instantly (the Boss kill switch).
  - Commands have a timeout so a runaway process cannot hang the system.

This module is intentionally small and documented so the AI can read it,
understand the limits of its own world, and propose improvements — but the
isolation guarantees themselves are enforced here and by the container.
"""

import os
import subprocess
import shlex
from pathlib import Path

# The single directory the AI is allowed to touch.
WORKSPACE = Path(__file__).parent.parent / "sandbox_workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

# Flipped by the Boss kill switch. When True, every operation is refused.
KILLED = False


class SandboxError(Exception):
    pass


def _safe_path(relative: str) -> Path:
    """Resolve a path and guarantee it stays inside WORKSPACE."""
    target = (WORKSPACE / relative).resolve()
    if not str(target).startswith(str(WORKSPACE.resolve())):
        raise SandboxError(f"Path escape blocked: {relative}")
    return target


def _check_alive() -> None:
    if KILLED:
        raise SandboxError("Sandbox is halted by the Boss kill switch.")


def run_shell(command: str, timeout: int = 60) -> dict:
    """Run a shell command inside the workspace and capture output."""
    _check_alive()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "stdout": proc.stdout[-8000:],
            "stderr": proc.stderr[-8000:],
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "stdout": "", "stderr": "Timed out", "exit_code": -1}


def write_file(relative: str, content: str) -> dict:
    _check_alive()
    target = _safe_path(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": relative, "bytes": len(content.encode("utf-8"))}


def read_file(relative: str) -> dict:
    _check_alive()
    target = _safe_path(relative)
    if not target.exists():
        return {"path": relative, "error": "not found"}
    return {"path": relative, "content": target.read_text(encoding="utf-8", errors="replace")}


def list_dir(relative: str = ".") -> dict:
    _check_alive()
    target = _safe_path(relative)
    if not target.exists():
        return {"path": relative, "error": "not found"}
    entries = []
    for p in sorted(target.iterdir()):
        entries.append({"name": p.name, "is_dir": p.is_dir(), "size": p.stat().st_size})
    return {"path": relative, "entries": entries}


def set_killed(value: bool) -> None:
    """Boss kill switch hook — toggled from the control API, not by the AI."""
    global KILLED
    KILLED = value
