"""
Sandbox - the isolated world the agent operates inside.

Every file operation and command is confined to SANDBOX_DIR. Any attempt to
read or write outside that boundary is rejected. The agent has full freedom
*inside* this directory and none outside it.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from config import SANDBOX_DIR, EXEC_TIMEOUT


def _resolve_inside(rel_path: str) -> Path:
    """Resolve a path and guarantee it stays within the sandbox."""
    target = (SANDBOX_DIR / rel_path).resolve()
    if not str(target).startswith(str(SANDBOX_DIR.resolve())):
        raise PermissionError(f"Path escapes sandbox: {rel_path}")
    return target


class Sandbox:
    """Confined filesystem + command execution."""

    def list_files(self, rel_path: str = ".") -> list[str]:
        base = _resolve_inside(rel_path)
        if not base.exists():
            return []
        out = []
        for p in sorted(base.rglob("*")):
            if p.is_file():
                out.append(str(p.relative_to(SANDBOX_DIR)))
        return out

    def read_file(self, rel_path: str) -> str:
        target = _resolve_inside(rel_path)
        if not target.exists():
            return f"[error] file not found: {rel_path}"
        return target.read_text(encoding="utf-8", errors="replace")

    def write_file(self, rel_path: str, content: str) -> str:
        target = _resolve_inside(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"[ok] wrote {len(content)} bytes to {rel_path}"

    def execute(self, command: str) -> dict:
        """Run a shell command, confined to the sandbox working directory."""
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(SANDBOX_DIR),
                capture_output=True,
                text=True,
                timeout=EXEC_TIMEOUT,
            )
            return {
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-2000:],
                "exit_code": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "[timeout]", "exit_code": -1}
        except Exception as exc:  # noqa: BLE001
            return {"stdout": "", "stderr": f"[error] {exc}", "exit_code": -1}
