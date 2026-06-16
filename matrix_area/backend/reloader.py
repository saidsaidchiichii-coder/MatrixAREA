"""
reloader.py — Hot-Reload (إعادة التحميل الحي)
=============================================
After the agent has tested a self-edit in the staging area (staging.py) and it
was promoted into self_source/, this module can push that tested file into the
LIVE backend and reload it in-process — so the system starts running the
improved code without a full restart. This is the real "self-evolution" step.

SAFETY (non-negotiable):
  - PROTECTED modules are NEVER hot-reloaded. The kill switch (sandbox.py) and
    the API server core (main.py) stay fixed, so the Boss always keeps control.
  - Only files that already exist (and passed a staging test) can be reloaded.
"""

import sys
import shutil
import importlib
from pathlib import Path

BACKEND = Path(__file__).parent
SELF_BACKEND = BACKEND.parent / "sandbox_workspace" / "self_source" / "backend"

# These can never be replaced at runtime — they hold the Boss's control.
PROTECTED = {"sandbox", "main", "reloader"}


def hot_reload(module_name: str) -> dict:
    """Promote a tested self_source module into the live process and reload it."""
    if module_name in PROTECTED:
        return {"error": f"'{module_name}' is protected (kill switch / server core) — cannot hot-reload."}

    src = SELF_BACKEND / f"{module_name}.py"
    if not src.exists():
        return {"error": f"No tested source for '{module_name}' in self_source/. Use propose_self_edit first."}

    # Copy the tested-and-promoted file over the live module, then reload it.
    shutil.copy2(src, BACKEND / f"{module_name}.py")
    if module_name in sys.modules:
        try:
            importlib.reload(sys.modules[module_name])
            return {"reloaded": module_name, "live": True, "note": "running improved code now"}
        except Exception as exc:  # noqa: BLE001
            return {"reloaded": module_name, "live": False, "error": str(exc)}
    return {"error": f"'{module_name}' is not currently loaded in the process."}
