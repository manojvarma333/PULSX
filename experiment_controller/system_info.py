"""System/hardware info collection (PRD section 37), stored with every experiment for
reproducibility (PRD section 29). All lookups are best-effort: missing tools (g++,
docker, git) yield None rather than raising, since this is a local research tool that
must run even on a minimally-provisioned machine.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys

import psutil


def _run(cmd: list[str]) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def collect_system_info() -> dict:
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu_model": platform.processor() or platform.machine(),
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "python_version": sys.version.split()[0],
        "gpp_version": _run(["g++", "--version"]),
        "docker_version": _run(["docker", "--version"]),
        "git_commit": _run(["git", "rev-parse", "HEAD"]),
    }
