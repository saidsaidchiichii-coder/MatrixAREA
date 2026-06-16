"""
staging.py — Staging Area & Self-Testing (التجربة والخطأ)
=========================================================
The AI never applies a code change blindly. It proposes an edit + a test; we
run the edited file together with the test inside an isolated staging folder.
Only if the test passes do we "promote" the change to the AI's evolving source
copy (self_source/). The live backend is never touched here.

Flow:
  propose_self_edit(target, new_content, test_code)
    1. copy current self_source -> staging/
    2. write new_content over target in staging/
    3. write test_code as staging/__selftest.py
    4. run it; capture pass/fail
    5. if pass -> copy staged target back into self_source/  (promote)
       if fail -> discard, return the error so the AI can try again
"""

import shutil
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent / "sandbox_workspace"
SELF_DIR = WORKSPACE / "self_source"
STAGING = WORKSPACE / "staging"


def propose_self_edit(target: str, new_content: str, test_code: str, timeout: int = 30) -> dict:
    """Test a proposed edit in isolation; promote only if the test passes."""
    if not SELF_DIR.exists():
        return {"error": "source not injected yet — call inject_source first"}

    # Confine target to the self_source tree (no escapes).
    staged_target = (STAGING / target).resolve()
    if not str(staged_target).startswith(str((STAGING).resolve())):
        return {"error": f"path escape blocked: {target}"}

    # 1-2. Fresh staging copy + apply the edit.
    if STAGING.exists():
        shutil.rmtree(STAGING)
    shutil.copytree(SELF_DIR, STAGING)
    staged_target.parent.mkdir(parents=True, exist_ok=True)
    staged_target.write_text(new_content, encoding="utf-8")

    # 3. Drop the self-test.
    (STAGING / "__selftest.py").write_text(test_code, encoding="utf-8")

    # 4. Run the test inside staging.
    try:
        proc = subprocess.run(
            ["python3", "__selftest.py"],
            cwd=str(STAGING),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"promoted": False, "passed": False, "error": "test timed out"}

    passed = proc.returncode == 0
    result = {
        "passed": passed,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }

    # 5. Promote on success.
    if passed:
        promoted_path = (SELF_DIR / target)
        promoted_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged_target, promoted_path)
        result["promoted"] = True
        result["note"] = f"{target} updated in self_source/ (evolving copy)."
    else:
        result["promoted"] = False
        result["note"] = "Test failed — change discarded. Fix and retry."

    return result
