"""
monitor.py — The Resource Mirror (مراقب الموارد)
================================================
Lets the system (and the AI) see CPU, RAM and process counts in real time.
The AI uses this signal to learn to write "light" code that does not exhaust
the machine, and the Boss Panel charts it live.
"""

import psutil
import time


def snapshot() -> dict:
    """A single point-in-time reading of the host resources."""
    vm = psutil.virtual_memory()
    return {
        "ts": time.time(),
        "cpu_percent": psutil.cpu_percent(interval=0.0),
        "ram_percent": vm.percent,
        "ram_used_mb": round(vm.used / 1024 / 1024, 1),
        "ram_total_mb": round(vm.total / 1024 / 1024, 1),
        "process_count": len(psutil.pids()),
    }
