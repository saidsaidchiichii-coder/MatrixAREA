"""
MatrixAREA - Central configuration.
All runtime settings live here. API keys are read from the environment,
never hardcoded.
"""
import os
from pathlib import Path

# --- Paths ---------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
SANDBOX_DIR = ROOT_DIR / "sandbox_world"      # isolated working area
SOURCE_MIRROR = SANDBOX_DIR / "self_source"   # agent's own code, exposed to itself
TOOLS_DIR = SANDBOX_DIR / "tools"             # tools the agent builds for itself
MEMORY_DIR = ROOT_DIR / "memory"
SNAPSHOT_DIR = ROOT_DIR / "snapshots"         # version history for rollback

for _p in (SANDBOX_DIR, SOURCE_MIRROR, TOOLS_DIR, MEMORY_DIR, SNAPSHOT_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# --- Model ---------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# --- Tool belt / web search ---------------------------------------------
# The agent builds its own Python tools under TOOLS_DIR and can search the
# web. Default search provider is Exa (set EXA_API_KEY in the environment).
SEARCH_PROVIDER = os.getenv("MATRIX_SEARCH", "exa")
EXA_API_KEY = os.getenv("EXA_API_KEY", "")

# --- Specialized clones --------------------------------------------------
# When the agent replicates it can give each clone a role so the swarm
# divides labour (a manager coordinates the coders and designers).
CLONE_ROLES = {"manager", "coder", "designer", "researcher", "generalist"}

# --- Limits --------------------------------------------------------------
MAX_CLONES = 10            # hard cap, never exceeded
MAX_STEPS_PER_RUN = 25     # safety bound on the think-act loop
EXEC_TIMEOUT = 30          # seconds per sandbox command

# --- Governance (the Boss / Human Feedback Loop) -------------------------
# Level-3 changes (architecture / system prompt / core files) are the
# "dangerous" ones: they require the operator's explicit approval before the
# agent may apply them. Toggle this off only if you want fully autonomous L3.
REQUIRE_L3_APPROVAL = os.getenv("MATRIX_REQUIRE_L3", "1") == "1"
APPROVAL_TIMEOUT = 300     # seconds the agent waits for a boss decision on L3
AUDIT_LOG = MEMORY_DIR / "audit.jsonl"   # append-only, tamper-evident ledger

# Core source files: editing any of these is always classified Level 3.
CORE_FILES = {
    "backend/agent.py",
    "backend/main.py",
    "backend/config.py",
    "backend/governor.py",
    "backend/evolution.py",
    "backend/sandbox.py",
    "backend/clone_manager.py",
}

# --- Server --------------------------------------------------------------
HOST = os.getenv("MATRIX_HOST", "127.0.0.1")
PORT = int(os.getenv("MATRIX_PORT", "8000"))
