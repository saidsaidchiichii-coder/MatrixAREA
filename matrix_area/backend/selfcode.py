"""
selfcode.py — Source Code Injection (حقن الكود المصدري)
=======================================================
Gives MATRIX awareness of its own source code. On startup we copy the whole
backend + frontend into the sandbox workspace under `self_source/`, then tell
the agent: "this is YOUR source code — you may read it and understand your own
logic."

IMPORTANT boundary: the agent reads/edits its source ONLY inside the workspace
copy (self_source/). The live, running backend and the Boss kill switch are
NOT replaced from here — that protection is intentional and non-negotiable.
"""

import shutil
from pathlib import Path

BACKEND = Path(__file__).parent
FRONTEND = BACKEND.parent / "frontend"
WORKSPACE = BACKEND.parent / "sandbox_workspace"
SELF_DIR = WORKSPACE / "self_source"


def inject_source() -> dict:
    """Copy the system's own source into the AI's workspace and return a manifest."""
    if SELF_DIR.exists():
        shutil.rmtree(SELF_DIR)
    (SELF_DIR / "backend").mkdir(parents=True, exist_ok=True)
    (SELF_DIR / "frontend").mkdir(parents=True, exist_ok=True)

    manifest = []
    for src in BACKEND.glob("*.py"):
        dst = SELF_DIR / "backend" / src.name
        shutil.copy2(src, dst)
        manifest.append(f"self_source/backend/{src.name}")
    for src in FRONTEND.glob("*"):
        if src.is_file():
            dst = SELF_DIR / "frontend" / src.name
            shutil.copy2(src, dst)
            manifest.append(f"self_source/frontend/{src.name}")

    return {"injected": True, "files": manifest, "root": "self_source/"}


def source_summary() -> str:
    """A short text the agent receives so it knows its own code exists."""
    files = []
    if SELF_DIR.exists():
        for p in sorted(SELF_DIR.rglob("*")):
            if p.is_file():
                files.append(str(p.relative_to(WORKSPACE)))
    listing = "\n".join(f"  - {f}" for f in files)
    return (
        "This is YOUR own source code, copied into your workspace under "
        "'self_source/'. You can read it to understand your own logic and "
        "propose improvements (via propose_self_edit, which tests changes in a "
        "staging area first). You CANNOT replace the live running process or "
        "the Boss kill switch.\n"
        f"Your source files:\n{listing}"
    )
