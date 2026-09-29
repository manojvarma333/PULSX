"""CPU/memory sampling for the current process (PRD section 13/38). Wraps psutil so the
rest of the codebase doesn't depend on it directly.
"""
from __future__ import annotations

import os

try:
    import psutil
    _process = psutil.Process(os.getpid())
    _process.cpu_percent(interval=None)  # prime the internal baseline
except ImportError:  # pragma: no cover - psutil is an optional runtime dependency
    psutil = None
    _process = None


def sample_process_usage() -> dict:
    """Returns {"cpu_usage": percent, "memory_usage": percent}. 0.0/0.0 if psutil is unavailable."""
    if _process is None:
        return {"cpu_usage": 0.0, "memory_usage": 0.0}
    return {
        "cpu_usage": _process.cpu_percent(interval=None),
        "memory_usage": _process.memory_percent(),
    }
