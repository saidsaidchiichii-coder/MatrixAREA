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
MEMORY_DIR = ROOT_DIR / "memory"
SNAPSHOT_DIR = ROOT_DIR / "snapshots"         # version history for rollback

for _p in (SANDBOX_DIR, SOURCE_MIRROR, MEMORY_DIR, SNAPSHOT_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# --- Model ---------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# --- Limits --------------------------------------------------------------
MAX_CLONES = 10            # hard cap, never exceeded
MAX_STEPS_PER_RUN = 25     # safety bound on the think-act loop
EXEC_TIMEOUT = 30          # seconds per sandbox command

# --- Server --------------------------------------------------------------
HOST = os.getenv("MATRIX_HOST", "127.0.0.1")
PORT = int(os.getenv("MATRIX_PORT", "8000"))
