"""
Toolsmith - the agent forges its own tools (Stage 2: tool building).

This is what turns MatrixAREA from a chatbot into a real agent: it can write
a new Python tool, register it, and call it later. Each tool is a file in
sandbox_world/tools/ that exposes `run(args: dict)`. Tools execute in a
subprocess whose working directory is confined to the sandbox.

A registry.json keeps name -> metadata so the agent (and the operator) can
see what tools the swarm has built over time.
"""
from __future__ import annotations

import json
import subprocess
import time

import config

REGISTRY = config.TOOLS_DIR / "registry.json"

TEMPLATE_HINT = (
    "# A MatrixAREA tool. Must define run(args: dict) and return a JSON-able value.\n"
    "def run(args):\n    return {'echo': args}\n"
)


def _load() -> dict:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save(reg: dict) -> None:
    config.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=2), encoding="utf-8")


def build_tool(name: str, code: str, description: str = "") -> dict:
    safe = "".join(c for c in (name or "") if c.isalnum() or c in "_-")
    if not safe:
        return {"ok": False, "error": "invalid tool name"}
    if "def run(" not in code:
        return {"ok": False, "error": "tool code must define run(args)"}
    config.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    (config.TOOLS_DIR / f"{safe}.py").write_text(code, encoding="utf-8")
    reg = _load()
    reg[safe] = {
        "description": description,
        "file": f"{safe}.py",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _save(reg)
    return {"ok": True, "tool": safe, "registered": list(reg.keys())}


def list_tools() -> dict:
    return _load()


def run_tool(name: str, args: dict | None = None) -> dict:
    reg = _load()
    if name not in reg:
        return {"ok": False, "error": f"tool not found: {name}"}
    path = config.TOOLS_DIR / reg[name]["file"]
    runner = (
        "import json,sys\n"
        "ns={}\n"
        f"exec(open(r'{path}').read(), ns)\n"
        "print(json.dumps(ns['run'](json.loads(sys.stdin.read() or '{}'))))\n"
    )
    try:
        proc = subprocess.run(
            ["python3", "-c", runner],
            input=json.dumps(args or {}),
            cwd=str(config.SANDBOX_DIR),
            capture_output=True, text=True, timeout=config.EXEC_TIMEOUT,
        )
        if proc.returncode != 0:
            return {"ok": False, "error": proc.stderr[-1200:]}
        return {"ok": True, "output": proc.stdout[-3000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "[timeout]"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
